package server

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/Shopify/sarama"
	"github.com/go-redis/redis/v8"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/websocket/v2"
	"github.com/streadway/amqp"
	"food-delivery/main_server/types"
)

type MainServer struct {
	rdb       *redis.Client
	rabbitmq  *amqp.Connection
	kafka     sarama.SyncProducer
	wsClients map[string]*websocket.Conn
}

func NewMainServer(redisAddr, rabbitmqURL, kafkaAddr string) (*MainServer, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr: redisAddr,
	})

	rmq, err := amqp.Dial(rabbitmqURL)
	if err != nil {
		return nil, err
	}

	kafkaConfig := sarama.NewConfig()
	kafkaConfig.Producer.Return.Successes = true

	producer, err := sarama.NewSyncProducer([]string{kafkaAddr}, kafkaConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create kafka producer: %w", err)
	}

	return &MainServer{
		rdb:       rdb,
		rabbitmq:  rmq,
		kafka:     producer,
		wsClients: make(map[string]*websocket.Conn),
	}, nil
}

func (s *MainServer) logEvent(topic string, event map[string]interface{}) error {
	event["timestamp"] = time.Now().Unix()
	data, err := json.Marshal(event)
	if err != nil {
		return err
	}

	_, _, err = s.kafka.SendMessage(&sarama.ProducerMessage{
		Topic: topic,
		Value: sarama.StringEncoder(data),
	})
	return err
}

func (s *MainServer) ConsumeOrders() {
	ch, err := s.rabbitmq.Channel()
	if err != nil {
		log.Fatal(err)
	}
	defer ch.Close()

	q, err := ch.QueueDeclare("food-queue", true, false, false, false, nil)
	if err != nil {
		log.Fatal(err)
	}

	msgs, err := ch.Consume(q.Name, "", true, false, false, false, nil)
	if err != nil {
		log.Fatal(err)
	}

	for msg := range msgs {
		orderID := string(msg.Body)
		go s.processOrder(orderID)
	}
}

func (s *MainServer) processOrder(orderID string) {
	details, err := s.getOrderDetails(orderID)
	if err != nil {
		log.Printf("Error getting order details: %v", err)
		return
	}

	courierID := s.findNearestCourier(details.RestaurantLat, details.RestaurantLon)
	if courierID == "" {
		log.Printf("No available couriers for order %s", orderID)
		return
	}

	if err := s.assignOrderToCourier(orderID, courierID, details); err != nil {
		log.Printf("Error assigning order: %v", err)
		return
	}
}

func (s *MainServer) getOrderDetails(orderID string) (*types.OrderDetails, error) {
	resp, err := http.Get(fmt.Sprintf("http://django:8000/internal/order/%s", orderID))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var details types.OrderDetails
	if err := json.NewDecoder(resp.Body).Decode(&details); err != nil {
		return nil, err
	}
	return &details, nil
}

func (s *MainServer) findNearestCourier(lat, lon float64) string {
	ctx := context.Background()
	var nearestID string
	minDistance := math.MaxFloat64

	keys, err := s.rdb.Keys(ctx, "courier:*").Result()
	if err != nil {
		return ""
	}

	for _, key := range keys {
		courierData, err := s.rdb.HGetAll(ctx, key).Result()
		if err != nil {
			continue
		}

		if courierData["is_active"] == "true" && courierData["is_busy"] == "false" {
			cLat, _ := strconv.ParseFloat(courierData["latitude"], 64)
			cLon, _ := strconv.ParseFloat(courierData["longitude"], 64)

			dist := calculateDistance(lat, lon, cLat, cLon)
			if dist < minDistance {
				minDistance = dist
				nearestID = strings.TrimPrefix(key, "courier:")
			}
		}
	}
	return nearestID
}

func (s *MainServer) assignOrderToCourier(orderID, courierID string, details *types.OrderDetails) error {
	ctx := context.Background()

	// Mark courier as busy
	err := s.rdb.HSet(ctx, "courier:"+courierID, "is_busy", "true").Err()
	if err != nil {
		return err
	}

	// Send order to courier via WebSocket
	if ws, ok := s.wsClients[courierID]; ok {
		orderMsg := map[string]interface{}{
			"order_id":           orderID,
			"restaurant_address": details.RestaurantAddress,
			"delivery_address":   details.DeliveryAddress,
			"details":            details.Details,
		}
		if err := ws.WriteJSON(orderMsg); err != nil {
			return err
		}
	} else {
		return fmt.Errorf("courier %s not connected", courierID)
	}

	// Log assignment event
	err = s.logEvent("food_orders", map[string]interface{}{
		"event":      "order_assigned",
		"order_id":   orderID,
		"courier_id": courierID,
	})
	if err != nil {
		log.Printf("Failed to log assignment event: %v", err)
	}

	return nil
}

func (s *MainServer) handleDeliveryConfirmation(courierID, orderID string) {
	ctx := context.Background()

	// Mark courier as available
	err := s.rdb.HSet(ctx, "courier:"+courierID, "is_busy", "false").Err()
	if err != nil {
		log.Printf("Failed to update courier status: %v", err)
	}

	// Notify Django
	_, err = http.Post(
		fmt.Sprintf("http://django:8000/internal/order/%s/complete", orderID),
		"application/json",
		strings.NewReader(`{"status":"delivered"}`),
	)
	if err != nil {
		log.Printf("Failed to notify Django: %v", err)
	}

	// Log delivery event
	err = s.logEvent("food_orders", map[string]interface{}{
		"event":      "order_delivered",
		"order_id":   orderID,
		"courier_id": courierID,
	})
	if err != nil {
		log.Printf("Failed to log delivery event: %v", err)
	}
}

func (s *MainServer) HandleCourierWebSocket(c *websocket.Conn) {
	courierID := c.Query("courier_id")
	s.wsClients[courierID] = c
	defer delete(s.wsClients, courierID)

	for {
		var msg struct {
			Event   string `json:"event"`
			OrderID string `json:"order_id"`
		}

		if err := c.ReadJSON(&msg); err != nil {
			break
		}

		if msg.Event == "delivery_confirmed" {
			s.handleDeliveryConfirmation(courierID, msg.OrderID)
		}
	}
}

func (s *MainServer) HandleTrackingWebSocket(c *websocket.Conn) {
	orderID := c.Query("order_id")
	if orderID == "" {
		return
	}

	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		courierID, err := s.rdb.Get(context.Background(), "order:"+orderID+":courier").Result()
		if err != nil {
			continue
		}

		location, err := s.rdb.HGetAll(context.Background(), "courier:"+courierID).Result()
		if err != nil {
			continue
		}

		if location["is_active"] == "false" {
			c.WriteJSON(map[string]string{
				"message": "Курьер временно недоступен",
			})
			continue
		}

		c.WriteJSON(map[string]interface{}{
			"order_id":  orderID,
			"latitude":  location["latitude"],
			"longitude": location["longitude"],
		})
	}
}

func (s *MainServer) CheckCourierStatus() {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		ctx := context.Background()
		keys, err := s.rdb.Keys(ctx, "courier:*").Result()
		if err != nil {
			log.Printf("Failed to get courier keys: %v", err)
			continue
		}

		for _, key := range keys {
			s.checkSingleCourierStatus(ctx, key)
		}
	}
}

func (s *MainServer) checkSingleCourierStatus(ctx context.Context, key string) {
	courierData, err := s.rdb.HGetAll(ctx, key).Result()
	if err != nil {
		return
	}

	if courierData["is_busy"] == "true" {
		lastUpdate, _ := strconv.ParseInt(courierData["last_update"], 10, 64)
		if time.Now().Unix()-lastUpdate > 300 {
			courierID := strings.TrimPrefix(key, "courier:")
			s.handleCourierTimeout(courierID)
		}
	}
}

func calculateDistance(lat1, lon1, lat2, lon2 float64) float64 {
	const R = 6371 // Earth radius in kilometers

	lat1Rad := lat1 * math.Pi / 180
	lat2Rad := lat2 * math.Pi / 180
	deltaLat := (lat2 - lat1) * math.Pi / 180
	deltaLon := (lon2 - lon1) * math.Pi / 180

	a := math.Sin(deltaLat/2)*math.Sin(deltaLat/2) +
		math.Cos(lat1Rad)*math.Cos(lat2Rad)*
			math.Sin(deltaLon/2)*math.Sin(deltaLon/2)
	c := 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))

	return R * c
}

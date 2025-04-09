package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"time"
	"github.com/Shopify/sarama"
	"github.com/streadway/amqp"
)

func (s *Server) consumeOrders() {
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

func (s *Server) processOrder(orderID string) {
	// Get order details from Django
	resp, err := http.Get(fmt.Sprintf("http://django:8000/internal/order/%s", orderID))
	if err != nil {
		return
	}
	defer resp.Body.Close()

	var orderInfo OrderInfo
	if err := json.NewDecoder(resp.Body).Decode(&orderInfo); err != nil {
		return
	}

	// Find nearest courier
	courierID := s.findNearestCourier(orderInfo.RestaurantLat, orderInfo.RestaurantLon)
	if courierID == "" {
		return
	}

	// Update Redis and send order to courier
	s.assignOrderToCourier(orderID, courierID, &orderInfo)
}

func (s *Server) findNearestCourier(lat, lon float64) string {
	ctx := context.Background()
	var nearestCourierID string
	minDistance := math.MaxFloat64

	// Get all courier keys
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
				nearestCourierID = strings.TrimPrefix(key, "courier:")
			}
		}
	}

	return nearestCourierID
}

func (s *Server) checkCourierStatus() {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		ctx := context.Background()
		keys, err := s.rdb.Keys(ctx, "courier:*").Result()
		if err != nil {
			continue
		}

		for _, key := range keys {
			courierData, err := s.rdb.HGetAll(ctx, key).Result()
			if err != nil {
				continue
			}

			if courierData["is_busy"] == "true" {
				lastUpdate, _ := strconv.ParseInt(courierData["last_update"], 10, 64)
				if time.Now().Unix()-lastUpdate > 300 { // 5 minutes
					courierID := strings.TrimPrefix(key, "courier:")
					s.handleCourierTimeout(courierID)
				}
			}
		}
	}
}

func calculateDistance(lat1, lon1, lat2, lon2 float64) float64 {
	// Haversine formula implementation
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

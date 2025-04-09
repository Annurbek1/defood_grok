package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math"
	"math/rand"
	"sync"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/swagger"
	_ "food-delivery/delivery/docs"

	"github.com/streadway/amqp"
)

// @title Delivery Service API
// @version 1.0
// @description Delivery service for food ordering system
// @host localhost:4000
// @BasePath /

type DeliveryPerson struct {
	ID        string  `json:"id"`
	Latitude  float64 `json:"lat"`
	Longitude float64 `json:"lon"`
	Available bool    `json:"available"`
}

type DeliveryOrder struct {
	OrderID string  `json:"order_id"`
	Lat     float64 `json:"lat"`
	Lon     float64 `json:"lon"`
}

var (
	deliveryPersons = make(map[string]DeliveryPerson)
	dpMux           sync.Mutex
)

func main() {
	rand.Seed(time.Now().UnixNano())

	go func() {
		for {
			conn, err := amqp.Dial("amqp://guest:guest@localhost:5672/")
			if err != nil {
				log.Printf("RabbitMQ connection error: %v. Retrying in 5 seconds...", err)
				time.Sleep(5 * time.Second)
				continue
			}
			defer conn.Close()

			ch, err := conn.Channel()
			if err != nil {
				log.Printf("Failed to open channel: %v. Retrying in 5 seconds...", err)
				time.Sleep(5 * time.Second)
				continue
			}
			defer ch.Close()

			go consumeDeliveryOrders(conn)

			// Wait for connection to close
			<-conn.NotifyClose(make(chan *amqp.Error))
			log.Println("RabbitMQ connection lost. Reconnecting...")
		}
	}()

	go simulateDeliveryPersons()

	app := fiber.New(fiber.Config{
		ReadTimeout:  time.Second * 10,
		WriteTimeout: time.Second * 10,
	})

	app.Use(logger.New())

	// Swagger route should be before other routes
	app.Get("/swagger/*", swagger.New(swagger.Config{
		Title: "Delivery Service API",
	}))

	// @Summary Get all delivery persons
	// @Tags Delivery
	// @Produce json
	// @Success 200 {array} DeliveryPerson
	// @Router /delivery-persons [get]
	app.Get("/delivery-persons", func(c *fiber.Ctx) error {
		dpMux.Lock()
		defer dpMux.Unlock()

		var dps []DeliveryPerson
		for _, dp := range deliveryPersons {
			dps = append(dps, dp)
		}
		return c.JSON(dps)
	})

	// @Summary Health check
	// @Tags Health
	// @Success 200 {object} map[string]string
	// @Router /health [get]
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"status": "Delivery service running",
		})
	})

	port := ":4000"
	log.Printf("Delivery service starting on %s", port)
	if err := app.Listen(port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

func consumeDeliveryOrders(conn *amqp.Connection) {
	ch, err := conn.Channel()
	if err != nil {
		log.Printf("Channel error: %v", err)
		return
	}
	defer ch.Close()

	// Declare delivery_orders queue
	ordersQueue, err := ch.QueueDeclare(
		"delivery_orders", 
		true,   // durable
		false,  // delete when unused
		false,  // exclusive
		false,  // no-wait
		nil,    // arguments
	)
	if err != nil {
		log.Printf("Failed to declare delivery_orders queue: %v", err)
		return
	}

	// Declare delivery_updates queue (без сохранения в переменную)
	_, err = ch.QueueDeclare(
		"delivery_updates",
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		log.Printf("Failed to declare delivery_updates queue: %v", err)
		return
	}

	msgs, err := ch.Consume(
		ordersQueue.Name,
		"",
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		log.Fatal("Consume error:", err)
	}

	for d := range msgs {
		var order DeliveryOrder
		if err := json.Unmarshal(d.Body, &order); err != nil {
			log.Printf("Failed to parse order: %v", err)
			continue
		}
		go processDeliveryOrder(order, ch)
	}
}

func processDeliveryOrder(order DeliveryOrder, ch *amqp.Channel) {
	assignedID := assignDeliveryPerson(order)

	status := "in_delivery"
	if assignedID == "" {
		status = "failed"
	}

	update := map[string]interface{}{
		"order_id":    order.OrderID,
		"status":      status,
		"delivery_id": assignedID,
	}

	body, _ := json.Marshal(update)
	_ = ch.Publish("", "delivery_updates", false, false, amqp.Publishing{
		ContentType: "application/json",
		Body:        body,
	})
}

func assignDeliveryPerson(order DeliveryOrder) string {
	dpMux.Lock()
	defer dpMux.Unlock()

	var closestID string
	minDistance := math.MaxFloat64

	for id, dp := range deliveryPersons {
		if dp.Available {
			distance := calculateDistance(order.Lat, order.Lon, dp.Latitude, dp.Longitude)
			if distance < minDistance {
				minDistance = distance
				closestID = id
			}
		}
	}

	if closestID != "" {
		dp := deliveryPersons[closestID]
		dp.Available = false
		deliveryPersons[closestID] = dp
		go simulateDeliveryCompletion(closestID)
	}

	return closestID
}

func simulateDeliveryCompletion(dpID string) {
	time.Sleep(1 * time.Minute) // Simulate delivery
	dpMux.Lock()
	defer dpMux.Unlock()
	if dp, exists := deliveryPersons[dpID]; exists {
		dp.Available = true
		deliveryPersons[dpID] = dp
	}
}

func simulateDeliveryPersons() {
	for {
		time.Sleep(15 * time.Second)
		dpMux.Lock()
		id := fmt.Sprintf("dp-%d", len(deliveryPersons)+1)
		deliveryPersons[id] = DeliveryPerson{
			ID:        id,
			Latitude:  40.7128 + rand.Float64()*0.1 - 0.05,
			Longitude: -74.0060 + rand.Float64()*0.1 - 0.05,
			Available: true,
		}
		dpMux.Unlock()
		log.Printf("New delivery person: %s", id)
	}
}

func calculateDistance(lat1, lon1, lat2, lon2 float64) float64 {
	return math.Sqrt(math.Pow(lat2-lat1, 2) + math.Pow(lon2-lon1, 2))
}

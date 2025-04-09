package main

import (
	"encoding/json"
	"log"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/streadway/amqp"
)

type OrderMessage struct {
	OrderID string      `json:"order_id"`
	Order   OrderRequest `json:"order"`
}

type OrderRequest struct {
	FoodID         int    `json:"food_id"`
	Location       string `json:"location"`
	RestaurantName string `json:"restaurant_name"`
	CustomerName   string `json:"customer_name"`
	CustomerPhone  string `json:"customer_phone"`
	PaymentMethod  string `json:"payment_method"`
}

func main() {
	conn, err := amqp.Dial("amqp://guest:guest@localhost:5672/")
	if err != nil {
		log.Fatal("Failed to connect to RabbitMQ:", err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		log.Fatal("Failed to open channel:", err)
	}
	defer ch.Close()

	_, err = ch.QueueDeclare("orders", true, false, false, false, nil)
	if err != nil {
		log.Fatal("Failed to declare queue:", err)
	}

	msgs, err := ch.Consume("orders", "", true, false, false, false, nil)
	if err != nil {
		log.Fatal("Failed to register consumer:", err)
	}

	forever := make(chan bool)

	go func() {
		for d := range msgs {
			var order OrderMessage
			if err := json.Unmarshal(d.Body, &order); err != nil {
				log.Printf("Error processing order: %v", err)
				continue
			}

			log.Printf("Processing order %s for %s", order.OrderID, order.Order.RestaurantName)
		}
	}()

	app := fiber.New(fiber.Config{
		ReadTimeout:  time.Second * 10,
		WriteTimeout: time.Second * 10,
	})

	app.Use(logger.New())

	// Health check endpoint
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"status":  "ok",
			"service": "restaurant",
		})
	})

	port := ":3000"
	log.Printf("Restaurant service starting on %s", port)
	if err := app.Listen(port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
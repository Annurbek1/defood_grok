package main

import (
	"context"
	"encoding/json"
	"food-delivery/api/config"
	"log"
	"time"

	"github.com/Shopify/sarama"
	"github.com/go-redis/redis/v8"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"github.com/gofiber/swagger"
	"github.com/gofiber/websocket/v2"
	"github.com/streadway/amqp"
)

type Server struct {
	config     *config.Config
	rdb        *redis.Client
	rabbitmq   *amqp.Connection
	kafka      sarama.SyncProducer
	wsClients  map[string]*websocket.Conn
	orderInfos map[string]*OrderInfo
}

type OrderInfo struct {
	OrderID       string  `json:"order_id"`
	CourierID     string  `json:"courier_id"`
	RestaurantLat float64 `json:"restaurant_latitude"`
	RestaurantLon float64 `json:"restaurant_longitude"`
	DeliveryLat   float64 `json:"delivery_latitude"`
	DeliveryLon   float64 `json:"delivery_longitude"`
	Details       string  `json:"details"`
}

func main() {
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Fatal("Failed to load config:", err)
	}

	server := &Server{
		config:     cfg,
		wsClients:  make(map[string]*websocket.Conn),
		orderInfos: make(map[string]*OrderInfo),
	}

	// Initialize connections
	if err := server.initConnections(); err != nil {
		log.Fatal("Failed to initialize connections:", err)
	}

	app := fiber.New(fiber.Config{
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
		ErrorHandler: errorHandler,
	})

	// Middlewares
	app.Use(recover.New())
	app.Use(logger.New())
	app.Use(cors.New())

	// Routes
	setupRoutes(app, server)

	// Swagger
	app.Get("/swagger/*", swagger.HandlerDefault)

	// WebSocket routes
	app.Use("/ws", server.validateToken)
	app.Get("/ws", websocket.New(server.handleCourierWebSocket))
	app.Get("/track", websocket.New(server.handleTrackingWebSocket))

	// Start order consumer
	go server.consumeOrders()

	// Start courier status checker
	go server.checkCourierStatus()

	log.Printf("Server starting on port %s", cfg.Server.Port)
	log.Fatal(app.Listen(":" + cfg.Server.Port))
}

func setupRoutes(app *fiber.App, server *Server) {
	// Health check
	app.Get("/health", healthCheck)

	// API v1
	v1 := app.Group("/api/v1")

	// Orders
	orders := v1.Group("/orders")
	orders.Post("/", createOrder)
	orders.Get("/", getOrders)
	orders.Get("/:id", getOrder)
	orders.Put("/:id", updateOrder)

	// Delivery
	delivery := v1.Group("/delivery")
	delivery.Get("/couriers", getCouriers)
	delivery.Post("/assign", assignCourier)
}

func (s *Server) initConnections() error {
	// Redis connection
	s.rdb = redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})

	// RabbitMQ connection
	conn, err := amqp.Dial("amqp://guest:guest@rabbitmq-denaueats:5672/")
	if err != nil {
		return err
	}
	s.rabbitmq = conn

	// Kafka producer
	config := sarama.NewConfig()
	config.Producer.Return.Successes = true
	producer, err := sarama.NewSyncProducer([]string{"kafka-denaueats:9092"}, config)
	if err != nil {
		return err
	}
	s.kafka = producer

	return nil
}

func errorHandler(c *fiber.Ctx, err error) error {
	code := fiber.StatusInternalServerError

	if e, ok := err.(*fiber.Error); ok {
		code = e.Code
	}

	return c.Status(code).JSON(fiber.Map{
		"error": err.Error(),
	})
}

func healthCheck(c *fiber.Ctx) error {
	return c.JSON(fiber.Map{
		"status": "ok",
		"time":   time.Now(),
	})
}

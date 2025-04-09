package main

import (
	"context"
	"encoding/json"
	"fmt"
	"food-delivery/api/config"
	"log"
	"strconv"
	"strings"
	"time"

	"github.com/Shopify/sarama"
	"github.com/go-redis/redis/v8"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"github.com/gofiber/swagger"
	"github.com/gofiber/websocket/v2"
	"github.com/golang-jwt/jwt/v4"
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
		Addr: s.config.Redis.Addr,
		DB:   s.config.Redis.DB,
	})

	if err := s.rdb.Ping(context.Background()).Err(); err != nil {
		return fmt.Errorf("redis connection failed: %v", err)
	}

	// RabbitMQ connection with retry
	var rabbitmqConn *amqp.Connection
	var err error
	for i := 0; i < 5; i++ {
		log.Printf("Attempting to connect to RabbitMQ (attempt %d/5)...", i+1)
		rabbitmqConn, err = amqp.Dial(s.config.RabbitMQ.URL)
		if err == nil {
			break
		}
		if i < 4 {
			log.Printf("Failed to connect to RabbitMQ: %v. Retrying in 5 seconds...", err)
			time.Sleep(5 * time.Second)
		}
	}
	if err != nil {
		return fmt.Errorf("failed to connect to RabbitMQ after 5 attempts: %v", err)
	}
	s.rabbitmq = rabbitmqConn

	// Kafka setup with retry
	kafkaConfig := sarama.NewConfig()
	kafkaConfig.Producer.Return.Successes = true

	var producer sarama.SyncProducer
	for i := 0; i < 5; i++ {
		producer, err = sarama.NewSyncProducer(s.config.Kafka.Brokers, kafkaConfig)
		if err == nil {
			break
		}
		if i < 4 {
			log.Printf("Failed to connect to Kafka: %v. Retrying in 5 seconds...", err)
			time.Sleep(5 * time.Second)
		}
	}
	if err != nil {
		return fmt.Errorf("failed to create Kafka producer: %v", err)
	}
	s.kafka = producer

	return nil
}

func (s *Server) validateToken(c *fiber.Ctx) error {
	token := c.Query("token")
	courierID := c.Query("courier_id")

	if token == "" || courierID == "" {
		return fiber.ErrUnauthorized
	}

	claims := jwt.MapClaims{}
	_, err := jwt.ParseWithClaims(token, claims, func(token *jwt.Token) (interface{}, error) {
		return []byte(s.config.JWT.SecretKey), nil
	})

	if err != nil || claims["courier_id"] != courierID {
		return fiber.ErrUnauthorized
	}

	return c.Next()
}

func (s *Server) handleCourierWebSocket(c *websocket.Conn) {
	courierID := c.Query("courier_id")
	ctx := context.Background()

	// Set courier as active in Redis
	err := s.rdb.HSet(ctx, "courier:"+courierID, map[string]interface{}{
		"is_active":   "true",
		"last_update": time.Now().Unix(),
	}).Err()

	if err != nil {
		log.Printf("Error setting courier active: %v", err)
		return
	}

	// Ensure courier is marked inactive when connection closes
	defer func() {
		if err := s.rdb.HSet(ctx, "courier:"+courierID, "is_active", "false").Err(); err != nil {
			log.Printf("Error setting courier inactive: %v", err)
		}
		delete(s.wsClients, courierID)
	}()

	s.wsClients[courierID] = c

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

func (s *Server) logEvent(topic string, event map[string]interface{}) error {
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

func (s *Server) checkCourierStatus() {
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

func (s *Server) handleCourierTimeout(courierID string) {
	ctx := context.Background()

	// Reset courier status
	err := s.rdb.HSet(ctx, "courier:"+courierID, "is_busy", "false").Err()
	if err != nil {
		log.Printf("Failed to reset courier status: %v", err)
		return
	}

	// Get order ID from courier
	orderID, err := s.rdb.Get(ctx, "courier:"+courierID+":order").Result()
	if err != nil {
		return
	}

	// Return order to queue
	ch, err := s.rabbitmq.Channel()
	if err != nil {
		return
	}
	defer ch.Close()

	err = ch.Publish(
		"",           // exchange
		"food-queue", // routing key
		false,        // mandatory
		false,        // immediate
		amqp.Publishing{
			ContentType: "text/plain",
			Body:        []byte(orderID),
		},
	)
	if err != nil {
		log.Printf("Failed to return order to queue: %v", err)
	}

	// Log event
	s.logEvent("food_orders", map[string]interface{}{
		"event":      "courier_timeout",
		"courier_id": courierID,
		"order_id":   orderID,
	})
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

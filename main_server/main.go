package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"github.com/gofiber/swagger"
	"github.com/gofiber/websocket/v2"
	_ "food-delivery/main_server/docs"
	"food-delivery/main_server/server"
)

func main() {
	srv, err := server.NewMainServer(
		"localhost:6379",
		"amqp://guest:guest@rabbitmq-denaueats:5672/",
		"kafka-denaueats:9092",
	)
	if err != nil {
		log.Fatal(err)
	}

	app := fiber.New(fiber.Config{
		ReadTimeout:  time.Second * 10,
		WriteTimeout: time.Second * 10,
		ErrorHandler: errorHandler,
	})

	// Middleware
	app.Use(recover.New())
	app.Use(logger.New())
	app.Use(srv.MetricsMiddleware())

	// Swagger
	app.Get("/swagger/*", swagger.HandlerDefault)

	// Metrics endpoint
	app.Get("/metrics", prometheusHandler())

	// WebSocket routes
	app.Use("/ws", srv.ValidateToken)
	app.Get("/ws", websocket.New(srv.HandleCourierWebSocket))
	app.Get("/track", websocket.New(srv.HandleTrackingWebSocket))

	// Start order consumer
	go srv.ConsumeOrders()

	// Start courier status checker
	go srv.CheckCourierStatus()

	// Graceful shutdown
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-c
		log.Println("Gracefully shutting down...")
		_ = app.Shutdown()
	}()

	log.Fatal(app.Listen(":8080"))
}

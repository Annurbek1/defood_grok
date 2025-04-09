package main

import (
	"food-delivery/location/server"
	"log"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/websocket/v2"
)

func main() {
	app := fiber.New()
	locationServer := server.NewLocationServer("localhost:6379")

	// WebSocket route with token validation
	app.Use("/ws", locationServer.ValidateToken)
	app.Get("/ws", websocket.New(locationServer.HandleWSConnection))

	// Health check endpoint
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"status":  "ok",
			"service": "location",
		})
	})

	log.Fatal(app.Listen(":9000"))
}

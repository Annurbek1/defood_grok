package server

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/websocket/v2"
	"github.com/golang-jwt/jwt"
)

type LocationServer struct {
	rdb *redis.Client
}

type LocationUpdate struct {
	CourierID string  `json:"courier_id"`
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
}

func NewLocationServer(redisAddr string) *LocationServer {
	return &LocationServer{
		rdb: redis.NewClient(&redis.Options{
			Addr: redisAddr,
		}),
	}
}

func (s *LocationServer) ValidateToken(c *fiber.Ctx) error {
	token := c.Query("token")
	courierID := c.Query("courier_id")

	if token == "" || courierID == "" {
		return fiber.ErrUnauthorized
	}

	claims := jwt.MapClaims{}
	_, err := jwt.ParseWithClaims(token, claims, func(token *jwt.Token) (interface{}, error) {
		return []byte("my-secret-key"), nil
	})

	if err != nil || claims["courier_id"] != courierID {
		return fiber.ErrUnauthorized
	}

	return c.Next()
}

func (s *LocationServer) HandleWSConnection(c *websocket.Conn) {
	courierID := c.Query("courier_id")
	ctx := context.Background()

	// Set courier as active
	err := s.rdb.HSet(ctx, "courier:"+courierID, map[string]interface{}{
		"is_active":   "true",
		"last_update": time.Now().Unix(),
	}).Err()

	if err != nil {
		log.Printf("Error setting courier active: %v", err)
		return
	}

	// Ensure we set courier as inactive when connection closes
	defer func() {
		err := s.rdb.HSet(ctx, "courier:"+courierID, "is_active", "false").Err()
		if err != nil {
			log.Printf("Error setting courier inactive: %v", err)
		}
		c.Close()
	}()

	for {
		var update LocationUpdate
		if err := c.ReadJSON(&update); err != nil {
			break
		}

		if update.CourierID != courierID {
			continue
		}

		// Update location in Redis
		err := s.rdb.HMSet(ctx, "courier:"+courierID, map[string]interface{}{
			"latitude":    update.Latitude,
			"longitude":   update.Longitude,
			"last_update": time.Now().Unix(),
		}).Err()

		if err != nil {
			log.Printf("Error updating courier location: %v", err)
		}
	}
}

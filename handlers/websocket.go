package handlers

import (
	"context"
	"encoding/json"
	"github.com/gofiber/websocket/v2"
	"github.com/golang-jwt/jwt"
	"strings"
	"time"
)

func (s *Server) validateToken(c *fiber.Ctx) error {
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

func (s *Server) handleCourierWebSocket(c *websocket.Conn) {
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

func (s *Server) handleTrackingWebSocket(c *websocket.Conn) {
	orderID := c.Query("order_id")
	if orderID == "" {
		return
	}

	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		orderInfo, exists := s.orderInfos[orderID]
		if !exists {
			continue
		}

		// Get courier location from Redis
		courierKey := "courier:" + orderInfo.CourierID
		location, err := s.rdb.HGetAll(context.Background(), courierKey).Result()
		if err != nil {
			continue
		}

		if location["is_active"] == "false" {
			c.WriteJSON(fiber.Map{
				"message": "Курьер временно недоступен",
			})
			continue
		}

		c.WriteJSON(fiber.Map{
			"order_id":  orderID,
			"latitude":  location["latitude"],
			"longitude": location["longitude"],
		})
	}
}

// ... (continuing in next section)

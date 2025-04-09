package models

import "time"

type OrderStatus string

const (
	OrderStatusPending    OrderStatus = "pending"
	OrderStatusAccepted   OrderStatus = "accepted"
	OrderStatusPreparing  OrderStatus = "preparing"
	OrderStatusReady      OrderStatus = "ready"
	OrderStatusDelivering OrderStatus = "delivering"
	OrderStatusDelivered  OrderStatus = "delivered"
	OrderStatusCancelled  OrderStatus = "cancelled"
)

type Order struct {
	ID            string      `json:"id"`
	CustomerID    string      `json:"customer_id"`
	RestaurantID  string      `json:"restaurant_id"`
	Items         []OrderItem `json:"items"`
	TotalPrice    float64     `json:"total_price"`
	Status        OrderStatus `json:"status"`
	DeliveryInfo  DeliveryInfo `json:"delivery_info"`
	PaymentInfo   PaymentInfo  `json:"payment_info"`
	CreatedAt     time.Time    `json:"created_at"`
	UpdatedAt     time.Time    `json:"updated_at"`
}

type OrderItem struct {
	FoodID     string  `json:"food_id"`
	Quantity   int     `json:"quantity"`
	UnitPrice  float64 `json:"unit_price"`
	TotalPrice float64 `json:"total_price"`
}

type DeliveryInfo struct {
	Address     Address     `json:"address"`
	CourierID   string      `json:"courier_id,omitempty"`
	EstimatedTime time.Time `json:"estimated_time"`
}

type Address struct {
	Latitude   float64 `json:"latitude"`
	Longitude  float64 `json:"longitude"`
	Street     string  `json:"street"`
	City       string  `json:"city"`
	PostalCode string  `json:"postal_code"`
}

type PaymentInfo struct {
	Method  string `json:"method"`
	Status  string `json:"status"`
	Amount  float64 `json:"amount"`
}

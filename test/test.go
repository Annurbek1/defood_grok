package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
)

func main() {
	// 1. Создаем тестовый заказ
	createTestOrder()

	// 2. Эмулируем курьера
	go simulateCourier()

	// 3. Эмулируем клиента, отслеживающего заказ
	trackOrder()

	select {}
}

func createTestOrder() {
	order := map[string]interface{}{
		"customer_id":   "test_customer",
		"restaurant_id": "test_restaurant",
		"items": []map[string]interface{}{
			{
				"food_id":     "food1",
				"quantity":    2,
				"unit_price":  10.5,
				"total_price": 21.0,
			},
		},
		"delivery_info": map[string]interface{}{
			"address": map[string]interface{}{
				"latitude":    40.7128,
				"longitude":   -74.0060,
				"street":      "Test Street",
				"city":        "Test City",
				"postal_code": "12345",
			},
		},
	}

	jsonData, _ := json.Marshal(order)
	resp, err := http.Post("http://localhost:8080/api/v1/orders", 
		"application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		fmt.Printf("Ошибка создания заказа: %v\n", err)
		return
	}
	fmt.Printf("Заказ создан, статус: %d\n", resp.StatusCode)
}

func simulateCourier() {
	// Подключаемся к серверу локации
	url := "ws://localhost:9000/ws?courier_id=test_courier&token=test_token"
	c, _, err := websocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		fmt.Printf("Ошибка подключения курьера: %v\n", err)
		return
	}
	defer c.Close()

	// Отправляем обновления локации
	ticker := time.NewTicker(10 * time.Second)
	lat, lon := 40.7128, -74.0060
	
	for range ticker.C {
		location := map[string]interface{}{
			"courier_id": "test_courier",
			"latitude":   lat,
			"longitude":  lon,
		}
		lat += 0.001 // Имитируем движение
		lon += 0.001

		if err := c.WriteJSON(location); err != nil {
			fmt.Printf("Ошибка отправки локации: %v\n", err)
			return
		}
		fmt.Printf("Локация курьера обновлена: %f, %f\n", lat, lon)
	}
}

func trackOrder() {
	// Подключаемся к отслеживанию заказа
	url := "ws://localhost:8080/track?order_id=test_order"
	c, _, err := websocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		fmt.Printf("Ошибка подключения к отслеживанию: %v\n", err)
		return
	}
	defer c.Close()

	// Читаем обновления о местоположении
	for {
		var update map[string]interface{}
		if err := c.ReadJSON(&update); err != nil {
			fmt.Printf("Ошибка чтения обновления: %v\n", err)
			return
		}
		fmt.Printf("Получено обновление о доставке: %v\n", update)
	}
}

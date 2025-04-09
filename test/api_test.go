package test

import (
    "bytes"
    "encoding/json"
    "net/http"
    "testing"
)

func TestAPI(t *testing.T) {
    // Тест создания заказа
    order := map[string]interface{}{
        "customer_id": "test_customer",
        "restaurant_id": "test_restaurant",
        "items": []map[string]interface{}{
            {
                "food_id": "1",
                "quantity": 2,
                "unit_price": 10.5,
            },
        },
        "delivery_info": map[string]interface{}{
            "address": map[string]interface{}{
                "latitude": 55.7558,
                "longitude": 37.6173,
                "street": "Test Street",
                "city": "Moscow",
            },
        },
    }

    jsonData, _ := json.Marshal(order)
    resp, err := http.Post(
        "http://localhost:8080/api/v1/orders",
        "application/json",
        bytes.NewBuffer(jsonData),
    )

    if err != nil {
        t.Fatalf("Failed to create order: %v", err)
    }

    if resp.StatusCode != http.StatusOK {
        t.Errorf("Expected status OK, got %v", resp.Status)
    }
}

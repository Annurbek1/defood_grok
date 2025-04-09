package types

type OrderDetails struct {
    OrderID           string  `json:"order_id"`
    RestaurantLat    float64 `json:"restaurant_latitude"`
    RestaurantLon    float64 `json:"restaurant_longitude"`
    DeliveryLat      float64 `json:"delivery_latitude"`
    DeliveryLon      float64 `json:"delivery_longitude"`
    Details          string  `json:"details"`
    RestaurantAddress string `json:"restaurant_address"`
    DeliveryAddress   string `json:"delivery_address"`
}

type CourierLocation struct {
    CourierID  string  `json:"courier_id"`
    Latitude   float64 `json:"latitude"`
    Longitude  float64 `json:"longitude"`
    IsActive   bool    `json:"is_active"`
    IsBusy     bool    `json:"is_busy"`
    LastUpdate int64   `json:"last_update"`
}

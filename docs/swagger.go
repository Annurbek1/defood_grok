package docs

import "github.com/swaggo/swag"

// @title Food Delivery API
// @version 1.0
// @description API для сервиса доставки еды
// @host localhost:8080
// @BasePath /api/v1

// @securityDefinitions.apikey ApiKeyAuth
// @in header
// @name Authorization
var SwaggerInfo = &swag.Spec{
    Version:     "1.0",
    Host:        "localhost:8080",
    BasePath:    "/api/v1",
    Title:       "Food Delivery API",
    Description: "API для сервиса доставки еды",
}

func init() {
    swag.Register(SwaggerInfo.InstanceName(), SwaggerInfo)
}

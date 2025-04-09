package docs

import "github.com/swaggo/swag"

// @title Food Delivery Main Server API
// @version 1.0
// @description Main server for food delivery system
// @host localhost:8080
// @BasePath /api/v1
// @schemes http
// @securityDefinitions.apikey BearerAuth
// @in header
// @name Authorization

var SwaggerInfo = &swag.Spec{
    Version:     "1.0",
    Host:        "localhost:8080",
    BasePath:    "/api/v1",
    Schemes:     []string{"http"},
    Title:       "Food Delivery Main Server API",
    Description: "Main server for food delivery system",
}

func init() {
    swag.Register(SwaggerInfo.InstanceName(), SwaggerInfo)
}

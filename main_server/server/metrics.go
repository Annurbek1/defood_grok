package server

import (
    "github.com/gofiber/fiber/v2"
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    ordersProcessed = promauto.NewCounter(prometheus.CounterOpts{
        Name: "food_delivery_orders_processed_total",
        Help: "The total number of processed orders",
    })

    activeCouriers = promauto.NewGauge(prometheus.GaugeOpts{
        Name: "food_delivery_active_couriers",
        Help: "The number of currently active couriers",
    })

    orderProcessingTime = promauto.NewHistogram(prometheus.HistogramOpts{
        Name: "food_delivery_order_processing_duration_seconds",
        Help: "Time spent processing order",
        Buckets: prometheus.DefBuckets,
    })
)

func (s *MainServer) metricsMiddleware() fiber.Handler {
    return func(c *fiber.Ctx) error {
        start := time.Now()
        err := c.Next()
        duration := time.Since(start).Seconds()
        
        orderProcessingTime.Observe(duration)
        
        return err
    }
}

package config

import (
	"os"
	"time"

	"github.com/joho/godotenv"
)

type Config struct {
	RabbitMQ RabbitMQConfig
	Server   ServerConfig
	Redis    RedisConfig
	Kafka    KafkaConfig
	JWT      JWTConfig
}

type RabbitMQConfig struct {
	URL          string
	ExchangeName string
	QueueName    string
}

type ServerConfig struct {
	Port            string
	ReadTimeout    time.Duration
	WriteTimeout   time.Duration
	MaxConnections int
}

type RedisConfig struct {
	Addr     string
	Password string
	DB       int
}

type KafkaConfig struct {
	Brokers []string
	Topic   string
}

type JWTConfig struct {
	SecretKey string
}

func LoadConfig() (*Config, error) {
	_ = godotenv.Load()

	return &Config{
		RabbitMQ: RabbitMQConfig{
			URL:          getEnv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq-denaueats:5672/"),
			ExchangeName: getEnv("RABBITMQ_EXCHANGE", "food_delivery"),
			QueueName:    getEnv("RABBITMQ_QUEUE", "food-queue"),
		},
		Server: ServerConfig{
			Port:            getEnv("SERVER_PORT", "8080"),
			ReadTimeout:    time.Second * 10,
			WriteTimeout:   time.Second * 10,
			MaxConnections: 1000,
		},
		Redis: RedisConfig{
			Addr:     getEnv("REDIS_ADDR", "localhost:6379"),
			Password: getEnv("REDIS_PASSWORD", ""),
			DB:       0,
		},
		Kafka: KafkaConfig{
			Brokers: []string{getEnv("KAFKA_BROKER", "kafka-denaueats:9092")},
			Topic:   getEnv("KAFKA_TOPIC", "food_orders"),
		},
		JWT: JWTConfig{
			SecretKey: getEnv("JWT_SECRET_KEY", "my-secret-key"),
		},
	}, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

#!/bin/bash

# Base project directory
PROJECT_DIR="/home/gaybullayev/Desktop/BISMILLAH"

# Функция для очистки и завершения
cleanup() {
    echo "Stopping services..."
    kill $(jobs -p)
    docker stop redis rabbitmq
    docker rm redis rabbitmq
    exit 0
}

# Перехват сигналов завершения
trap cleanup SIGINT SIGTERM

# Добавляем пользователя в группу docker
echo "Adding user to docker group..."
sudo usermod -aG docker $USER

# Запуск Redis
if ! docker ps | grep -q redis; then
    echo "Starting Redis..."
    docker run -d --name redis -p 6379:6379 redis
fi

# Запуск RabbitMQ
if ! docker ps | grep -q rabbitmq; then
    echo "Starting RabbitMQ..."
    docker run -d --name rabbitmq \
        -p 5672:5672 \
        -p 15672:15672 \
        rabbitmq:management
fi

# Ждем полного запуска RabbitMQ
echo "Waiting for RabbitMQ to start..."
sleep 15

# Проверка директорий
if [ ! -d "$PROJECT_DIR/delivery" ] || [ ! -d "$PROJECT_DIR/restorant" ]; then
    echo "Error: Required directories not found"
    cleanup
fi

# Запуск сервисов
echo "Starting delivery service..."
cd "$PROJECT_DIR/delivery" && go run main.go &
DELIVERY_PID=$!

echo "Starting restaurant service..."
cd "$PROJECT_DIR/restorant" && go run main.go &
RESTAURANT_PID=$!

echo "All services are running!"
echo "Press Ctrl+C to stop all services"

# Ожидание завершения всех процессов
wait

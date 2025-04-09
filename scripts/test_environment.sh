#!/bin/bash

# Проверяем, запущены ли необходимые сервисы
check_service() {
    if ! nc -z localhost $1 >/dev/null 2>&1; then
        echo "Error: Service on port $1 is not running"
        return 1
    fi
    return 0
}

# Запускаем все сервисы
echo "Starting services..."

# 1. Запускаем Docker контейнеры
docker-compose up -d redis rabbitmq kafka

# 2. Ждем запуска RabbitMQ
echo "Waiting for RabbitMQ to start..."
until nc -z localhost 5672; do
    sleep 1
done

# 3. Запускаем Django
echo "Starting Django server..."
cd ../django_project
python manage.py runserver 8000 &
DJANGO_PID=$!

# 4. Запускаем Go сервисы
echo "Starting Go services..."
cd ../main_server
go run main.go &
MAIN_SERVER_PID=$!

cd ../delivery
go run main.go &
DELIVERY_PID=$!

# 5. Проверяем, что все сервисы запущены
echo "Checking services..."
sleep 5

services_ok=true
check_service 8000 || services_ok=false  # Django
check_service 8080 || services_ok=false  # Main Server
check_service 4000 || services_ok=false  # Delivery Service
check_service 5672 || services_ok=false  # RabbitMQ
check_service 6379 || services_ok=false  # Redis
check_service 9092 || services_ok=false  # Kafka

if [ "$services_ok" = true ]; then
    echo "All services are running!"
    echo "Running integration tests..."
    cd ../tests
    python integration_test.py
else
    echo "Some services failed to start"
    exit 1
fi

# Cleanup
cleanup() {
    echo "Stopping services..."
    kill $DJANGO_PID $MAIN_SERVER_PID $DELIVERY_PID
    docker-compose down
}

trap cleanup EXIT

# Ждем сигнала завершения
wait

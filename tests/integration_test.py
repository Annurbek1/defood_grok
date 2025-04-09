import requests
import websocket
import json
import time

BASE_URL = "http://localhost:8000"
MAIN_WS_URL = "ws://localhost:8080"
LOCATION_WS_URL = "ws://localhost:8081"

def test_integration():
    # 1. Регистрация курьера
    register_data = {
        "phone_number": "998901234567",
        "password": "test123",
        "first_name": "Test",
        "last_name": "Courier"
    }
    response = requests.post(f"{BASE_URL}/register/", json=register_data)
    assert response.status_code == 201
    print("✓ Courier registration successful")

    # 2. Логин и получение JWT
    login_data = {
        "phone_number": "998901234567",
        "password": "test123"
    }
    response = requests.post(f"{BASE_URL}/login/", json=login_data)
    assert response.status_code == 200
    token = response.json()["access"]
    print("✓ Login successful, JWT token received")

    # 3. Подключение к WebSocket Main Server
    ws_main = websocket.WebSocket()
    ws_main.connect(f"{MAIN_WS_URL}/ws?token={token}")
    print("✓ Connected to Main Server WebSocket")

    # 4. Подключение к WebSocket Location Server
    ws_location = websocket.WebSocket()
    ws_location.connect(f"{LOCATION_WS_URL}/ws?token={token}")
    print("✓ Connected to Location Server WebSocket")

    # 5. Отправка локации
    location_data = {
        "latitude": 41.2995,
        "longitude": 69.2401
    }
    ws_location.send(json.dumps(location_data))
    print("✓ Location data sent")

    # 6. Проверка получения заказа
    time.sleep(2) # Ждем немного
    result = ws_main.recv()
    print(f"Received from Main Server: {result}")

    ws_main.close()
    ws_location.close()

if __name__ == "__main__":
    test_integration()

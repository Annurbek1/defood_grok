import pika
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RabbitMQConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange_name = 'defood_exchange'
        # Обновляем маршрутизацию
        self.bindings = {
            'defood.orders.created': 'orders_queue',
            'defood.users.created': 'users_queue'
        }

    def connect(self):
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host='localhost',
                    port=5672,
                    credentials=pika.PlainCredentials('guest', 'guest'),
                    heartbeat=600,
                    connection_attempts=3
                )
            )
            self.channel = self.connection.channel()
            self.setup_exchange()
            return True
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            return False

    def setup_exchange(self):
        # Объявляем exchange
        self.channel.exchange_declare(
            exchange=self.exchange_name,
            exchange_type='topic',
            durable=True
        )

        # Объявляем очереди и привязываем их к exchange
        for routing_key, queue_name in self.bindings.items():
            self.channel.queue_declare(queue=queue_name, durable=True)
            self.channel.queue_bind(
                exchange=self.exchange_name,
                queue=queue_name,
                routing_key=routing_key  # Используем точный routing key
            )
            logger.info(f"Declared queue {queue_name} with routing key {routing_key}")

    def process_message(self, ch, method, properties, body):
        try:
            data = json.loads(body)
            routing_key = method.routing_key
            logger.info(f"""
            ====== New Message ======
            Routing Key: {routing_key}
            Queue: {self.bindings.get(routing_key)}
            Data: {data}
            ======================
            """)
            
            if 'orders' in routing_key:
                self.handle_order(data)
            elif 'users' in routing_key:
                self.handle_user(data)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag)

    def handle_order(self, data):
        try:
            order_id = data.get('order_id')
            event_type = data.get('event_type')
            timestamp = data.get('timestamp')
            
            logger.info(f"""
            ====== New Order Event ======
            Order ID: {order_id}
            Event Type: {event_type}
            Timestamp: {timestamp}
            ============================
            """)
        except Exception as e:
            logger.error(f"Error processing order: {e}")

    def handle_user(self, data):
        try:
            user_id = data.get('user_id')
            logger.info(f"""
            ====== New User Event ======
            User ID: {user_id}
            User Data: {data}
            ==========================
            """)
        except Exception as e:
            logger.error(f"Error processing user: {e}")

    def start_consuming(self):
        try:
            if not self.connect():
                return

            self.channel.basic_qos(prefetch_count=1)

            # Подписываемся на очереди
            for queue_name in self.bindings.values():
                self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=self.process_message
                )
                logger.info(f"Started consuming from queue: {queue_name}")

            logger.info('Started consuming messages. Press CTRL+C to exit.')
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
        except Exception as e:
            logger.error(f"Consumer error: {str(e)}")
        finally:
            if self.connection and not self.connection.is_closed:
                self.connection.close()

if __name__ == '__main__':
    consumer = RabbitMQConsumer()
    consumer.start_consuming()
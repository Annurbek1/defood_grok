from celery import shared_task
from datetime import datetime
import pika
import json
import logging
import time
from celery.exceptions import MaxRetriesExceededError
from .models import Order

logger = logging.getLogger(__name__)

class RabbitMQPublisher:
    def __init__(self, max_retries=5, retry_delay=5):
        self.exchange_name = 'defood_exchange'
        self.connection = None
        self.channel = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def connect(self):
        retries = 0
        while retries < self.max_retries:
            try:
                if not self.connection or self.connection.is_closed:
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
                    self.channel.exchange_declare(
                        exchange=self.exchange_name,
                        exchange_type='topic',
                        durable=True
                    )
                    return True
            except pika.exceptions.AMQPConnectionError as e:
                retries += 1
                if retries == self.max_retries:
                    logger.error(f"Failed to connect to RabbitMQ after {self.max_retries} attempts")
                    raise
                logger.warning(f"RabbitMQ connection attempt {retries} failed, retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
        return False

    def publish(self, routing_key, message):
        try:
            connected = self.connect()
            if not connected:
                raise Exception("Failed to establish RabbitMQ connection")
                
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            raise
        finally:
            if self.connection and not self.connection.is_closed:
                self.connection.close()

@shared_task(name='models.tasks.send_order_to_queue')
def send_order_to_queue(order_id):
    try:
        # Получаем данные заказа
        order = Order.objects.get(id=order_id)
        message = {
            'order_id': str(order.id),
            'event_type': 'order_created',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'user_id': str(order.user.id),
                'restaurant_id': str(order.restaurant.id),
                'total_amount': str(order.total_amount),
                'status': order.status,
                'items': [{
                    'menu_item_id': str(item.menu_item.id),
                    'quantity': item.quantity,
                    'price': str(item.price_at_time)
                } for item in order.items.all()]
            }
        }
        
        publisher = RabbitMQPublisher()
        publisher.publish('defood.orders.created', message)
        logger.info(f"Order message sent to queue: {message}")
        return message
    except Exception as e:
        logger.error(f"Failed to send order to queue: {e}")
        raise

@shared_task(name='models.tasks.send_user_data_to_queue')
def send_user_data_to_queue(user_data):
    try:
        message = {
            'event_type': 'user_created',
            'timestamp': datetime.now().isoformat(),
            'data': user_data
        }
        
        publisher = RabbitMQPublisher()
        publisher.publish('defood.users.created', message)
        logger.info(f"User message sent to queue: {message}")
        return message
    except Exception as e:
        logger.error(f"Failed to send user data to queue: {e}")
        raise

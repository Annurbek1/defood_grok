from celery import shared_task
from datetime import datetime
import pika
import json
import logging
import time
from celery.exceptions import MaxRetriesExceededError
from django.db import transaction
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
        last_error = None
        while retries < self.max_retries:
            try:
                if not self.connection or self.connection.is_closed:
                    self.connection = pika.BlockingConnection(
                        pika.ConnectionParameters(
                            host='localhost',
                            port=5672,
                            credentials=pika.PlainCredentials('guest', 'guest'),
                            heartbeat=600,
                            connection_attempts=3,
                            socket_timeout=5
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
                last_error = e
                retries += 1
                if retries < self.max_retries:
                    logger.warning(f"RabbitMQ connection attempt {retries} failed, retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
        
        logger.error(f"Failed to connect to RabbitMQ after {self.max_retries} attempts: {last_error}")
        return False

    def publish(self, routing_key, message, max_retries=3):
        for attempt in range(max_retries):
            try:
                if self.connect():
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
                raise Exception("Failed to establish connection")
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Publish attempt {attempt + 1} failed, retrying...")
                time.sleep(2)
        return False

@shared_task(bind=True, max_retries=3)
def send_order_to_queue(self, order_id):
    try:
        with transaction.atomic():
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
            if not publisher.publish('defood.orders.created', message):
                order.delete()
                raise Exception("Failed to publish order to queue")
                
            logger.info(f"Order message sent to queue: {message}")
            return message
    except Exception as e:
        logger.error(f"Failed to process order {order_id}: {str(e)}")
        try:
            order = Order.objects.get(id=order_id)
            order.delete()
        except:
            pass
        raise self.retry(exc=e, countdown=5)

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

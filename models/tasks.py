from celery import shared_task
import pika
import json
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def send_user_data_to_queue(self, data):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()

        # Выбираем очередь в зависимости от типа данных
        queue_name = 'order_data_queue' if 'order_id' in data else 'user_data_queue'
        channel.queue_declare(queue=queue_name, durable=True)

        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(data),
            properties=pika.BasicProperties(
                delivery_mode=2,  # делаем сообщение постоянным
            )
        )

        connection.close()
        logger.info(f"Data sent to RabbitMQ queue {queue_name}: {data}")

    except Exception as e:
        logger.error(f"RabbitMQ Error: {e}")
        raise self.retry(exc=e)


@shared_task
def process_user_data_from_queue():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()

        channel.queue_declare(queue='user_data_queue', durable=True)

        def callback(ch, method, properties, body):
            try:
                user_data = json.loads(body)
                logger.info(f"Received user data from RabbitMQ: {user_data}")

                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                logger.error(f"Error processing message: {e}")

        channel.basic_consume(queue='user_data_queue', on_message_callback=callback)
        logger.info('Waiting for messages in user_data_queue...')
        channel.start_consuming()

    except Exception as e:
        logger.error(f"RabbitMQ Error: {e}")

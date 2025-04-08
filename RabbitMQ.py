import pika
import json
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def handle_order_data(data):
    """Обработка данных заказа"""
    try:
        if 'order_id' in data:
            logger.info(f"Обработка заказа #{data['order_id']}")
            logger.info(f"Данные заказа: {json.dumps(data, indent=2, ensure_ascii=False)}")
        elif 'user_id' in data:
            logger.info(f"Обработка данных пользователя #{data['user_id']}")
            logger.info(f"Данные пользователя: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except Exception as e:
        logger.error(f"Ошибка при обработке данных: {str(e)}")

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        logger.info(f"Получено новое сообщение из очереди")
        handle_order_data(data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON: {str(e)}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}")

def start_consumer():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()

        channel.queue_declare(queue='user_data_queue', durable=True)
        channel.queue_declare(queue='order_data_queue', durable=True)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue='user_data_queue',
            on_message_callback=callback
        )
        channel.basic_consume(
            queue='order_data_queue',
            on_message_callback=callback
        )

        logger.info('Ожидание сообщений. Для выхода нажмите CTRL+C')
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError:
        logger.error("Ошибка подключения к RabbitMQ. Проверьте, запущен ли сервер.")
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения работы")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}")
    finally:
        try:
            connection.close()
        except:
            pass

if __name__ == "__main__":
    start_consumer()
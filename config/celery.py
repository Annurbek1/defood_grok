import os
from celery import Celery
from kombu import Exchange, Queue

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('defood_startapp')

# Настройка обмена сообщениями
defood_exchange = Exchange('defood_exchange', type='topic', durable=True)

# Определяем очереди
app.conf.task_queues = (
    Queue('orders_queue', defood_exchange, routing_key='defood.orders.created'),
    Queue('users_queue', defood_exchange, routing_key='defood.users.created'),
)

# Настройка маршрутизации задач
app.conf.task_routes = {
    'models.tasks.send_order_to_queue': {
        'queue': 'orders_queue',
        'routing_key': 'defood.orders.created'
    },
    'models.tasks.send_user_data_to_queue': {
        'queue': 'users_queue',
        'routing_key': 'defood.users.created'
    },
}

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tashkent',
    enable_utc=True,
)

app.autodiscover_tasks()

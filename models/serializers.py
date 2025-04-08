from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Order, OrderItem, MenuItem, Address, Restaurant
from .tasks import send_user_data_to_queue

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('phone_number', 'first_name', 'last_name')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('phone_number', 'password', 'first_name', 'last_name')

    def create(self, validated_data):
        user = User.objects.create_user(
            phone_number=validated_data["phone_number"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            password=validated_data["password"]
        )

        # Celery queue'ga yuborish
        send_user_data_to_queue.delay({
            "id": user.id,
            "phone_number": user.phone_number,
            "first_name": user.first_name,
            "last_name": user.last_name,
        })

        return user


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = User.objects.filter(phone_number=data['phone_number']).first()
        if user and user.check_password(data['password']):
            refresh = RefreshToken.for_user(user)

            login_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            send_user_data_to_queue.delay({
                "id": user.id,
                "phone_number": user.phone_number,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "login_time": login_time
            })

            return {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }

        raise serializers.ValidationError("Telefon raqami yoki parol noto‘g‘ri")

class OrderItemSerializer(serializers.ModelSerializer):
    menu_item = serializers.PrimaryKeyRelatedField(queryset=MenuItem.objects.all())
    price_at_time = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'menu_item', 'quantity', 'price_at_time']

    def create(self, validated_data):
        # Исправляем обработку menu_item
        menu_item = MenuItem.objects.get(id=validated_data['menu_item'].id)
        validated_data['price_at_time'] = menu_item.price
        return OrderItem.objects.create(menu_item=menu_item, **validated_data)

class OrderSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    restaurant = serializers.PrimaryKeyRelatedField(queryset=Restaurant.objects.all())
    items = OrderItemSerializer(many=True, required=True)
    delivery_address = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all(), required=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'restaurant', 'items', 'delivery_address', 'total_amount', 'status', 'created_at', 'updated_at']
        extra_kwargs = {
            'total_amount': {'required': False},
            'status': {'default': 'PENDING'},
            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
        }

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)

        total_amount = 0
        for item_data in items_data:
            menu_item = item_data.pop('menu_item')  # menu_item уже объект
            quantity = item_data.pop('quantity', 1)
            price = menu_item.price
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=quantity,
                price_at_time=price
            )
            total_amount += price * quantity

        order.total_amount = total_amount
        order.save()

        # Отправка данных заказа в RabbitMQ
        order_data = {
            'order_id': order.id,
            'user_id': order.user.id,
            'restaurant_id': order.restaurant.id,
            'total_amount': str(order.total_amount),
            'status': order.status,
            'created_at': order.created_at.isoformat(),
            'items': [{
                'menu_item_id': item.menu_item.id,
                'quantity': item.quantity,
                'price': str(item.price_at_time)
            } for item in order.items.all()]
        }
        send_user_data_to_queue.delay(order_data)

        return order

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['street', 'city', 'postal_code']

class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'address', 'phone', 'description', 'delivery_radius', 'min_order_amount', 'working_hours', 'created_at']
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation

class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = '__all__'
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Order, OrderItem, MenuItem, Address, Restaurant, CustomUser, Courier
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
    phone_number = serializers.CharField()  # Изменили с phone на phone_number
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = CustomUser.objects.filter(phone_number=data['phone_number']).first()
        if user and user.check_password(data['password']):
            refresh = RefreshToken.for_user(user)
            token_data = {'user_id': user.id}
            try:
                courier = Courier.objects.get(user=user)
                token_data['courier_id'] = courier.id
            except Courier.DoesNotExist:
                pass
            refresh.payload.update(token_data)
            return {'token': str(refresh.access_token)}
        raise serializers.ValidationError("Invalid phone number or password")


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item = serializers.PrimaryKeyRelatedField(queryset=MenuItem.objects.all())
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = OrderItem
        fields = ['menu_item', 'quantity']


class OrderCreateSerializer(serializers.ModelSerializer):
    type = serializers.CharField(default='food')
    
    class Meta:
        model = Order
        fields = ['type', 'restaurant', 'address', 'details']  # Changed from delivery_address to address

    def validate(self, data):
        user = self.context['request'].user
        if data['address'].user != user:  # Changed from delivery_address
            raise serializers.ValidationError("Invalid address")
        return data


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    
    class Meta:
        model = Order
        fields = ['id', 'restaurant', 'address', 'items', 'total_amount', 'status', 'details']

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Необходимо указать хотя бы один товар")
        return value

    def create(self, validated_data):
        try:
            items_data = validated_data.pop('items')
            # Создаем заказ с пользователем из контекста и details
            order = Order.objects.create(
                user=self.context['request'].user,
                status='PENDING',
                details={
                    'items': [{
                        'menu_item_id': str(item['menu_item'].id),
                        'name': item['menu_item'].name,
                        'quantity': item['quantity'],
                        'price': str(item['menu_item'].price)
                    } for item in items_data],
                },
                **validated_data
            )

            # Создаем элементы заказа и считаем общую сумму
            total_amount = 0
            for item_data in items_data:
                menu_item = item_data['menu_item']
                quantity = item_data['quantity']
                price_at_time = menu_item.price
                
                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    price_at_time=price_at_time
                )
                total_amount += price_at_time * quantity

            # Обновляем детали заказа с общей суммой
            order.details.update({
                'total_amount': str(total_amount),
                'address': {
                    'street': order.address.street,
                    'house': order.address.house_number,
                    'apartment': order.address.apartment,
                    'floor': order.address.floor,
                    'entrance': order.address.entrance,
                },
                'restaurant': {
                    'name': order.restaurant.name,
                    'address': order.restaurant.address,
                    'phone': order.restaurant.phone
                },
                'created_at': order.created_at.isoformat()
            })
            
            # Сохраняем заказ с обновленными деталями и суммой
            order.total_amount = total_amount
            order.save()
            
            return order
            
        except Exception as e:
            if 'order' in locals():
                order.delete()
            logger.error(f"Error creating order: {str(e)}")
            raise serializers.ValidationError(f"Ошибка при создании заказа: {str(e)}")


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
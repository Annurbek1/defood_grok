import logging
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, views, status
from rest_framework import viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes, schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.schemas import AutoSchema
from rest_framework import serializers
from rest_framework.viewsets import ModelViewSet
from .models import Restaurant, Address, MenuItem, Order, Courier
from .serializers import (
    RestaurantSerializer,
    AddressSerializer,
    MenuItemSerializer,
    OrderSerializer,
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    OrderCreateSerializer
)
from .tasks import send_user_data_to_queue, send_order_to_queue

from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LoginView(views.APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Вход пользователя в систему",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phone_number', 'password'],
            properties={
                'phone_number': openapi.Schema(type=openapi.TYPE_STRING, description="Номер телефона"),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description="Пароль"),
            },
        ),
        responses={
            200: openapi.Response('Успешный вход', LoginSerializer),
            401: 'Неверные учетные данные',
        }
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @swagger_auto_schema(
        operation_description="Создание нового заказа",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['restaurant', 'address', 'items'],
            properties={
                'restaurant': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID ресторана"),
                'address': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID адреса доставки"),
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'menu_item': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID позиции меню"),
                            'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, description="Количество", minimum=1)
                        },
                        required=['menu_item', 'quantity']
                    )
                )
            }
        ),
        responses={
            201: OrderSerializer,
            400: 'Неверный запрос',
            401: 'Не авторизован'
        }
    )
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            order = serializer.save()
            
            # Немедленно отправляем задачу
            task_result = send_order_to_queue.apply_async(
                args=[str(order.id)],
                routing_key='defood.orders.created'
            )
            logger.info(f"Task sent: {task_result.id}")
            
            return Response({
                'status': 'success',
                'message': 'Заказ успешно создан',
                'order': OrderSerializer(order).data,
                'task_id': task_result.id
            }, status=status.HTTP_201_CREATED)
            
        except serializers.ValidationError as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Ошибка при создании заказа: {str(e)}")
            return Response({
                'status': 'error',
                'message': 'Произошла ошибка при создании заказа'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        operation_description="Get list of orders",
        responses={200: OrderSerializer(many=True)}
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Order.objects.none()
        if self.request.user.is_authenticated:
            return Order.objects.filter(user=self.request.user)
        return Order.objects.none()


class CourierActivateView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            courier = Courier.objects.get(user=request.user)
            courier.status = 'active'
            courier.save()
            return Response({'message': 'Courier activated'})
        except Courier.DoesNotExist:
            return Response({'error': 'Not a courier'}, status=status.HTTP_403_FORBIDDEN)


class CustomAutoSchema(AutoSchema):
    def get_operation_id(self, path, method):
        return f"{method.lower()}_{path}"


@api_view(['GET'])
@schema(CustomAutoSchema())
@permission_classes([AllowAny])
def internal_order_detail(request, id):
    order = get_object_or_404(Order, id=id)
    return Response({
        'order_id': str(order.id),
        'restaurant_latitude': float(order.restaurant.latitude),
        'restaurant_longitude': float(order.restaurant.longitude),
        'delivery_latitude': float(order.address.latitude),
        'delivery_longitude': float(order.address.longitude),
        'details': order.details  # Теперь используем сохраненные details
    })


@api_view(['POST'])
@schema(CustomAutoSchema())
@permission_classes([AllowAny])
def internal_order_complete(request, id):
    order = get_object_or_404(Order, id=id)
    order.status = request.data.get('status', 'delivered')
    order.save()
    return Response({'message': 'Order updated'})


class RestaurantViewSet(ModelViewSet):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer


class AddressViewSet(ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer


class MenuItemViewSet(ModelViewSet):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
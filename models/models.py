from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
import config.settings as settings
from django.utils import timezone

# Менеджер для CustomUser
class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Phone number is required")
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(phone_number, password, **extra_fields)

# Пользователь
class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(
        max_length=15, 
        unique=True, 
        default="default_phone",  # Adding default value
        help_text="Format: 998XXXXXXXXX"
    )
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)  # Перенос из UserProfile
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    objects = CustomUserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        indexes = [
            models.Index(fields=['phone_number']),  # Ускорение поиска по номеру
        ]

    def __str__(self):
        return self.phone_number

# Адрес клиента
class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    street = models.CharField(max_length=255)
    house_number = models.CharField(max_length=50)
    apartment = models.CharField(max_length=50, blank=True)
    floor = models.CharField(max_length=10, blank=True)
    entrance = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=False, default=41.2995)  # Обязательное
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=False, default=69.2401)  # Обязательное
    is_default = models.BooleanField(default=False)
    address_label = models.CharField(max_length=50, choices=[
        ('HOME', 'Home'),
        ('WORK', 'Work'),
        ('OTHER', 'Other')
    ])

    class Meta:
        indexes = [
            models.Index(fields=['latitude', 'longitude']),  # Для geospatial-запросов
            models.Index(fields=['user']),  # Ускорение фильтрации по пользователю
        ]

# Ресторан
class Restaurant(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    address = models.TextField()  # Для совместимости
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=False, default=41.2995)  # Обязательное
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=False, default=69.2401)  # Обязательное
    phone = models.CharField(max_length=15)
    rating = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)
    delivery_radius = models.FloatField(help_text="Delivery radius in kilometers")
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    working_hours = models.JSONField()  # Формат: {"monday": "09:00-21:00", ...}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['latitude', 'longitude']),  # Для логистики
            models.Index(fields=['is_active']),  # Ускорение фильтрации активных ресторанов
        ]

# Элемент меню
class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_items')
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    preparation_time = models.IntegerField(
        help_text="Preparation time in minutes",
        validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )

    class Meta:
        indexes = [
            models.Index(fields=['restaurant', 'is_available']),  # Ускорение фильтрации по ресторану
        ]

# Заказ
class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT)
    address = models.ForeignKey(Address, on_delete=models.PROTECT)  # Changed from delivery_address
    courier = models.ForeignKey('Courier', on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    details = models.JSONField(default=dict)  # Added missing field
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('PREPARING', 'Preparing'),
        ('DELIVERING', 'Delivering'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ], default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),  # Ускорение фильтрации по пользователю
            models.Index(fields=['restaurant']),  # Ускорение по ресторану
            models.Index(fields=['courier']),  # Ускорение по курьеру
            models.Index(fields=['status']),  # Ускорение фильтрации по статусу
        ]

# Элемент заказа
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        indexes = [
            models.Index(fields=['order']),  # Ускорение фильтрации по заказу
        ]

# Курьер
class Courier(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vehicle_type = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    average_rating = models.FloatField(default=0.0)

    class Meta:
        indexes = [
            models.Index(fields=['is_active']),  # Ускорение фильтрации активных курьеров
        ]
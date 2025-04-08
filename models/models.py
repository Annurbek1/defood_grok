import uuid
import config.settings as settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    street = models.CharField(max_length=255)
    house_number = models.CharField(max_length=50)
    apartment = models.CharField(max_length=50, blank=True)
    floor = models.CharField(max_length=10, blank=True)
    entrance = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True)
    is_default = models.BooleanField(default=False)
    address_label = models.CharField(max_length=50, choices=[
        ('HOME', 'Home'),
        ('WORK', 'Work'),
        ('OTHER', 'Other')
    ])
    comment = models.TextField(blank=True)

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)

class Restaurant(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    address = models.TextField()  # Оставляем как TextField для обратной совместимости
    # Или можно добавить связь с моделью Address, если нужно:
    # address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True)
    phone = models.CharField(max_length=15)
    rating = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)
    delivery_radius = models.FloatField(help_text="Delivery radius in kilometers")
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    working_hours = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='menu_items/', null=True, blank=True)
    is_available = models.BooleanField(default=True)
    preparation_time = models.IntegerField(
        help_text="Preparation time in minutes",
        validators=[MinValueValidator(0), MaxValueValidator(1440)]  # Максимум 24 часа
    )

class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT)
    delivery_address = models.ForeignKey(Address, on_delete=models.PROTECT)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
    ], default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_at_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=False,
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    special_instructions = models.TextField(blank=True)

class Courier(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vehicle_type = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    current_location = models.JSONField(null=True)
    average_rating = models.FloatField(default=0.0)

class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    restaurant_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    courier_rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Promotion(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField()
    discount_percentage = models.PositiveIntegerField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

class PaymentMethod(models.Model):
    PAYMENT_TYPES = [
        ('CARD', 'Credit/Debit Card'),
        ('CASH', 'Cash on Delivery'),
        ('APPLE_PAY', 'Apple Pay'),
        ('GOOGLE_PAY', 'Google Pay'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    is_default = models.BooleanField(default=False)
    card_last_four = models.CharField(max_length=4, blank=True)
    card_expiry = models.CharField(max_length=7, blank=True)
    card_brand = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

class Payment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
        ('CANCELLED', 'Cancelled'),
    ]

    order = models.ForeignKey('Order', on_delete=models.PROTECT)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_id = models.CharField(max_length=255, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True)

class Refund(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True)
    refund_transaction_id = models.CharField(max_length=255, unique=True, null=True)

class ReferralCode(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=20, unique=True)
    times_used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.code:
            # Generate unique referral code if not set
            self.code = f"REF{self.user.id}{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

class ReferralRelationship(models.Model):
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referrals_made')
    referred = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referred_by')
    created_at = models.DateTimeField(auto_now_add=True)
    referral_code_used = models.ForeignKey(ReferralCode, on_delete=models.SET_NULL, null=True)

class ReferralReward(models.Model):
    REWARD_TYPE_CHOICES = [
        ('DISCOUNT', 'Discount'),
        ('CASHBACK', 'Cashback'),
        ('FREE_DELIVERY', 'Free Delivery'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('AVAILABLE', 'Available'),
        ('USED', 'Used'),
        ('EXPIRED', 'Expired'),
    ]

    relationship = models.ForeignKey(ReferralRelationship, on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reward_type = models.CharField(max_length=20, choices=REWARD_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    expires_at = models.DateTimeField(null=True)
    used_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    usage_order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)

class ReferralProgram(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    referrer_reward_amount = models.DecimalField(max_digits=10, decimal_places=2)
    referred_reward_amount = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reward_expiry_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.phone_number if self.phone_number else self.email
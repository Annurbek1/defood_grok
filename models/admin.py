from django.contrib import admin
from .models import (
    UserProfile, Restaurant, Category, MenuItem, 
    Order, OrderItem, Courier, Review, Promotion,
    Address, PaymentMethod, Payment, Refund,
    ReferralCode, ReferralRelationship, ReferralReward, ReferralProgram
)

admin.site.register(UserProfile)
admin.site.register(Restaurant)
admin.site.register(Category)
admin.site.register(MenuItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Courier)
admin.site.register(Review)
admin.site.register(Promotion)
admin.site.register(Address)
admin.site.register(PaymentMethod)
admin.site.register(Payment)
admin.site.register(Refund)
admin.site.register(ReferralCode)
admin.site.register(ReferralRelationship)
admin.site.register(ReferralReward)
admin.site.register(ReferralProgram)

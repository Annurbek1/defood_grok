from django.contrib import admin
from .models import (
    Restaurant, MenuItem, 
    Order, OrderItem, Courier,
    Address
)

admin.site.register(Restaurant)
admin.site.register(MenuItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Courier)
admin.site.register(Address)
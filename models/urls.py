from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import RegisterView, LoginView, ProfileView, OrderViewSet
from .views import RestaurantViewSet, AddressViewSet, MenuItemViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')  # Управление заказами
router.register(r'restaurants', RestaurantViewSet, basename='restaurant')  # Управление ресторанами
router.register(r'addresses', AddressViewSet, basename='address')  # Управление адресами
router.register(r'menu-items', MenuItemViewSet, basename='menuitem')  # Управление меню

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),  # Регистрация
    path('login/', LoginView.as_view(), name='login'),  # Авторизация
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # Обновление токена
    path('profile/', ProfileView.as_view(), name='profile'),  # Профиль пользователя
    path('api/', include(router.urls)),  # Подключение маршрутов API
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
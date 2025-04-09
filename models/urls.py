from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, LoginView, ProfileView,
    OrderViewSet, RestaurantViewSet, AddressViewSet, MenuItemViewSet,
    internal_order_detail, internal_order_complete, health_check,
)

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'restaurants', RestaurantViewSet, basename='restaurant')
router.register(r'addresses', AddressViewSet, basename='address')
router.register(r'menu-items', MenuItemViewSet, basename='menuitem')

urlpatterns = [
    # Auth endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),

    # API endpoints (using router)
    path('api/', include(router.urls)),

    # Internal API endpoints
    path('internal/order/<str:id>/', internal_order_detail, name='internal-order-detail'),
    path('internal/order/<str:id>/complete/', internal_order_complete, name='internal-order-complete'),

    # Health check endpoint
    path('health/', health_check, name='health-check'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
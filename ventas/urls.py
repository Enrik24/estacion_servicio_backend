from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SurtidorViewSet, TurnoViewSet, ClienteViewSet, VentaViewSet

router = DefaultRouter()
router.register(r'surtidores', SurtidorViewSet)
router.register(r'turnos', TurnoViewSet)
router.register(r'clientes', ClienteViewSet)
router.register(r'ventas', VentaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IslaViewSet, LadoViewSet, TipoCombustibleViewSet, TurnoViewSet, ClienteViewSet, VentaViewSet

router = DefaultRouter()
router.register(r'islas', IslaViewSet)
router.register(r'lados', LadoViewSet)
router.register(r'tipos-combustible', TipoCombustibleViewSet)
router.register(r'turnos', TurnoViewSet)
router.register(r'clientes', ClienteViewSet)
router.register(r'ventas', VentaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
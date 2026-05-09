from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SucursalViewSet,IslaViewSet, LadoViewSet, TipoCombustibleViewSet, TurnoViewSet, ClienteViewSet, VehiculoViewSet, VentaViewSet

router = DefaultRouter()
router.register(r'islas', IslaViewSet)
router.register(r'lados', LadoViewSet)
router.register(r'tipos-combustible', TipoCombustibleViewSet)
router.register(r'turnos', TurnoViewSet)
router.register(r'ventas-clientes', ClienteViewSet, basename='ventas-clientes')
router.register(r'ventas', VentaViewSet)
router.register(r'sucursales', SucursalViewSet)
router.register(r'vehiculos', VehiculoViewSet, basename='vehiculos')
urlpatterns = [
    path('', include(router.urls)),
]

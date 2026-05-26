"""URLs para la aplicación de ventas.

Define las rutas para acceder a todos los ViewSets de ventas,
incluyendo islas, lados, combustibles, turnos, clientes, vehículos, sucursales y consolidación.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ConsolidacionCajaViewSet, SucursalViewSet, IslaViewSet, LadoViewSet,
    TipoCombustibleViewSet, TurnoViewSet, ClienteViewSet, VentaViewSet, VehiculoViewSet,
    PreciosCombustibleView, ComprasViewSet
)

router = DefaultRouter()

# ViewSets para gestión de infraestructura
router.register(r'islas', IslaViewSet, basename='isla')
router.register(r'lados', LadoViewSet, basename='lado')

router.register(r'tipos-combustible', TipoCombustibleViewSet, basename='tipo-combustible')
router.register(r'sucursales', SucursalViewSet, basename='sucursal')

# ViewSets para gestión de operaciones
router.register(r'turnos', TurnoViewSet, basename='turno')
router.register(r'clientes', ClienteViewSet, basename='cliente')

router.register(r'clientes-ventas', ClienteViewSet, basename='cliente-ventas')
router.register(r'ventas', VentaViewSet, basename='venta')
router.register(r'vehiculos', VehiculoViewSet, basename='vehiculo')
router.register(r'compras', ComprasViewSet, basename='compra')

# ViewSet para reportes y consolidación
router.register(r'consolidacion', ConsolidacionCajaViewSet, basename='consolidacion-caja')

urlpatterns = [

    path('precios-combustible/', PreciosCombustibleView.as_view()),
    path('', include(router.urls)),
]

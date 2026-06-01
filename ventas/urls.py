"""URLs para la aplicación de ventas.

Define las rutas para acceder a todos los ViewSets de ventas,
incluyendo islas, lados, combustibles, turnos, clientes, vehículos, sucursales y consolidación.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ConsolidacionCajaViewSet, SucursalViewSet, IslaViewSet, LadoViewSet,
    TipoCombustibleViewSet, TurnoViewSet, ClienteViewSet, VentaViewSet, VehiculoViewSet,
    PreciosCombustibleView, ComprasViewSet, CrearPrepagoAPIView, StripeWebhookAPIView, MisOrdenesPrepagoAPIView,
    DescargarComprobantePDFAPIView, ValidarPrepagoAPIView, DespacharPrepagoAPIView,
    OrdenesPrepagoOperadorAPIView, CompletarPerfilClienteAPIView, SucursalesPublicasAPIView
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

    # Público — landing page
    path('sucursales-publicas/', SucursalesPublicasAPIView.as_view(), name='sucursales-publicas'),

    path('perfil/completar/', CompletarPerfilClienteAPIView.as_view(), name='perfil-completar'),
    path('precios-combustible/', PreciosCombustibleView.as_view()),
    path('prepago/crear/', CrearPrepagoAPIView.as_view(), name='prepago-crear'),
    path('prepago/webhook/', StripeWebhookAPIView.as_view(), name='prepago-webhook'),
    path('prepago/mis-ordenes/', MisOrdenesPrepagoAPIView.as_view(), name='prepago-mis-ordenes'),
    path('prepago/<int:orden_id>/pdf/', DescargarComprobantePDFAPIView.as_view(), name='prepago-pdf'),
    path('prepago/validar/<str:numero_orden>/', ValidarPrepagoAPIView.as_view(), name='prepago-validar'),
    path('prepago/despachar/<str:numero_orden>/', DespacharPrepagoAPIView.as_view(), name='prepago-despachar'),
    path('prepago/ordenes-pendientes/', OrdenesPrepagoOperadorAPIView.as_view(), name='prepago-ordenes-pendientes'),
    path('', include(router.urls)),
]

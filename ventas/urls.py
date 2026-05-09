from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConsolidacionCajaViewSet, SucursalViewSet,IslaViewSet, LadoViewSet, TipoCombustibleViewSet, TurnoViewSet, ClienteViewSet, VentaViewSet

router = DefaultRouter()
router.register(r'islas', IslaViewSet)
router.register(r'lados', LadoViewSet)
router.register(r'tipos-combustible', TipoCombustibleViewSet)
router.register(r'turnos', TurnoViewSet)
router.register(r'clientes', ClienteViewSet)
router.register(r'ventas', VentaViewSet)
router.register(r'sucursales', SucursalViewSet)
# Registra el ViewSet de consolidación de caja en la ruta 'consolidacion'
# basename='consolidacion-caja' define el nombre para las URLs generadas (ej: consolidacion-caja-list, consolidacion-caja-detail)
router.register(r'consolidacion', ConsolidacionCajaViewSet, basename='consolidacion-caja')
urlpatterns = [
    path('', include(router.urls)),
]
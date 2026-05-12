"""URLs para la aplicación de reportes.

Define las rutas para acceder a los diferentes reportes disponibles.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ReportesViewSet

router = DefaultRouter()
router.register(r'', ReportesViewSet, basename='reportes')

urlpatterns = [
    path('', ReportesViewSet.as_view({'get': 'ventas'}), name='reportes-ventas'),
    path('ventas/', ReportesViewSet.as_view({'get': 'ventas'}), name='reportes-ventas'),
    path('turnos/', ReportesViewSet.as_view({'get': 'turnos'}), name='reportes-turnos'),
    path('clientes/', ReportesViewSet.as_view({'get': 'clientes'}), name='reportes-clientes'),
    path('sucursales/', ReportesViewSet.as_view({'get': 'sucursales'}), name='reportes-sucursales'),
    path('islas/', ReportesViewSet.as_view({'get': 'islas'}), name='reportes-islas'),
]

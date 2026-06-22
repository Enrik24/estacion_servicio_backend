from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TanqueViewSet, DescargaViewSet, OrdenCompraViewSet, PagoProveedorViewSet

router = DefaultRouter()
router.register(r'tanques', TanqueViewSet, basename='tanques')
router.register(r'descargas', DescargaViewSet, basename='descargas')
router.register(r'ordenes-compra', OrdenCompraViewSet, basename='ordenes-compra')
router.register(r'pagos-proveedores', PagoProveedorViewSet, basename='pagos-proveedores')

urlpatterns = [
    path('', include(router.urls)),
]
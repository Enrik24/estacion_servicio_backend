from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UsuarioViewSet, RolViewSet, PermisoViewSet, ClienteViewSet,
    LimiteConsumoViewSet, login_view, logout_view, asignar_roles
)
from .predicciones_views import PrediccionConsumoAPIView

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet)
router.register(r'clientes', ClienteViewSet, basename='clientes')
router.register(r'roles', RolViewSet)
router.register(r'permisos', PermisoViewSet)
router.register(r'limites-consumo', LimiteConsumoViewSet, basename='limites-consumo')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('usuarios/<int:pk>/asignar-roles/', asignar_roles, name='asignar-roles'),
    path('predicciones-consumo/', PrediccionConsumoAPIView.as_view(), name='predicciones-consumo'),
]

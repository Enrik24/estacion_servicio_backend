from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UsuarioViewSet, RolViewSet, PermisoViewSet,
    login_view, logout_view, asignar_roles,
    request_password_reset, reset_password,
    register_view,
)


router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet)
router.register(r'roles', RolViewSet)
router.register(r'permisos', PermisoViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/register/', register_view, name='register'),
    path('auth/request-reset/', request_password_reset, name='request_reset'),
    path('auth/reset-password/<uuid:token>/', reset_password, name='reset_password'),
    path('usuarios/<int:pk>/asignar-roles/', asignar_roles, name='asignar-roles'),
]
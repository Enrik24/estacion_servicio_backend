from django.urls import path
from . import views

urlpatterns = [
    path('descargar/', views.descargar_backup, name='backup-descargar'),
    path('restaurar/', views.restaurar_backup, name='backup-restaurar'),
]
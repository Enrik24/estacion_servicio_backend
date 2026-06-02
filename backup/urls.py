from django.urls import path
from . import views

urlpatterns = [
    path('descargar/', views.descargar_backup, name='descargar_backup'),
    path('restaurar/', views.restaurar_backup, name='restaurar_backup'),
    path('listar/', views.listar_backups, name='listar_backups'),
    path('descargar-supabase/<str:nombre>/', views.descargar_backup_supabase, name='descargar_backup_supabase'),
]
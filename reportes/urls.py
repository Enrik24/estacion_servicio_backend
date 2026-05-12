from django.urls import path
from . import views

urlpatterns = [
    path('ventas/',      views.reporte_ventas,      name='reporte-ventas'),
    path('turnos/',      views.reporte_turnos,      name='reporte-turnos'),
    path('clientes/',    views.reporte_clientes,    name='reporte-clientes'),
    path('sucursales/',  views.reporte_sucursales,  name='reporte-sucursales'),
    path('islas/',       views.reporte_islas,       name='reporte-islas'),
    path('interpretar/', views.interpretar_comando, name='interpretar-comando'),
    path('email/',       views.enviar_reporte_email, name='enviar-reporte-email'),
]

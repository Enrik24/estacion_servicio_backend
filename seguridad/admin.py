from django.contrib import admin
from .models import Bitacora

@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario_email', 'accion', 'modulo_afectado', 'estado', 'fecha_hora']
    list_filter = ['accion', 'estado', 'modulo_afectado', 'fecha_hora']
    search_fields = ['usuario_email', 'descripcion', 'ip_address']
    readonly_fields = ('fecha_hora',)
    
    def has_change_permission(self, request, obj=None):
        return False
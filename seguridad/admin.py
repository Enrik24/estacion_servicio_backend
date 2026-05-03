from django.contrib import admin
from .models import Bitacora

@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ['id', 'accion', 'estado', 'usuario_email', 'ip_address', 'fecha_hora']
    list_filter = ['accion', 'estado', 'fecha_hora']
    search_fields = ['usuario_email', 'usuario_nombre', 'ip_address']
    readonly_fields = [f.name for f in Bitacora._meta.fields]
    ordering = ['-fecha_hora']
    
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
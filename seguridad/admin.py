from django.contrib import admin
from .models import Bitacora

@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ['id', 'accion', 'usuario_nombre', 'modulo_afectado', 'dispositivo', 'direccion_ip', 'creado_en']
    list_filter = ['accion', 'dispositivo', 'creado_en']
    search_fields = ['usuario_nombre', 'descripcion', 'direccion_ip']
    readonly_fields = [f.name for f in Bitacora._meta.fields]
    ordering = ['-creado_en']
    
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Usuario, Rol, Permiso

@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    list_display = ['id', 'email', 'nombre', 'is_active', 'is_staff', 'created_at']
    list_filter = ['is_active', 'is_staff', 'created_at']
    search_fields = ['email', 'nombre']
    ordering = ['-created_at']
    filter_horizontal = ['roles']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información personal', {'fields': ('nombre',)}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'roles')}),
        ('Auditoría', {'fields': ('created_by', 'updated_by', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'nombre', 'password1', 'password2')}),
    )
    
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre', 'created_at']
    search_fields = ['nombre']
    filter_horizontal = ['permisos']

@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ['id', 'codigo', 'nombre']
    search_fields = ['codigo', 'nombre']
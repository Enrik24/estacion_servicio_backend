from rest_framework import permissions

class HasPermiso(permissions.BasePermission):
    def __init__(self, permiso=None):
        self.permiso = permiso
    
    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        
        permiso_requerido = self.permiso or getattr(view, 'permiso_requerido', None)
        if not permiso_requerido:
            return True
        
        return request.user.tiene_permiso(permiso_requerido)
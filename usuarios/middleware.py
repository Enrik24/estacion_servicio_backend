from django.http import HttpResponseForbidden

class AdminAccessMiddleware:
    """
    Middleware que valida el acceso al panel admin.
    Solo permite acceso a:
    - Superusuarios (is_superuser=True)
    - Usuarios con is_staff=True Y permiso 'admin.acceso'
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Validar acceso al admin
        if request.path.startswith('/admin/'):
            if not self._user_can_access_admin(request.user):
                return HttpResponseForbidden(
                    'No tienes permisos para acceder al panel de administración.'
                )
        
        response = self.get_response(request)
        return response
    
    def _user_can_access_admin(self, user):
        """Valida si el usuario puede acceder al admin"""
        # Usuarios no autenticados no pueden acceder
        if not user.is_authenticated:
            return False
        
        # Superusuarios siempre pueden acceder
        if user.is_superuser:
            return True
        
        # Usuarios staff necesitan el permiso 'admin.acceso'
        if user.is_staff:
            return user.tiene_permiso('admin.acceso')
        
        return False

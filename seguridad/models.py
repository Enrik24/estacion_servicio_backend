from django.db import models
from usuarios.models import Usuario, Permiso  # Importar el modelo de usuario para la relación en Bitacora

class Bitacora(models.Model):
    ACCIONES = [
        ('LOGIN', 'Inicio de sesión'),
        ('LOGOUT', 'Cierre de sesión'),
        ('CREAR', 'Creación'),
        ('EDITAR', 'Edición'),
        ('ELIMINAR', 'Eliminación'),
        ('CONSULTAR', 'Consulta'),
        ('RECUPERACION_CONTRASENA', 'Recuperación de contraseña'),
    ]
    
    ESTADOS = [
        ('EXITO', 'Éxito'),
        ('ERROR', 'Error'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    empresa = models.ForeignKey(
        'usuarios.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bitacoras'
    )
    usuario_email = models.EmailField(null=True, blank=True)
    usuario_nombre = models.CharField(max_length=150, null=True, blank=True)
    usuario_rol = models.CharField(max_length=150, null=True, blank=True)
    
    accion = models.CharField(max_length=30, choices=ACCIONES)
    estado = models.CharField(max_length=20, choices=ESTADOS)
    
    modulo_afectado = models.CharField(max_length=150, null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True) 
    fecha_hora = models.DateTimeField(auto_now_add=True)
    

    class Meta:
        db_table = 'bitacora'
        verbose_name = "Bitácora"
        verbose_name_plural = "Bitácoras"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.accion} - {self.usuario_email or 'Sistema'} - {self.fecha_hora.strftime('%Y-%m-%d %H:%M')}"
def registrar_bitacora(request, accion, descripcion, estado='EXITO', modulo='Sistema', usuario=None):
    try:
        usuario_log = usuario or (request.user if request.user.is_authenticated else None)
        empresa = getattr(usuario_log, 'empresa', None) if usuario_log else None
        
        # Obtener rol de forma segura
        rol_nombre = 'Sin rol'
        if usuario_log:
            try:
                rol = usuario_log.roles.first()
                if rol:
                    rol_nombre = rol.nombre
            except Exception:
                rol_nombre = 'Sin rol'

        Bitacora.objects.create(
            usuario=usuario_log,
            empresa=empresa,
            usuario_email=getattr(usuario_log, 'email', None),
            usuario_nombre=getattr(usuario_log, 'nombre', None),
            usuario_rol=rol_nombre,
            accion=accion,
            estado=estado,
            modulo_afectado=modulo,
            descripcion=descripcion,
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )
    except Exception:
        pass


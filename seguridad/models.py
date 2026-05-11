from django.db import models
from usuarios.models import Usuario, Permiso  # Importar el modelo de usuario para la relación en Bitacora

class Bitacora(models.Model):
    ACCIONES = [
        ('LOGIN', 'Inicio de sesión'),
        ('LOGOUT', 'Cierre de sesión'),
        ('CREAR', 'Creación'),
        ('EDITAR', 'Edición'),
        ('ELIMINAR', 'Eliminación'),
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

    usuario_email = models.EmailField(null=True, blank=True)
    usuario_nombre = models.CharField(max_length=150, null=True, blank=True)
    usuario_rol = models.CharField(max_length=150, null=True, blank=True)
    
    accion = models.CharField(max_length=20, choices=ACCIONES)
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
        return f"{self.accion} - {self.usuario_email or "Sistema"} - {self.fecha_hora.strftime('%Y-%m-%d %H:%M')}"

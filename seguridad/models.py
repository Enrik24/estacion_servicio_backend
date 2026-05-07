from django.db import models
from usuarios.models import Usuario  # ← Import relativo simple

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
    accion = models.CharField(max_length=20, choices=ACCIONES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS)

    class Meta:
        db_table = 'bitacora'
        verbose_name = 'Bitácora'
        verbose_name_plural = 'Bitácoras'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.accion} - {self.usuario_email} - {self.fecha_hora}"

from django.db import models
from django.contrib.postgres.fields import JSONField
from usuarios.models import Usuario  # ← Import relativo simple

class Bitacora(models.Model):
    ACCIONES = [
        ('CREATE', 'Crear'),
        ('UPDATE', 'Actualizar'),
        ('DELETE', 'Eliminar'),
        ('LOGIN', 'Inicio de sesión'),
        ('LOGOUT', 'Cierre de sesión'),
    ]
    
    DISPOSITIVOS = [
        ('Web', 'Web'),
        ('Mobile', 'Mobile'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bitacoras'
    )
    usuario_nombre = models.CharField(max_length=150, null=True, blank=True)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    modulo_afectado = models.CharField(max_length=100, null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    detalles = models.JSONField(default=dict, blank=True)
    direccion_ip = models.GenericIPAddressField(null=True, blank=True)
    dispositivo = models.CharField(
        max_length=10, 
        choices=DISPOSITIVOS, 
        default='Web'
    )
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bitacora'
        verbose_name = 'Bitácora'
        verbose_name_plural = 'Bitácoras'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['-creado_en']),
            models.Index(fields=['accion']),
            models.Index(fields=['dispositivo']),
            models.Index(fields=['usuario']),
        ]

    def __str__(self):
        return f"{self.accion} - {self.usuario_nombre} - {self.creado_en}"

from django.db import models
from usuarios.models import Usuario, Empresa
from ventas.models import Isla, Lado, Sucursal


class EstadoSurtidor(models.Model):
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
        ('FALLA', 'Falla'),
        ('AUTORIZADO_REMOTO', 'Autorizado Remoto (LPR)')
    ]

    lado = models.OneToOneField(
        Lado,
        on_delete=models.CASCADE,
        related_name='estado_surtidor'
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVO')
    descripcion_falla = models.TextField(blank=True, null=True)
    reportado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estados_reportados'
    )
    fecha_reporte = models.DateTimeField(auto_now=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)


    # =========================================================================
    # NUEVOS CAMPOS PARA INTEGRACIÓN IoT / LPR / CU 14
    # =========================================================================
    placa_activa = models.CharField(
        max_length=15, 
        blank=True, 
        null=True, 
        help_text="Placa leída por la cámara LPR que disparó el CU 14"
    )
    monto_autorizado = models.DecimalField(
        max_length=10,
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Monto prepagado inyectado remotamente al surtidor"
    )
    cliente_activo = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='despachos_remotos_actuales',
        help_text="Usuario dueño de la compra online activa"
    )

    # =========================================================================
    # MÉTODO DE NEGOCIO PARA CU 14 - LIMPIEZA DE DATOS POST-DESPACHO
    # =========================================================================
    def liberar_surtidor_post_despacho(self):
        """
        Limpia los datos transitorios inyectados por la IA (CU 14) 
        y devuelve el surtidor a estado disponible para el siguiente auto.
        """
        self.estado = 'ACTIVO'
        self.placa_activa = None
        self.monto_autorizado = 0.00
        self.cliente_activo = None
        self.descripcion_falla = None
        self.save()

    # =========================================================================

    class Meta:
        db_table = 'estados_surtidores'
        verbose_name = 'Estado de Surtidor'
        verbose_name_plural = 'Estados de Surtidores'

    def __str__(self):
        return f"Isla {self.lado.isla.numero} - Lado {self.lado.lado} - {self.estado}"


class HistorialEstadoSurtidor(models.Model):
    lado = models.ForeignKey(
        Lado,
        on_delete=models.CASCADE,
        related_name='historial_estados'
    )
    estado_anterior = models.CharField(max_length=20)
    estado_nuevo = models.CharField(max_length=20)
    descripcion = models.TextField(blank=True, null=True)
    cambiado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cambios_estado'
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'historial_estados_surtidores'
        ordering = ['-fecha']

    def __str__(self):
        return f"Isla {self.lado.isla.numero} - Lado {self.lado.lado}: {self.estado_anterior} → {self.estado_nuevo}"
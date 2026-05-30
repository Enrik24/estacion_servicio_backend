from django.db import models
from usuarios.models import Usuario, Empresa
from ventas.models import Sucursal, TipoCombustible


class Tanque(models.Model):
    id = models.BigAutoField(primary_key=True)
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='tanques'
    )
    tipo_combustible = models.ForeignKey(
        TipoCombustible,
        on_delete=models.PROTECT,
        related_name='tanques'
    )
    capacidad_maxima = models.DecimalField(max_digits=12, decimal_places=2)
    nivel_actual = models.DecimalField(max_digits=12, decimal_places=2)
    nivel_minimo_alerta = models.DecimalField(max_digits=12, decimal_places=2)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tanques'
        verbose_name = 'Tanque'
        verbose_name_plural = 'Tanques'
        ordering = ['sucursal', 'tipo_combustible']

    def __str__(self):
        return f"{self.sucursal.nombre} - {self.tipo_combustible.get_tipo_display()}"

    @property
    def porcentaje_nivel(self):
        if self.capacidad_maxima > 0:
            return round((float(self.nivel_actual) / float(self.capacidad_maxima)) * 100, 1)
        return 0

    @property
    def en_alerta(self):
        return self.nivel_actual <= self.nivel_minimo_alerta

    @property
    def litros_disponibles(self):
        return self.nivel_actual


class DescargaCombustible(models.Model):
    id = models.BigAutoField(primary_key=True)
    tanque = models.ForeignKey(
        Tanque,
        on_delete=models.CASCADE,
        related_name='descargas'
    )
    volumen_descargado = models.DecimalField(max_digits=12, decimal_places=2)
    nivel_antes = models.DecimalField(max_digits=12, decimal_places=2)
    nivel_despues = models.DecimalField(max_digits=12, decimal_places=2)
    registrado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='descargas_registradas'
    )
    observaciones = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'descargas_combustible'
        verbose_name = 'Descarga de Combustible'
        verbose_name_plural = 'Descargas de Combustible'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.tanque} - {self.volumen_descargado} Lt - {self.fecha.strftime('%d/%m/%Y')}"
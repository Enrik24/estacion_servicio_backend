from time import timezone
import datetime

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


class OrdenCompra(models.Model):
    """
    Representa el CU 19: Gestionar Órdenes de Compra a Proveedores.
    Fase de planificación logística y asignación de cupos de la ANH.
    """
    ESTADOS_OC = [
        ('PENDIENTE', 'Pendiente de Pago'),
        ('PAGADA', 'Pago Conciliado / Autorizada para Recojo'),
        ('COMPLETADA', 'Combustible Entregado en Surtidor'),
        ('ANULADA', 'Anulada'),
    ]

    # SOLUCIÓN CRÍTICA: Cambiado a unique=True para el código con prefijo (Ej: GEN-OC-0001)
    codigo_oc = models.CharField(max_length=20, unique=True, blank=True)
    proveedor = models.CharField(max_length=100, default='YPFB Corporación')
    tipo_combustible = models.ForeignKey(TipoCombustible, on_delete=models.PROTECT, related_name='ordenes_compra')
    volumen_solicitado = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=6, decimal_places=2)
    total_gasto = models.DecimalField(max_digits=12, decimal_places=2, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS_OC, default='PENDIENTE')
    creado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='ordenes_creadas')
    fecha_emision = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Orden de Compra"
        verbose_name_plural = "Órdenes de Compra"
        ordering = ['-fecha_emision']

    def save(self, *args, **kwargs):
        # 1. Calcular el gasto total automáticamente
        self.total_gasto = float(self.volumen_solicitado) * float(self.precio_unitario)
        
        # 2. Generación del código secuencial Multitenant
        if not self.codigo_oc:
            if self.creado_por and self.creado_por.empresa:
                empresa_actual = self.creado_por.empresa
                
                # REVISIÓN DINÁMICA DE CAMPOS: Evita el AttributeError
                if hasattr(empresa_actual, 'razon_social'):
                    nombre_base = empresa_actual.razon_social
                elif hasattr(empresa_actual, 'nombre'):
                    nombre_base = empresa_actual.nombre
                else:
                    nombre_base = "GENEX" # Fallback directo si no encuentra ninguno
                
                # Extraemos las 3 primeras letras limpias
                prefijo = str(nombre_base)[:3].upper().strip()
            else:
                prefijo = "GEN"
                empresa_actual = None

            if empresa_actual:
                # Contamos las órdenes que pertenecen al mismo Tenant (Empresa)
                total_ordenes_empresa = OrdenCompra.objects.filter(
                    creado_por__empresa=empresa_actual
                ).count()
            else:
                total_ordenes_empresa = OrdenCompra.objects.count()
            
            # Asegura el reinicio secuencial (0001) para tu nueva empresa
            nuevo_numero = total_ordenes_empresa + 1
            self.codigo_oc = f"{prefijo}-OC-{nuevo_numero:04d}"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo_oc} - {self.tipo_combustible} ({self.volumen_solicitado} Lts)"

class PagoProveedor(models.Model):
    """
    Representa el CU 20: Controlar Pagos a Proveedores.
    Fase de liquidación y prepago obligatorio.
    """
    METODOS_PAGO = [
        ('TRANSFERENCIA', 'Transferencia Electrónica SIGMA / Banco Unión'),
        ('DEPOSITO', 'Depósito en Ventanilla Bancaria'),
        ('QR', 'Pago por QR Institucional del Estado'),
    ]

    # Relación uno a uno inmutable: Un pago liquida exactamente una Orden de Compra
    orden_compra = models.OneToOneField(OrdenCompra, on_delete=models.CASCADE, related_name='pago_asociado')
    
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='TRANSFERENCIA')
    nro_referencia = models.CharField(max_length=100, blank=True, help_text="Código de transacción o número de depósito")
    comprobante_digital = models.FileField(upload_to='comprobantes_pagos/', null=True, blank=True)
    registrado_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='pagos_registrados')
    fecha_pago = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # 1. Guardamos el pago físicamente en la BD
        super().save(*args, **kwargs)
        
        # 2. TRIGGER AUTOMÁTICO: Cambiar estado de la Orden de Compra asociada
        if self.orden_compra:
            self.orden_compra.estado = 'PAGADA'
            # Forzamos la actualización únicamente del campo estado por rendimiento
            self.orden_compra.save(update_fields=['estado'])

    class Meta:
        verbose_name = "Pago a Proveedor"
        verbose_name_plural = "Pagos a Proveedores"
        db_table = "pagos_proveedores"

    def __str__(self):
        return f"Pago {self.nro_referencia} -> {self.orden_compra.codigo_oc}"
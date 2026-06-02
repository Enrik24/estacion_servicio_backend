
import uuid

from django.db import models
from usuarios.models import Usuario


class TipoCombustible(models.Model):
    TIPOS = [
        ('GASOLINA_ESPECIAL', 'Gasolina Especial'),
        ('GASOLINA_PREMIUM', 'Gasolina Premium'),
        ('DIESEL', 'Diésel Oil'),
        ('GNV', 'Gas Natural Vehicular'),
    ]

    id = models.BigAutoField(primary_key=True)
    tipo = models.CharField(max_length=30, choices=TIPOS)
    precio_litro = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    empresa = models.ForeignKey(
        'usuarios.Empresa',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tipos_combustible'
    )
    class Meta:
        db_table = 'tipos_combustible'
        verbose_name = 'Tipo de Combustible'
        verbose_name_plural = 'Tipos de Combustible'
        unique_together = ['tipo', 'empresa']

    def __str__(self):
        return f"{self.get_tipo_display()} - Bs. {self.precio_litro}/Lt"

class Sucursal(models.Model):
    ESTADOS = [
        ('ACTIVA', 'Activa'),
        ('INACTIVA', 'Inactiva'),
    ]

    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    nit = models.CharField(max_length=20, blank=True, null=True)
    cantidad_islas = models.IntegerField(default=1)
    tiene_gnv = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVA')
    latitud = models.DecimalField(max_digits=18, decimal_places=15, blank=True, null=True)
    longitud = models.DecimalField(max_digits=18, decimal_places=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    empresa = models.ForeignKey(
        'usuarios.Empresa',
        on_delete=models.CASCADE,
   
    )
    tipos_combustible = models.ManyToManyField(
        'TipoCombustible',
        blank=True,
        related_name='sucursales'
    )
    class Meta:
        db_table = 'sucursales'
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursales'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Isla(models.Model):
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
        ('FALLA', 'Falla'),
    ]

    id = models.BigAutoField(primary_key=True)
    numero = models.IntegerField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVO')
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='islas',
        null=True,
        blank=True
    )
    class Meta:
        db_table = 'islas'
        verbose_name = 'Isla'
        verbose_name_plural = 'Islas'
        ordering = ['numero']

        unique_together = ['sucursal', 'numero']  


    def __str__(self):
        suc_name = self.sucursal.nombre if self.sucursal else "S/N"
        return f"Isla {self.numero} - {suc_name}"


class Lado(models.Model):
    LADOS = [
        ('A', 'Lado A'),
        ('B', 'Lado B'),
    ]

    id = models.BigAutoField(primary_key=True)
    isla = models.ForeignKey(Isla, on_delete=models.CASCADE, related_name='lados')
    lado = models.CharField(max_length=1, choices=LADOS)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'lados'
        verbose_name = 'Lado'
        verbose_name_plural = 'Lados'
        unique_together = ['isla', 'lado']
        ordering = ['isla', 'lado']

    def __str__(self):
        return f"Isla {self.isla.numero} - Lado {self.lado}"

class Turno(models.Model):
    ESTADOS = [
        ('ABIERTO', 'Abierto'),
        ('CERRADO', 'Cerrado'),
    ]

    HORARIOS = [
        ('MANANA', 'Mañana 06:00 - 14:00'),
        ('TARDE', 'Tarde 14:00 - 22:00'),
        ('NOCHE', 'Noche 22:00 - 06:00'),
    ]

    id = models.BigAutoField(primary_key=True)
    operador = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='turnos')
    isla = models.ForeignKey(Isla, on_delete=models.PROTECT, related_name='turnos')
    horario = models.CharField(max_length=10, choices=HORARIOS)
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ABIERTO')
    monto_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    consolidado = models.BooleanField(default=False)
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='turnos',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'turnos'
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'

    def __str__(self):
        return f"Turno {self.id} - {self.operador.nombre} - Isla {self.isla.numero}"

class Cliente(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    nit = models.CharField(max_length=20, unique=True, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cliente_ventas',
    )
    telefono = models.CharField(max_length=20, null=True, blank=True)
    limite_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    saldo_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    empresa = models.ForeignKey(
        'usuarios.Empresa',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='clientes'
    )
    usuario = models.OneToOneField(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cliente_pos'
)
    class Meta:
        db_table = 'clientes'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return f"{self.nombre} - {self.nit}"
    
class Vehiculo(models.Model):
    id = models.BigAutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='vehiculos')
    placa = models.CharField(max_length=20, unique=True)
    marca = models.CharField(max_length=50, blank=True, null=True)
    modelo = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=30, blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehiculos'
        verbose_name = 'Vehículo'
        verbose_name_plural = 'Vehículos'

    def __str__(self):
        return f"{self.placa} - {self.cliente.nombre}"

class Venta(models.Model):
    METODOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TARJETA', 'Tarjeta'),
        ('QR', 'Pago QR'),
        ('CREDITO_FLEET', 'Crédito Fleet'),
    ]
    ESTADOS = [
        ('COMPLETADA', 'Completada'),
        ('ANULADA', 'Anulada'),
    ]

    id = models.BigAutoField(primary_key=True)
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name='ventas')
    lado = models.ForeignKey(Lado, on_delete=models.PROTECT, related_name='ventas')
    tipo_combustible = models.ForeignKey(TipoCombustible, on_delete=models.PROTECT, related_name='ventas')
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas')
    litros = models.DecimalField(max_digits=10, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='COMPLETADA')
    numero_comprobante = models.CharField(max_length=50, unique=True)

    client_request_id = models.UUIDField(unique=True, null=True, blank=True, db_index=True, default=None)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='ventas_registradas')

    class Meta:
        db_table = 'ventas'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Venta {self.numero_comprobante} - Bs. {self.total}"
    
class EmpresaCliente(models.Model):
    empresa = models.ForeignKey(
        'usuarios.Empresa',
        on_delete=models.CASCADE,
        related_name='empresa_clientes'
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='empresa_clientes'
    )
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)



class CompraCombustible(models.Model):
    id = models.BigAutoField(primary_key=True)
    tipo_combustible = models.ForeignKey(TipoCombustible, on_delete=models.PROTECT, related_name='compras')
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    unidad = models.CharField(max_length=10)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='compras_registradas')

    class Meta:
        db_table = 'compras_combustible'
        verbose_name = 'Compra de Combustible'
        verbose_name_plural = 'Compras de Combustible'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Compra {self.id} - {self.tipo_combustible.get_tipo_display()} - Bs. {self.total}"


class EmpresaCliente(models.Model):
    empresa = models.ForeignKey(
        'usuarios.Empresa',
        on_delete=models.CASCADE,
        related_name='empresa_clientes'
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='empresa_clientes'
    )
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'empresa_clientes'
        unique_together = ['empresa', 'cliente']
        verbose_name = 'Cliente de Empresa'
        verbose_name_plural = 'Clientes de Empresas'

    def __str__(self):
        return f"{self.cliente.nombre} - {self.empresa.nombre}"

class OrdenPrepago(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('PROCESANDO_PAGO', 'Procesando Pago'),
        ('PAGADO', 'Pagado'),
        ('FALLIDO', 'Fallido'),
        ('DESPACHADO', 'Despachado'),
        ('RECHAZADO', 'Rechazado'),
        ('VENCIDO', 'Vencido'),
    ]

    id = models.BigAutoField(primary_key=True)
    numero_orden = models.CharField(max_length=25, unique=True, editable=False, null=True, blank=True)
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='ordenes_prepago')
    tipo_combustible = models.ForeignKey('TipoCombustible', on_delete=models.PROTECT, related_name='ordenes_prepago')
    precio_por_litro = models.DecimalField(max_digits=10, decimal_places=2, help_text='Precio congelado al momento de la compra', null=True, blank=True)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    litros = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True)
    comprobante_pdf = models.FileField(upload_to='comprobantes/', null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_expiracion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ordenes_prepago'
        verbose_name = 'Orden de Prepago'
        verbose_name_plural = 'Órdenes de Prepago'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Prepago {self.numero_orden} - {self.cliente.nombre} - Bs. {self.monto_total}"

    def save(self, *args, **kwargs):
        from django.utils import timezone
        from datetime import timedelta
        if not self.fecha_expiracion:
            self.fecha_expiracion = timezone.now() + timedelta(hours=24)
        if not self.numero_orden:
            self.numero_orden = OrdenPrepago.generar_numero_orden()
        super().save(*args, **kwargs)

    @staticmethod
    def generar_numero_orden():
        """Genera un número de orden con formato PRE-AAAAMMDD-XXXXX."""
        from django.utils import timezone
        hoy = timezone.now().strftime('%Y%m%d')
        prefijo = f'PRE-{hoy}-'
        ultima = OrdenPrepago.objects.filter(
            numero_orden__startswith=prefijo
        ).order_by('-numero_orden').first()
        if ultima:
            try:
                ultimo_num = int(ultima.numero_orden.split('-')[-1])
            except ValueError:
                ultimo_num = 0
            siguiente = ultimo_num + 1
        else:
            siguiente = 1
        return f"{prefijo}{siguiente:05d}"

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
    tipo = models.CharField(max_length=30, choices=TIPOS, unique=True)
    precio_litro = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tipos_combustible'
        verbose_name = 'Tipo de Combustible'
        verbose_name_plural = 'Tipos de Combustible'

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
    latitud = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitud = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    numero = models.IntegerField(unique=True)
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

    def __str__(self):
        return f"Isla {self.numero}"


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
    telefono = models.CharField(max_length=20, null=True, blank=True)
    limite_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    saldo_credito = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clientes'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return f"{self.nombre} - {self.nit}"


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
    fecha_hora = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='ventas_registradas')

    class Meta:
        db_table = 'ventas'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Venta {self.numero_comprobante} - Bs. {self.total}"
    


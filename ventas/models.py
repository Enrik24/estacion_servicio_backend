from django.db import models
from usuarios.models import Usuario

class Surtidor(models.Model):
    TIPOS_COMBUSTIBLE = [
        ('GASOLINA', 'Gasolina'),
        ('DIESEL', 'Diésel'),
        ('GNV', 'Gas Natural Vehicular'),
    ]
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
        ('FALLA', 'Falla'),
    ]

    id = models.BigAutoField(primary_key=True)
    numero = models.IntegerField(unique=True)
    tipo_combustible = models.CharField(max_length=20, choices=TIPOS_COMBUSTIBLE)
    precio_litro = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVO')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'surtidores'
        verbose_name = 'Surtidor'
        verbose_name_plural = 'Surtidores'

    def __str__(self):
        return f"Surtidor {self.numero} - {self.tipo_combustible}"


class Turno(models.Model):
    ESTADOS = [
        ('ABIERTO', 'Abierto'),
        ('CERRADO', 'Cerrado'),
    ]

    id = models.BigAutoField(primary_key=True)
    operador = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='turnos')
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ABIERTO')
    monto_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monto_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'turnos'
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'

    def __str__(self):
        return f"Turno {self.id} - {self.operador.nombre} - {self.estado}"


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
    surtidor = models.ForeignKey(Surtidor, on_delete=models.PROTECT, related_name='ventas')
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
"""Serializadores para la aplicación de ventas.

Este módulo contiene los serializadores para convertir modelos Django a JSON
und realizar validaciones en las operaciones CRUD de venta, clientes, turnos e islas.
"""

from rest_framework import serializers
from .models import Sucursal, Isla, Lado, TipoCombustible, Turno, Cliente, Venta,Vehiculo
from django.db.models import Sum, Case, When, DecimalField


class IslaSerializer(serializers.ModelSerializer):
    """Serializador para el modelo Isla. Incluye los lados activos de cada isla."""
    lados = serializers.SerializerMethodField()

    class Meta:
        model = Isla
        fields = '__all__'

    def get_lados(self, obj):
        """Obtiene lista de lados activos con su ID y número."""
        return [{'id': l.id, 'lado': l.lado} for l in obj.lados.filter(activo=True)]


class LadoSerializer(serializers.ModelSerializer):
    """Serializador para el modelo Lado con número de isla y nombre formateado."""
    isla_numero = serializers.IntegerField(source='isla.numero', read_only=True)
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model = Lado
        fields = '__all__'

    def get_nombre_completo(self, obj):
        """Retorna el nombre completo formateado como 'Isla X - Lado Y'."""
        return f"Isla {obj.isla.numero} - Lado {obj.lado}"

class TipoCombustibleSerializer(serializers.ModelSerializer):
    """Serializador para tipos de combustible con su descripción legible."""
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = TipoCombustible
        fields = '__all__'


class TurnoSerializer(serializers.ModelSerializer):
    """Serializador para turnos con información del operador, isla y horario."""
    operador_nombre = serializers.CharField(source='operador.nombre', read_only=True)
    isla_numero = serializers.IntegerField(source='isla.numero', read_only=True)
    horario_display = serializers.CharField(source='get_horario_display', read_only=True)
    operador = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Turno
        fields = '__all__'
        read_only_fields = ['fecha_apertura', 'estado', 'operador']


class ClienteSerializer(serializers.ModelSerializer):
    """Serializador básico para el modelo Cliente."""
    class Meta:
        model = Cliente
        fields = '__all__'


class VentaSerializer(serializers.ModelSerializer):
    """Serializador para ventas con información del combustible, cliente, operador e isla."""
    tipo_combustible_nombre = serializers.CharField(source='tipo_combustible.get_tipo_display', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    operador_nombre = serializers.CharField(source='created_by.nombre', read_only=True)
    isla_numero = serializers.IntegerField(source='turno.isla.numero', read_only=True)
    lado_nombre = serializers.CharField(source='lado.lado', read_only=True)

    class Meta:
        model = Venta
        fields = '__all__'
        read_only_fields = ['total', 'precio_unitario', 'numero_comprobante', 'fecha_hora', 'created_by']


class RegistrarVentaSerializer(serializers.Serializer):
    """Serializador para registrar ventas con validación de litros o monto.
    
    Valida que se proporcione SOLO litros O monto_bs (no ambos).
    Si se proporciona monto, calcula automáticamente los litros.
    """
    lado_id = serializers.IntegerField()
    tipo_combustible_id = serializers.IntegerField()
    litros = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True)
    monto_bs = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    metodo_pago = serializers.ChoiceField(choices=Venta.METODOS_PAGO)
    cliente_id = serializers.IntegerField(required=False, allow_null=True)
    es_lleno = serializers.BooleanField(default=False)

    def validate_tipo_combustible_id(self, value):
        """Valida que el tipo de combustible exista y esté activo."""
        try:
            TipoCombustible.objects.get(id=value, activo=True)
        except TipoCombustible.DoesNotExist:
            raise serializers.ValidationError('Tipo de combustible no encontrado o inactivo')
        return value

    def validate(self, data):
        """Valida que se proporcione litros O monto_bs (exclusivamente).
        
        Si se proporciona monto_bs, calcula automáticamente los litros basándose
        en el precio unitario del tipo de combustible.
        """
        # Si es un lleno, no requiere validación de monto o litros
        if data.get('es_lleno'):
            return data
            
        # Si no es lleno, debe tener monto_bs
        if not data.get('monto_bs'):
            raise serializers.ValidationError(
                'Debes ingresar un monto en Bs o seleccionar "Lleno"'
            )
        if data.get('monto_bs') and data['monto_bs'] <= 0:
            raise serializers.ValidationError('El monto debe ser mayor a cero')
        return data
    
class VehiculoSerializer(serializers.ModelSerializer):
    """Serializador para vehículos con información del cliente asociado."""
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    cliente_nit = serializers.CharField(source='cliente.nit', read_only=True)
    cliente_telefono = serializers.CharField(source='cliente.telefono', read_only=True)
    cliente_id = serializers.IntegerField(source='cliente.id', read_only=True)

    class Meta:
        model = Vehiculo
        fields = ['id', 'placa', 'marca', 'modelo', 'color',
                  'cliente_id', 'cliente_nombre', 'cliente_nit', 'cliente_telefono']


class RegistrarClienteVehiculoSerializer(serializers.Serializer):
    """Serializador para registrar cliente y vehículo conjuntamente."""
    nombre = serializers.CharField(max_length=150)
    nit = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    ci = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    placa = serializers.CharField(max_length=20)
    marca = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    modelo = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    color = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)

    def validate_placa(self, value):
        """Valida que la placa no exista ya en la base de datos."""
        placa = value.upper().strip()
        if Vehiculo.objects.filter(placa=placa).exists():
            raise serializers.ValidationError('Ya existe un vehículo con esta placa')
        return placa

    def validate_nit(self, value):
        """Valida que el NIT no exista ya en la base de datos."""
        if value and Cliente.objects.filter(nit=value).exists():
            raise serializers.ValidationError('Ya existe un cliente con este NIT')
        return value    

class SucursalSerializer(serializers.ModelSerializer):
    cantidad_islas_creadas = serializers.SerializerMethodField()
    gerente = serializers.SerializerMethodField()
    tipos_combustible = serializers.PrimaryKeyRelatedField(
        queryset=TipoCombustible.objects.all(),
        many=True,
        required=False
    )
    class Meta:
        model = Sucursal
        fields = '__all__'

    def get_cantidad_islas_creadas(self, obj):
        return obj.islas.count()

    def get_gerente(self, obj):
        from usuarios.models import Usuario
        gerente = Usuario.objects.filter(
            sucursal=obj,
            roles__nombre__iexact='Gerente'
        ).first()
        if gerente:
            return {'id': gerente.id, 'nombre': gerente.nombre}
        gerente = Usuario.objects.filter(
            sucursal=obj,
            roles__nombre__iexact='Gerente/Dueño'
        ).first()
        if gerente:
            return {'id': gerente.id, 'nombre': gerente.nombre}
        return None  

class ConsolidacionCajaSerializer(serializers.Serializer):
    """Serializador para reportes de consolidación de caja.
    
    PROPÓSITO: Prepara datos de turnos cerrados para el reporte de consolidación de caja,
    calculando automáticamente:
    - Total de ventas completadas (monto en sistema)
    - Diferencia entre caja física y monto en sistema
    - Cantidad de facturas emitidas
    - Ubicación formateada (Sucursal - Isla)
    
    USO: Se utiliza en ConsolidacionCajaViewSet.list() para generar reportes de cierre
    de turnos con indicadores de reconciliación de caja.
    """
    
    # ============================================================================
    # CAMPOS BÁSICOS DEL TURNO - Datos estáticos obtenidos directamente del modelo
    # ============================================================================
    # ID único del turno (necesario para acciones como consolidar)
    id = serializers.IntegerField(read_only=True)
    # Nombre del operador que abrió el turno
    operador_nombre = serializers.ReadOnlyField(source='operador.nombre')
    # Número de isla donde se realizó el turno
    isla_numero = serializers.IntegerField(source='isla.numero', read_only=True)
    # Descripción legible del horario (ej: "Mañana 06:00-14:00")
    horario_display = serializers.CharField(source='get_horario_display', read_only=True)
    # Fecha y hora de apertura del turno
    fecha_apertura = serializers.DateTimeField(read_only=True)
    # Fecha y hora de cierre del turno
    fecha_cierre = serializers.DateTimeField(read_only=True)
    # Monto inicial en caja (dinero con el que se abrió el turno)
    monto_inicial = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    # Monto final en caja (dinero registrado al cierre del turno)
    monto_final = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    # ============================================================================
    # CAMPOS CALCULADOS - Generados mediante métodos personalizados (SerializerMethodField)
    # Estos campos realizan operaciones de agregación y cálculo sobre los datos del turno
    # ============================================================================
    # Ubicación formateada: "Sucursal: Nombre - Isla: Número"
    ubicacion = serializers.SerializerMethodField()
    # Total de ventas completadas sumadas desde la BD (monto registrado en el sistema)
    monto_sistema = serializers.SerializerMethodField()
    # Diferencia entre monto final (físico) y monto sistema (registrado)
    # Positivo = sobrante en caja | Negativo = faltante en caja
    diferencia = serializers.SerializerMethodField()
    # Cantidad total de facturas/ventas completadas en el turno
    total_facturas = serializers.SerializerMethodField()
    # Desglose de ventas por método de pago (Efectivo, Tarjeta, QR, Fleet)
    metodos_pago = serializers.SerializerMethodField()
    # Desglose de ventas por tipo de combustible (Gasolina Especial, Premium, Diésel, GNV)
    tipos_combustible = serializers.SerializerMethodField()

    class Meta:
        model = Turno
        # Define qué campos se incluyen en la serialización
        fields = [
            'id',
            'operador_nombre',
            'isla_numero',
            'horario_display',
            'fecha_apertura',
            'fecha_cierre',
            'monto_inicial',
            'monto_final',
            'ubicacion', 
            'monto_sistema',
            'diferencia',
            'total_facturas',
            'metodos_pago',
            'tipos_combustible'
        ]
    
    def get_ubicacion(self, obj):
        """Retorna la ubicación formateada como: 'Sucursal: X - Isla: Y'.
        
        NOTA IMPORTANTE: El Turno tiene dos formas de asociarse con Sucursal:
        1. Directamente via obj.sucursal (campo denormalizado)
        2. A través de obj.isla.sucursal (relación natural)
        
        Este método intenta ambas rutas y maneja gracefully si alguna es NULL.
        
        Args:
            obj: Instancia de Turno
            
        Returns:
            str: Ubicación formateada
        """
        # Intentar usar sucursal directa del Turno
        if obj.sucursal:
            return f"Sucursal: {obj.sucursal.nombre} - Isla: {obj.isla.numero}"
        # Si no, intentar usar la relación a través de Isla
        elif obj.isla and obj.isla.sucursal:
            return f"Sucursal: {obj.isla.sucursal.nombre} - Isla: {obj.isla.numero}"
        # Si ninguna está disponible, usar un valor por defecto
        else:
            return f"Isla: {obj.isla.numero if obj.isla else 'N/A'}"
    
    def get_monto_sistema(self, obj):
        """Calcula el total de ventas completadas (monto en sistema).
        
        LÓGICA: Suma todos los totales (campo 'total') de las ventas asociadas
        al turno que tengan estado 'COMPLETADA'. Excluye ventas anuladas.
        
        USO: Este es el monto que está registrado en el sistema/BD según los
        comprobantes de venta emitidos.
        
        Args:
            obj: Instancia de Turno
            
        Returns:
            Decimal: Total de ventas completadas. Retorna 0 si no hay ventas.
        """
        # aggregate() retorna un diccionario con la clave 'total__sum'
        # Si no hay ventas, retorna None, por lo que usamos 'or 0' para evitar errores
        total = obj.ventas.filter(estado='COMPLETADA').aggregate(Sum('total'))['total__sum']
        return total or 0
    
    def get_diferencia(self, obj):
        """Calcula la diferencia entre caja física y sistema.
        
        FÓRMULA: Diferencia = Monto Final (físico) - Monto Sistema (BD)
        
        INTERPRETACIÓN:
        - Diferencia > 0: Sobrante en caja (hay más dinero físico que en el sistema)
        - Diferencia < 0: Faltante en caja (hay menos dinero físico que en el sistema)
        - Diferencia = 0: Cuadre exacto (dinero físico coincide con sistema)
        
        USO: Este valor es crucial para identificar discrepancias en la gestión de caja.
        
        Args:
            obj: Instancia de Turno
            
        Returns:
            Decimal: La diferencia (puede ser positiva, negativa o cero)
        """
        # Obtiene el monto registrado en el sistema
        monto_sistema = self.get_monto_sistema(obj)
        # Obtiene el monto final (dinero físico en caja). Si es None, asume 0
        monto_final = obj.monto_final or 0
        # Calcula la diferencia
        return monto_final - monto_sistema
    
    def get_total_facturas(self, obj):
        """Retorna el total de facturas/ventas completadas en el turno.
        
        LÓGICA: Cuenta todas las ventas del turno con estado 'COMPLETADA'.
        
        USO: Indicador de productividad del turno (cuántas transacciones se hicieron).
        
        Args:
            obj: Instancia de Turno
            
        Returns:
            int: Cantidad de facturas completadas
        """
        return obj.ventas.filter(estado='COMPLETADA').count()

    def get_metodos_pago(self, obj):
        """Retorna el desglose de ventas agrupadas por método de pago.
        
        LÓGICA: Suma el total de todas las ventas completadas, agrupadas por
        cada método de pago disponible (EFECTIVO, TARJETA, QR, CREDITO_FLEET).
        
        USO: Proporciona información sobre cuál fue el monto recaudado por cada
        método de pago durante el turno.
        
        Returns:
            dict: Diccionario con claves como 'efectivo', 'tarjeta', 'qr', 'credito_fleet'
                  y valores como Decimal con el total de ventas por ese método.
                  Ejemplo: {'efectivo': Decimal('1000.00'), 'tarjeta': Decimal('500.00'), ...}
        """
        # Obtener todas las ventas completadas del turno
        ventas = obj.ventas.filter(estado='COMPLETADA')
        
        # Inicializar diccionario con métodos de pago
        resultado = {
            'efectivo': 0,
            'tarjeta': 0,
            'qr': 0,
            'credito_fleet': 0
        }
        
        # Iterar sobre las ventas y sumar por método de pago
        for venta in ventas:
            metodo = venta.metodo_pago.lower()
            if metodo == 'efectivo':
                resultado['efectivo'] += float(venta.total)
            elif metodo == 'tarjeta':
                resultado['tarjeta'] += float(venta.total)
            elif metodo == 'qr':
                resultado['qr'] += float(venta.total)
            elif metodo == 'credito_fleet':
                resultado['credito_fleet'] += float(venta.total)
        
        # Convertir a Decimal con 2 decimales para precisión en dinero
        return {
            'efectivo': round(resultado['efectivo'], 2),
            'tarjeta': round(resultado['tarjeta'], 2),
            'qr': round(resultado['qr'], 2),
            'credito_fleet': round(resultado['credito_fleet'], 2)
        }

    def get_tipos_combustible(self, obj):
        """Retorna el desglose de ventas agrupadas por tipo de combustible.
        
        LÓGICA: Suma el total de todas las ventas completadas, agrupadas por
        cada tipo de combustible disponible (GASOLINA_ESPECIAL, GASOLINA_PREMIUM,
        DIESEL, GNV).
        
        USO: Proporciona información sobre cuál fue el monto de ventas por cada
        tipo de combustible durante el turno, útil para análisis de inventario
        y demanda de productos.
        
        Returns:
            dict: Diccionario con claves como 'gasolina_especial', 'gasolina_premium',
                  'diesel', 'gnv' y valores como Decimal con el total de ventas 
                  por ese tipo.
                  Ejemplo: {'gasolina_especial': Decimal('2000.00'), ...}
        """
        # Obtener todas las ventas completadas del turno
        ventas = obj.ventas.filter(estado='COMPLETADA')
        
        # Inicializar diccionario con tipos de combustible
        resultado = {
            'gasolina_especial': 0,
            'gasolina_premium': 0,
            'diesel': 0,
            'gnv': 0
        }
        
        # Iterar sobre las ventas y sumar por tipo de combustible
        for venta in ventas:
            tipo = venta.tipo_combustible.tipo.lower()
            if tipo == 'gasolina_especial':
                resultado['gasolina_especial'] += float(venta.total)
            elif tipo == 'gasolina_premium':
                resultado['gasolina_premium'] += float(venta.total)
            elif tipo == 'diesel':
                resultado['diesel'] += float(venta.total)
            elif tipo == 'gnv':
                resultado['gnv'] += float(venta.total)
        
        # Convertir a Decimal con 2 decimales para precisión en dinero
        return {
            'gasolina_especial': round(resultado['gasolina_especial'], 2),
            'gasolina_premium': round(resultado['gasolina_premium'], 2),
            'diesel': round(resultado['diesel'], 2),
            'gnv': round(resultado['gnv'], 2)
        }
        
        return obj.islas.count()


# TICKET
class TicketVentaSerializer(serializers.ModelSerializer):
    comprobante = serializers.SerializerMethodField()
    sucursal = serializers.SerializerMethodField()
    despacho = serializers.SerializerMethodField()
    operador = serializers.SerializerMethodField()
    combustible = serializers.SerializerMethodField()
    pago = serializers.SerializerMethodField()
    cliente = serializers.SerializerMethodField()

    class Meta:
        model = Venta
        fields = ['comprobante', 'sucursal', 'despacho', 'operador', 'combustible', 'pago', 'cliente']

    def get_comprobante(self, obj):
        return {
            'numero': obj.numero_comprobante,
            'fecha_hora': obj.fecha_hora,
            'estado': obj.estado,
        }

    def get_sucursal(self, obj):
        sucursal = obj.turno.isla.sucursal
        if not sucursal:
            return None
        return {
            'nombre': sucursal.nombre,
            'direccion': sucursal.direccion,
            'telefono': sucursal.telefono,
            'nit': sucursal.nit,
        }

    def get_despacho(self, obj):
        return {
            'isla': obj.turno.isla.numero,
            'lado': obj.lado.lado,
            'horario': obj.turno.get_horario_display(),
        }

    def get_operador(self, obj):
        return {
            'nombre': obj.created_by.nombre,
        }

    def get_combustible(self, obj):
        return {
            'tipo': obj.tipo_combustible.get_tipo_display(),
            'litros': str(obj.litros),
            'precio_unitario': str(obj.precio_unitario),
            'total': str(obj.total),
        }

    def get_pago(self, obj):
        return {
            'metodo': obj.get_metodo_pago_display(),
        }

    def get_cliente(self, obj):
        if not obj.cliente:
            return None
        return {
            'nombre': obj.cliente.nombre,
            'nit': obj.cliente.nit,
        }

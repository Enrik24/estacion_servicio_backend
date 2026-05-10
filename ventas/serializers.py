from rest_framework import serializers
from .models import Sucursal, Isla, Lado, TipoCombustible, Turno, Cliente, Venta
from django.db.models import Sum


class IslaSerializer(serializers.ModelSerializer):
    lados = serializers.SerializerMethodField()

    class Meta:
        model = Isla
        fields = '__all__'

    def get_lados(self, obj):
        return [{'id': l.id, 'lado': l.lado} for l in obj.lados.filter(activo=True)]


class LadoSerializer(serializers.ModelSerializer):
    isla_numero = serializers.IntegerField(source='isla.numero', read_only=True)
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model = Lado
        fields = '__all__'

    def get_nombre_completo(self, obj):
        return f"Isla {obj.isla.numero} - Lado {obj.lado}"

class TipoCombustibleSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = TipoCombustible
        fields = '__all__'


class TurnoSerializer(serializers.ModelSerializer):
    operador_nombre = serializers.CharField(source='operador.nombre', read_only=True)
    isla_numero = serializers.IntegerField(source='isla.numero', read_only=True)
    horario_display = serializers.CharField(source='get_horario_display', read_only=True)
    operador = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Turno
        fields = '__all__'
        read_only_fields = ['fecha_apertura', 'estado', 'operador']


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'


class VentaSerializer(serializers.ModelSerializer):
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
    lado_id = serializers.IntegerField()
    tipo_combustible_id = serializers.IntegerField()
    litros = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, allow_null=True)
    monto_bs = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    metodo_pago = serializers.ChoiceField(choices=Venta.METODOS_PAGO)
    cliente_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_tipo_combustible_id(self, value):
        try:
            TipoCombustible.objects.get(id=value, activo=True)
        except TipoCombustible.DoesNotExist:
            raise serializers.ValidationError('Tipo de combustible no encontrado o inactivo')
        return value

    def validate(self, data):
        # Validar que se proporcione litros o monto_bs, pero no ambos
        litros = data.get('litros')
        monto_bs = data.get('monto_bs')
        
        if not litros and not monto_bs:
            raise serializers.ValidationError('Debes proporcionar litros o monto_bs')
        
        if litros and monto_bs:
            raise serializers.ValidationError('No proporciones ambos: litros y monto_bs')
        
        # Si proporciona monto_bs, calcular litros
        if monto_bs:
            if monto_bs <= 0:
                raise serializers.ValidationError('El monto debe ser mayor a cero')
            try:
                tipo_combustible = TipoCombustible.objects.get(id=data['tipo_combustible_id'], activo=True)
                litros_calculados = monto_bs / tipo_combustible.precio_litro
                data['litros'] = litros_calculados
            except TipoCombustible.DoesNotExist:
                raise serializers.ValidationError('Tipo de combustible no encontrado')
        else:
            # Validar litros si se proporciona
            if litros <= 0:
                raise serializers.ValidationError('Los litros deben ser mayor a cero')
        
        return data
#SUCURSAL
class SucursalSerializer(serializers.ModelSerializer):
    cantidad_islas_creadas = serializers.SerializerMethodField()

    class Meta:
        model = Sucursal
        fields = '__all__'

    def get_cantidad_islas_creadas(self, obj):
        return obj.islas.count()

# Serializador para la consolidación de caja - prepara datos de turnos cerrados para reporte
class ConsolidacionCajaSerializer(serializers.Serializer):
    # Campo de solo lectura: obtiene el nombre del operador del turno
    operador_nombre = serializers.ReadOnlyField(source='operador.nombre')
    isla_numero = serializers.IntegerField(source='isla.numero', read_only=True)
    horario_display = serializers.CharField(source='get_horario_display', read_only=True)
    fecha_apertura = serializers.DateTimeField(read_only=True)
    fecha_cierre = serializers.DateTimeField(read_only=True)
    monto_inicial = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    monto_final = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    def get_total_facturas(self, obj):
        """Calcula el total de facturas en el turno"""
        ventas = Venta.objects.filter(turno=obj, estado='COMPLETADA')
        return ventas.count()
    
    def get_total_ventas(self, obj):
        """Calcula el total de ventas del turno"""
        ventas = Venta.objects.filter(turno=obj, estado='COMPLETADA')
        return sum(v.total for v in ventas)
    
    def get_diferencia(self, obj):
        """Calcula la diferencia entre monto final y total de ventas"""
        ventas = Venta.objects.filter(turno=obj, estado='COMPLETADA')
        total_ventas = sum(v.total for v in ventas)
        monto_final = obj.monto_final or 0
        return monto_final - total_ventas
    
    total_facturas = serializers.SerializerMethodField()
    total_ventas = serializers.SerializerMethodField()
    diferencia = serializers.SerializerMethodField()
    
    # Campo calculado: cantidad total de facturas (ventas completadas)
    total_facturas = serializers.SerializerMethodField()

    class Meta:
        model = Turno
        # Define qué campos se incluyen en la serialización
        fields = [
            'operador_nombre',
            'ubicacion', 
            'monto_sistema',
            'diferencia',
            'total_facturas'
            ]
    
    # Método que calcula y retorna la ubicación formateada (sucursal + isla)
    def get_ubicacion(self, obj):
        return f"Sucursal: {obj.isla.sucursal.nombre} - Isla: {obj.isla.numero}"
    
    # Método que obtiene el total de ventas completadas sumando todos los montos
    def get_monto_sistema(self, obj):
        # Filtra ventas completadas y suma sus totales; retorna 0 si no hay ventas
        total = obj.ventas.filter(estado='COMPLETADA').aggregate(Sum('total'))['total__sum']
        return total or 0
    
    # Método que calcula la diferencia entre caja física y sistema
    def get_diferencia(self, obj):
        # Obtiene el monto total del sistema
        monto_sistema = self.get_monto_sistema(obj)
        # Obtiene el monto final registrado en caja (o 0 si está vacío)
        monto_final = obj.monto_final or 0
        # Retorna la diferencia: positiva (sobrante) o negativa (faltante)
        return monto_final - monto_sistema
    
    # Método que cuenta el total de ventas completadas en el turno
    def get_total_facturas(self, obj):
        return obj.ventas.filter(estado='COMPLETADA').count()
        
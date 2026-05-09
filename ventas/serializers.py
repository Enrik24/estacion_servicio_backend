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
    litros = serializers.DecimalField(max_digits=10, decimal_places=3)
    metodo_pago = serializers.ChoiceField(choices=Venta.METODOS_PAGO)
    cliente_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_tipo_combustible_id(self, value):
        try:
            TipoCombustible.objects.get(id=value, activo=True)
        except TipoCombustible.DoesNotExist:
            raise serializers.ValidationError('Tipo de combustible no encontrado o inactivo')
        return value

    def validate_litros(self, value):
        if value <= 0:
            raise serializers.ValidationError('Los litros deben ser mayor a cero')
        return value
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
    
    # Campo calculado: genera ubicación completa (sucursal e isla)
    ubicacion = serializers.SerializerMethodField()
    
    # Campo calculado: suma total de ventas completadas del turno
    monto_sistema = serializers.SerializerMethodField()
    
    # Campo calculado: diferencia entre monto registrado en caja y monto del sistema
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
        
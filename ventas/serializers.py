from rest_framework import serializers
from .models import Sucursal, Isla, Lado, TipoCombustible, Turno, Cliente, Venta


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
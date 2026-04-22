from rest_framework import serializers
from .models import Surtidor, Turno, Cliente, Venta
from usuarios.models import Usuario


class SurtidorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surtidor
        fields = '__all__'


class TurnoSerializer(serializers.ModelSerializer):
    operador_nombre = serializers.CharField(source='operador.nombre', read_only=True)
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
    surtidor_numero = serializers.IntegerField(source='surtidor.numero', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    operador_nombre = serializers.CharField(source='created_by.nombre', read_only=True)

    class Meta:
        model = Venta
        fields = '__all__'
        read_only_fields = ['total', 'precio_unitario', 'numero_comprobante', 'fecha_hora', 'created_by']


class RegistrarVentaSerializer(serializers.Serializer):
    surtidor_id = serializers.IntegerField()
    litros = serializers.DecimalField(max_digits=10, decimal_places=3)
    metodo_pago = serializers.ChoiceField(choices=Venta.METODOS_PAGO)
    cliente_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_surtidor_id(self, value):
        try:
            surtidor = Surtidor.objects.get(id=value, estado='ACTIVO')
        except Surtidor.DoesNotExist:
            raise serializers.ValidationError('Surtidor no encontrado o inactivo')
        return value

    def validate_litros(self, value):
        if value <= 0:
            raise serializers.ValidationError('Los litros deben ser mayor a cero')
        return value
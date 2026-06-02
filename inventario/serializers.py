from rest_framework import serializers
from .models import Tanque, DescargaCombustible


class TanqueSerializer(serializers.ModelSerializer):
    porcentaje_nivel = serializers.ReadOnlyField()
    en_alerta = serializers.ReadOnlyField()
    tipo_combustible_nombre = serializers.CharField(
        source='tipo_combustible.get_tipo_display', read_only=True
    )
    sucursal_nombre = serializers.CharField(
        source='sucursal.nombre', read_only=True
    )

    class Meta:
        model = Tanque
        fields = [
            'id', 'sucursal', 'sucursal_nombre', 'tipo_combustible',
            'tipo_combustible_nombre', 'capacidad_maxima', 'nivel_actual',
            'nivel_minimo_alerta', 'porcentaje_nivel', 'en_alerta',
            'activo', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        nivel_actual = data.get('nivel_actual', 0)
        capacidad_maxima = data.get('capacidad_maxima', 0)
        if nivel_actual > capacidad_maxima:
            raise serializers.ValidationError(
                {'nivel_actual': 'El nivel actual no puede superar la capacidad máxima.'}
            )
        return data


class DescargaCombustibleSerializer(serializers.ModelSerializer):
    registrado_por_nombre = serializers.CharField(
        source='registrado_por.nombre', read_only=True
    )
    tanque_nombre = serializers.CharField(
        source='tanque.__str__', read_only=True
    )

    class Meta:
        model = DescargaCombustible
        fields = [
            'id', 'tanque', 'tanque_nombre', 'volumen_descargado',
            'nivel_antes', 'nivel_despues', 'registrado_por',
            'registrado_por_nombre', 'observaciones', 'fecha'
        ]
        read_only_fields = ['nivel_antes', 'nivel_despues', 'registrado_por', 'fecha']
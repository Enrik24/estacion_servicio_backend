from rest_framework import serializers
from .models import Bitacora

class BitacoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bitacora
        fields = [
            'id',
            'usuario_nombre',
            'accion',
            'modulo_afectado',
            'descripcion',
            'detalles',
            'direccion_ip',
            'dispositivo',
            'creado_en'
        ]
        read_only_fields = ['id', 'creado_en']
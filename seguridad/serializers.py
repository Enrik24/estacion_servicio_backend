from rest_framework import serializers
from .models import Bitacora

class BitacoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bitacora
        fields = [
            'id',
            'usuario_nombre',
            'usuario_email',
            'usuario_rol',
            'accion',
            'modulo_afectado',
            'descripcion',
            'ip_address',
            'user_agent',
            'fecha_hora'
        ]
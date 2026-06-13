from rest_framework import serializers
from .models import EstadoSurtidor, HistorialEstadoSurtidor


class EstadoSurtidorSerializer(serializers.ModelSerializer):
    isla_numero = serializers.IntegerField(source='lado.isla.numero', read_only=True)
    lado_letra = serializers.CharField(source='lado.lado', read_only=True)
    sucursal_nombre = serializers.CharField(source='lado.isla.sucursal.nombre', read_only=True)
    reportado_por_nombre = serializers.CharField(source='reportado_por.nombre', read_only=True)
    cliente_activo_nombre = serializers.CharField(source='cliente_activo.nombre', read_only=True, allow_null=True)

    class Meta:
        model = EstadoSurtidor
        fields = [
            'id', 'lado', 'isla_numero', 'lado_letra', 'sucursal_nombre',
            'estado', 'descripcion_falla', 'reportado_por_nombre',
            'fecha_reporte', 'fecha_resolucion',
            
            # =========================================================================
            # NUEVOS CAMPOS EX_PUESTOS PARA EL CU 14 / DETALLE DEL GERENTE
            # =========================================================================
            'placa_activa',
            'monto_autorizado',
            'cliente_activo_nombre',
            # =========================================================================
        ]


class HistorialEstadoSurtidorSerializer(serializers.ModelSerializer):
    isla_numero = serializers.IntegerField(source='lado.isla.numero', read_only=True)
    lado_letra = serializers.CharField(source='lado.lado', read_only=True)
    sucursal_nombre = serializers.CharField(source='lado.isla.sucursal.nombre', read_only=True)
    cambiado_por_nombre = serializers.CharField(source='cambiado_por.nombre', read_only=True)

    class Meta:
        model = HistorialEstadoSurtidor
        fields = [
            'id', 'lado', 'isla_numero', 'lado_letra', 'sucursal_nombre',
            'estado_anterior', 'estado_nuevo', 'descripcion',
            'cambiado_por_nombre', 'fecha'
        ]
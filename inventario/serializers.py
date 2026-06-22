from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault
from .models import Tanque, DescargaCombustible, PagoProveedor, OrdenCompra


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


# ── SERIALIZER PARA EL CU 19: GESTIONAR ÓRDENES DE COMPRA ───────────────────
class OrdenCompraSerializer(serializers.ModelSerializer):
    creado_por_nombre = serializers.CharField(source='creado_por.nombre', read_only=True)
    tipo_combustible_nombre = serializers.CharField(source='tipo_combustible.get_tipo_display', read_only=True)
    
    class Meta:
        model = OrdenCompra
        fields = [
            'id', 'codigo_oc', 'proveedor', 'tipo_combustible', 'tipo_combustible_nombre',
            'volumen_solicitado', 'precio_unitario', 'total_gasto', 
            'estado', 'creado_por', 'creado_por_nombre', 'fecha_emision'
        ]
        # Agregamos codigo_oc a read_only_fields porque lo calcula el servidor
        read_only_fields = ['id', 'codigo_oc', 'total_gasto', 'creado_por', 'fecha_emision']

    def validate_volumen_solicitado(self, value):
        """ Validación: Evita registros de volumen incoherentes o vacíos """
        if value <= 0:
            raise serializers.ValidationError("El volumen solicitado debe ser mayor a 0 litros.")
        return value

    def validate_precio_unitario_compra(self, value):
        """ Validación: El costo mayorista de YPFB debe ser un valor positivo """
        if value <= 0:
            raise serializers.ValidationError("El precio unitario de compra debe ser mayor a 0 Bs.")
        return value


# ── SERIALIZER PARA EL CU 20: CONTROLAR PAGOS A PROVEEDORES ────────────────
class PagoProveedorSerializer(serializers.ModelSerializer):
    registrado_por_nombre = serializers.CharField(source='registrado_por.nombre', read_only=True)
    comprobante_digital = serializers.FileField(required=False, allow_null=True)
    
    # SOLUCIÓN CRÍTICA: Inyectar el usuario predeterminado de la sesión en la validación
    registrado_por = serializers.HiddenField(default=CurrentUserDefault())

    class Meta:
        model = PagoProveedor
        fields = [
            'id', 'orden_compra', 'monto_pagado', 'metodo_pago', 
            'nro_referencia', 'comprobante_digital', 'registrado_por', 
            'registrado_por_nombre', 'fecha_pago'
        ]
        # Quitamos 'registrado_por' de aquí porque HiddenField ya maneja su flujo de lectura/escritura seguro
        read_only_fields = ['id', 'nro_referencia', 'fecha_pago']

    def validate(self, data):
        orden = data.get('orden_compra')
        monto_ingresado = data.get('monto_pagado')

        if orden.estado != 'PENDIENTE':
            raise serializers.ValidationError({
                "orden_compra": f"La orden {orden.codigo_oc} ya no se encuentra pendiente."
            })

        if monto_ingresado != orden.total_gasto:
            raise serializers.ValidationError({
                "monto_pagado": f"El monto ingresado (Bs. {monto_ingresado}) no coincide con el costo total de la Orden de Compra (Bs. {orden.total_gasto})."
            })
        
        return data
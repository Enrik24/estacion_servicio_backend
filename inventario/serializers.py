from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault
from .models import Tanque, DescargaCombustible, PagoProveedor, OrdenCompra
from decimal import Decimal


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
    tanque_sucursal = serializers.CharField(
        source='tanque.sucursal.nombre', read_only=True
    )
    tanque_tipo_combustible = serializers.CharField(
        source='tanque.tipo_combustible.get_tipo_display', read_only=True
    )

    class Meta:
        model = DescargaCombustible
        fields = [
            'id', 'tanque', 'tanque_nombre', 'tanque_sucursal',
            'tanque_tipo_combustible', 'volumen_descargado',
            'nivel_antes', 'nivel_despues', 'registrado_por',
            'registrado_por_nombre', 'observaciones', 'fecha'
        ]
        read_only_fields = ['nivel_antes', 'nivel_despues', 'registrado_por', 'fecha']


# ── SERIALIZER PARA EL CU 19: GESTIONAR ÓRDENES DE COMPRA ───────────────────
class OrdenCompraSerializer(serializers.ModelSerializer):
    creado_por_nombre = serializers.CharField(source='creado_por.nombre', read_only=True)
    tipo_combustible_nombre = serializers.CharField(source='tipo_combustible.get_tipo_display', read_only=True)
    
    # EXTRACCIÓN DINÁMICA MEDIANTE EL USUARIO PROPIETARIO:
    sucursal_nombre = serializers.CharField(source='creado_por.sucursal.nombre', read_only=True)
    empresa_nombre = serializers.CharField(source='creado_por.sucursal.empresa.nombre', read_only=True)
    empresa_nit = serializers.CharField(source='creado_por.sucursal.empresa.nit', read_only=True)
    
    class Meta:
        model = OrdenCompra
        fields = [
            'id', 'codigo_oc', 'proveedor', 'tipo_combustible', 'tipo_combustible_nombre',
            'volumen_solicitado', 'precio_unitario', 'total_gasto', 'estado', 
            'creado_por', 'creado_por_nombre', 'fecha_emision',
            'sucursal_nombre', 'empresa_nombre', 'empresa_nit' 
        ]
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
    codigo_oc = serializers.CharField(source='orden_compra.codigo_oc', read_only=True)
    empresa_nombre = serializers.CharField(source='registrado_por.empresa.nombre', read_only=True) 
    
    orden_compra = serializers.PrimaryKeyRelatedField(queryset=OrdenCompra.objects.all())
    monto_pagado = serializers.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        model = PagoProveedor
        fields = [
            'id', 'orden_compra', 'codigo_oc', 'monto_pagado', 'metodo_pago', 
            'comprobante_digital', 'registrado_por', 'registrado_por_nombre', 
            'fecha_pago', 'empresa_nombre'
        ]
        read_only_fields = ['id', 'fecha_pago', 'registrado_por']

    def to_internal_value(self, data):
        """
        Filtro de entrada crítico: Limpia y castea las cadenas de texto del FormData 
        a los tipos nativos que Django REST Framework espera recibir.
        """
        # Hacemos una copia mutable de los datos del FormData
        data = data.copy()
        
        # 1. Limpiar el ID de la Orden de Compra
        if 'orden_compra' in data:
            try:
                data['orden_compra'] = int(str(data['orden_compra']).strip())
            except (ValueError, TypeError):
                pass  # Deja que el validador nativo lance el error si es un texto inválido
                
        # 2. Limpiar el Monto Pagado (Decimal)
        if 'monto_pagado' in data:
            try:
                # Reemplaza comas si las hubiera y limpia espacios
                monto_str = str(data['monto_pagado']).replace(',', '').strip()
                data['monto_pagado'] = float(monto_str)
            except (ValueError, TypeError):
                pass

        # 3. Solución definitiva al error de "undefined" en el método de pago
        if 'metodo_pago' in data:
            val_metodo = str(data['metodo_pago']).strip()
            if val_metodo == "undefined" or val_metodo == "":
                data['metodo_pago'] = 'TRANSFERENCIA' # Fallback seguro de tu backend

        return super().to_internal_value(data)

    def validate(self, data):
        orden = data.get('orden_compra')
        monto_ingresado = data.get('monto_pagado')

        if orden.estado != 'PENDIENTE':
            raise serializers.ValidationError({
                "orden_compra": f"La orden {orden.codigo_oc} ya no se encuentra pendiente."
            })

        # NOTA: Comparamos convirtiendo a Decimal para evitar inconsistencias de flotantes en base de datos
        if Decimal(str(monto_ingresado)) != Decimal(str(orden.total_gasto)):
            raise serializers.ValidationError({
                "monto_pagado": f"El monto ingresado (Bs. {monto_ingresado}) no coincide con el costo total de la Orden de Compra (Bs. {orden.total_gasto})."
            })
        
        return data
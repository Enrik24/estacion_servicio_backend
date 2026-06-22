from rest_framework import viewsets, status
from rest_framework import permissions as rest_permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from seguridad.models import registrar_bitacora
from usuarios import permissions
from ventas.models import TipoCombustible
from ventas.serializers import TipoCombustibleSerializer
from .models import Tanque, DescargaCombustible, PagoProveedor , OrdenCompra
from .serializers import TanqueSerializer, DescargaCombustibleSerializer, PagoProveedorSerializer, OrdenCompraSerializer
from decimal import Decimal

class TanqueViewSet(viewsets.ModelViewSet):
    serializer_class = TanqueSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Tanque.objects.all()
        if user.empresa:
            qs = Tanque.objects.filter(sucursal__empresa=user.empresa)
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                qs = qs.filter(sucursal=user.sucursal)
            return qs
        return Tanque.objects.none()

    def perform_create(self, serializer):
        tanque = serializer.save()
        registrar_bitacora(
            self.request,
            accion='CREAR',
            modulo='Inventario',
            descripcion=f'Creó tanque de {tanque.tipo_combustible.get_tipo_display()} en {tanque.sucursal.nombre} con capacidad {tanque.capacidad_maxima} Lt',
        )

    def perform_update(self, serializer):
        tanque = serializer.save()
        registrar_bitacora(
            self.request,
            accion='EDITAR',
            modulo='Inventario',
            descripcion=f'Actualizó tanque de {tanque.tipo_combustible.get_tipo_display()} en {tanque.sucursal.nombre}',
        )

    @action(detail=True, methods=['post'])
    def registrar_descarga(self, request, pk=None):
        tanque = self.get_object()
        volumen = request.data.get('volumen_descargado')
        observaciones = request.data.get('observaciones', '')

        if not volumen:
            return Response({'error': 'volumen_descargado es requerido'}, status=400)

        volumen = float(volumen)
        if volumen <= 0:
            return Response({'error': 'El volumen debe ser mayor a 0'}, status=400)

        

        nivel_antes = tanque.nivel_actual
        volumen = Decimal(str(volumen))
        nivel_despues = nivel_antes + volumen

        if nivel_despues > tanque.capacidad_maxima:
            return Response({
                'error': f'El volumen excede la capacidad del tanque. Disponible: {tanque.capacidad_maxima - nivel_antes} Lt'
            }, status=400)

        with transaction.atomic():
            tanque.nivel_actual = nivel_despues
            tanque.save()

            descarga = DescargaCombustible.objects.create(
                tanque=tanque,
                volumen_descargado=volumen,
                nivel_antes=nivel_antes,
                nivel_despues=nivel_despues,
                registrado_por=request.user,
                observaciones=observaciones,
            )
         # Verificar si está en nivel crítico y notificar
        if tanque.en_alerta:
            from utils.onesignal import notificar_nivel_critico
            notificar_nivel_critico(tanque)
        registrar_bitacora(
            request,
            accion='CREAR',
            modulo='Inventario',
            descripcion=f'Registró descarga de {volumen} Lt de {tanque.tipo_combustible.get_tipo_display()} en {tanque.sucursal.nombre}. Nivel: {nivel_antes} → {nivel_despues} Lt',
        )

        return Response({
            'mensaje': f'Descarga registrada correctamente. Nuevo nivel: {nivel_despues} Lt',
            'tanque': TanqueSerializer(tanque).data,
            'descarga': DescargaCombustibleSerializer(descarga).data,
        })

    @action(detail=True, methods=['patch'])
    def ampliar_capacidad(self, request, pk=None):
        tanque = self.get_object()
        nueva_capacidad = request.data.get('capacidad_maxima')

        if not nueva_capacidad:
            return Response({'error': 'capacidad_maxima es requerida'}, status=400)

        nueva_capacidad = float(nueva_capacidad)
        if nueva_capacidad <= float(tanque.capacidad_maxima):
            return Response({'error': 'La nueva capacidad debe ser mayor a la actual'}, status=400)

        capacidad_anterior = tanque.capacidad_maxima
        tanque.capacidad_maxima = nueva_capacidad
        nivel_minimo = nueva_capacidad * 0.20
        tanque.nivel_minimo_alerta = nivel_minimo
        tanque.save()

        registrar_bitacora(
            request,
            accion='EDITAR',
            modulo='Inventario',
            descripcion=f'Amplió capacidad de tanque {tanque.tipo_combustible.get_tipo_display()} en {tanque.sucursal.nombre}: {capacidad_anterior} → {nueva_capacidad} Lt',
        )

        return Response({
            'mensaje': 'Capacidad ampliada correctamente',
            'tanque': TanqueSerializer(tanque).data,
        })


class DescargaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DescargaCombustibleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return DescargaCombustible.objects.all()
        if user.empresa:
            qs = DescargaCombustible.objects.filter(
                tanque__sucursal__empresa=user.empresa
            )
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                qs = qs.filter(tanque__sucursal=user.sucursal)
            return qs
        return DescargaCombustible.objects.none()
    
# ── CONTROLLER PARA EL CU 19: ÓRDENES DE COMPRA ─────────────────────────────
class OrdenCompraViewSet(viewsets.ModelViewSet):
    serializer_class = OrdenCompraSerializer
    permission_classes = [rest_permissions.IsAuthenticated]

    def get_queryset(self):
        usuario_actual = self.request.user
        
        if usuario_actual.is_superuser:
            return OrdenCompra.objects.all().order_by('-fecha_emision')
            
        if not usuario_actual.empresa:
            return OrdenCompra.objects.none()
            
        # FILTRO DIRECTO MULTITENANT: Muestra las órdenes de la empresa del usuario
        return OrdenCompra.objects.filter(
            creado_por__empresa=usuario_actual.empresa
        ).order_by('-fecha_emision')

    def perform_create(self, serializer):
        # Al guardar, Django ya sabe quién la crea
        serializer.save(creado_por=self.request.user)


# ── CONTROLLER PARA EL CU 20: PAGOS A PROVEEDORES (PREPAGO) ────────────────
class PagoProveedorViewSet(viewsets.ModelViewSet):
    serializer_class = PagoProveedorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        usuario_actual = self.request.user
        if usuario_actual.is_superuser:
            return PagoProveedor.objects.all().order_by('-fecha_pago')
        if not usuario_actual.empresa:
            return PagoProveedor.objects.none()
        return PagoProveedor.objects.filter(registrado_por__empresa=usuario_actual.empresa).order_by('-fecha_pago')

    # === INTERCEPCIÓN FORZADA DE TIPOS EN LA VISTA ===
    def create(self, request, *args, **kwargs):
        # 1. DEPURACIÓN DE EMERGENCIA: Ver qué diablos está mandando React
        print("*" * 50)
        print("TIPO DE DATA RECIBIDA:", type(request.data))
        print("CONTENIDO DE REQUEST.DATA:", request.data)
        print("*" * 50)

        # 2. Copiamos los datos para limpiarlos
        data = request.data.copy()
        
        # Extracción segura: Si viene como lista (QueryDict de FormData), sacamos el primer elemento
        def limpiar_valor(campo):
            valor = data.get(campo)
            if isinstance(valor, list) and len(valor) > 0:
                valor = valor[0]
            return str(valor).strip() if valor is not None else None

        oc_val = limpiar_valor('orden_compra')
        monto_val = limpiar_valor('monto_pagado')
        metodo_val = limpiar_valor('metodo_pago')

        # 3. Forzar conversión destructiva (Si falla, asigna None para que DRF de un error limpio, no un crash de tipos)
        if oc_val:
            try:
                data['orden_compra'] = int(oc_val)
            except (ValueError, TypeError):
                pass

        if monto_val:
            try:
                data['monto_pagado'] = float(monto_val)
            except (ValueError, TypeError):
                pass

        if metodo_val in ['undefined', '', None, 'null']:
            data['metodo_pago'] = 'TRANSFERENCIA'
        else:
            data['metodo_pago'] = metodo_val

        # 4. Validar y guardar
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        # Inyectamos el usuario de la sesión (Bryan)
        serializer.save(registrado_por=self.request.user)
class TipoCombustibleViewSet(viewsets.ModelViewSet):
    queryset = TipoCombustible.objects.filter(activo=True)
    serializer_class = TipoCombustibleSerializer
    permission_classes = [rest_permissions.IsAuthenticated]

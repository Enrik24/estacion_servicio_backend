from rest_framework import viewsets, status
from rest_framework import permissions as rest_permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from seguridad.models import registrar_bitacora
from usuarios import permissions
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
    """
    Controlador de la API para gestionar Órdenes de Compra (CU 19).
    Permite planificar los pedidos a YPFB y controlar los cupos de la ANH.
    """
    queryset = OrdenCompra.objects.all().order_by('-fecha_emision')
    serializer_class = OrdenCompraSerializer
    permission_classes = [rest_permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """ Inyecta automáticamente el usuario logueado como el creador de la OC """
        serializer.save(
            creado_por=self.request.user,
            estado='PENDIENTE' 
        )


# ── CONTROLLER PARA EL CU 20: PAGOS A PROVEEDORES (PREPAGO) ────────────────
class PagoProveedorViewSet(viewsets.ModelViewSet):
    """
    Controlador de la API para controlar Pagos a Proveedores (CU 20).
    Registra el recibo del banco y activa la orden para el recojo de combustible.
    """
    queryset = PagoProveedor.objects.all().order_by('-fecha_pago')
    serializer_class = PagoProveedorSerializer
    permission_classes = [rest_permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """
        Guarda el pago inyectando el usuario logueado y cambia 
        el estado de la Orden de Compra de forma atómica.
        """
        # 1. Persistir el Pago a Proveedor inyectando el usuario del token JWT
        pago = serializer.save()
        
        # 2. DISPARADOR AUTOMÁTICO (Regla de Negocio Unificada)
        orden_compra = pago.orden_compra
        orden_compra.estado = 'PAGADA'
        orden_compra.save()
        
        # Guardamos la orden en el contexto del serializer para usarla en el método create
        self.orden_compra_codigo = orden_compra.codigo_oc

    def create(self, request, *args, **kwargs):
        """
        Sobrescribe el método de creación estándar para envolver la operación
        en una transacción atómica de Base de Datos (Seguridad Crítica).
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Bloque atómico: Si algo falla adentro, se hace un Rollback completo
        with transaction.atomic():
            self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                "mensaje": f"Prepago de la orden {getattr(self, 'orden_compra_codigo', '')} conciliado. Logística de combustible autorizada.",
                "datos": serializer.data
            },
            status=status.HTTP_201_CREATED,
            headers=headers
        )
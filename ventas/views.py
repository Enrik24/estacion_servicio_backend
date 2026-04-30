from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
import uuid

from .models import Surtidor, Turno, Cliente, Venta
from .serializers import (
    SurtidorSerializer, TurnoSerializer, 
    ClienteSerializer, VentaSerializer, RegistrarVentaSerializer
)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora
from rest_framework.exceptions import ValidationError

class SurtidorViewSet(viewsets.ModelViewSet):
    queryset = Surtidor.objects.all()
    serializer_class = SurtidorSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'surtidores.ver'

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='surtidores.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='surtidores.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='surtidores.eliminar')]
        return super().get_permissions()


class TurnoViewSet(viewsets.ModelViewSet):
    queryset = Turno.objects.all()
    serializer_class = TurnoSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'turnos.ver'

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='turnos.abrir')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='turnos.cerrar')]
        return super().get_permissions()

    def perform_create(self, serializer):
        # Verifica que el operador no tenga un turno abierto ya
        turno_abierto = Turno.objects.filter(
            operador=self.request.user,
            estado='ABIERTO'
        ).exists()
        if turno_abierto:
            raise ValidationError('Ya tienes un turno abierto')
        serializer.save(operador=self.request.user)

        Bitacora.objects.create(
            usuario=self.request.user,
            usuario_email=self.request.user.email,
            usuario_nombre=self.request.user.nombre,
            accion='CREAR',
            estado='EXITO',
            ip_address=getattr(self.request, 'ip_address', None),
            user_agent=getattr(self.request, 'user_agent', '')[:500]
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, HasPermiso])
    def cerrar(self, request, pk=None):
        turno = self.get_object()

        if turno.estado == 'CERRADO':
            return Response(
                {'error': 'Este turno ya está cerrado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if turno.operador != request.user and not request.user.is_superuser:
            return Response(
                {'error': 'No puedes cerrar el turno de otro operador'},
                status=status.HTTP_403_FORBIDDEN
            )

        turno.estado = 'CERRADO'
        turno.fecha_cierre = timezone.now()
        turno.monto_final = request.data.get('monto_final', 0)
        turno.observaciones = request.data.get('observaciones', '')
        turno.save()

        Bitacora.objects.create(
            usuario=request.user,
            usuario_email=request.user.email,
            usuario_nombre=request.user.nombre,
            accion='EDITAR',
            estado='EXITO',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )

        serializer = TurnoSerializer(turno)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mi_turno(self, request):
        # Devuelve el turno abierto del operador logueado
        try:
            turno = Turno.objects.get(operador=request.user, estado='ABIERTO')
            serializer = TurnoSerializer(turno)
            return Response(serializer.data)
        except Turno.DoesNotExist:
            return Response({'turno': None})


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.filter(activo=True)
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'clientes.ver'

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='clientes.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='clientes.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='clientes.eliminar')]
        return super().get_permissions()


class VentaViewSet(viewsets.ModelViewSet):
    queryset = Venta.objects.all()
    serializer_class = VentaSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'ventas.ver'

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='ventas.registrar')]
        return super().get_permissions()

    @transaction.atomic
    def create(self, request):
        serializer = RegistrarVentaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Verifica que el operador tenga un turno abierto
        try:
            turno = Turno.objects.get(operador=request.user, estado='ABIERTO')
        except Turno.DoesNotExist:
            return Response(
                {'error': 'No tienes un turno abierto. Abre un turno antes de registrar ventas'},
                status=status.HTTP_400_BAD_REQUEST
            )

        surtidor = Surtidor.objects.get(id=data['surtidor_id'])

        # Calcula el total
        litros = data['litros']
        precio_unitario = surtidor.precio_litro
        total = litros * precio_unitario

        # Verifica límite de crédito si el método de pago es crédito fleet
        cliente = None
        if data.get('cliente_id'):
            try:
                cliente = Cliente.objects.get(id=data['cliente_id'], activo=True)
                if data['metodo_pago'] == 'CREDITO_FLEET':
                    if total > cliente.saldo_credito:
                        return Response(
                            {'error': f'Saldo de crédito insuficiente. Disponible: Bs. {cliente.saldo_credito}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    # Descuenta el saldo de crédito
                    cliente.saldo_credito -= total
                    cliente.save()
            except Cliente.DoesNotExist:
                return Response(
                    {'error': 'Cliente no encontrado'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Genera número de comprobante único
        numero_comprobante = f"VTA-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        # Registra la venta
        venta = Venta.objects.create(
            turno=turno,
            surtidor=surtidor,
            cliente=cliente,
            litros=litros,
            precio_unitario=precio_unitario,
            total=total,
            metodo_pago=data['metodo_pago'],
            numero_comprobante=numero_comprobante,
            created_by=request.user
        )

        Bitacora.objects.create(
            usuario=request.user,
            usuario_email=request.user.email,
            usuario_nombre=request.user.nombre,
            accion='CREAR',
            estado='EXITO',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )

        return Response(VentaSerializer(venta).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, HasPermiso])
    def anular(self, request, pk=None):
        venta = self.get_object()

        if venta.estado == 'ANULADA':
            return Response(
                {'error': 'Esta venta ya está anulada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        venta.estado = 'ANULADA'
        venta.save()

        # Si era crédito fleet devuelve el saldo al cliente
        if venta.metodo_pago == 'CREDITO_FLEET' and venta.cliente:
            venta.cliente.saldo_credito += venta.total
            venta.cliente.save()

        Bitacora.objects.create(
            usuario=request.user,
            usuario_email=request.user.email,
            usuario_nombre=request.user.nombre,
            accion='ELIMINAR',
            estado='EXITO',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )

        return Response({'mensaje': 'Venta anulada correctamente'})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mi_turno_ventas(self, request):
        # Devuelve las ventas del turno abierto del operador logueado
        try:
            turno = Turno.objects.get(operador=request.user, estado='ABIERTO')
            ventas = Venta.objects.filter(turno=turno, estado='COMPLETADA')
            serializer = VentaSerializer(ventas, many=True)
            return Response(serializer.data)
        except Turno.DoesNotExist:
            return Response({'ventas': [], 'mensaje': 'No tienes turno abierto'})
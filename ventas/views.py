from urllib import request

from rest_framework import viewsets, status
from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
import uuid

from .models import Sucursal, Isla, Lado, TipoCombustible, Turno, Cliente, Venta,Vehiculo
from .serializers import (
    SucursalSerializer, IslaSerializer, LadoSerializer, TipoCombustibleSerializer,
    TurnoSerializer, ClienteSerializer, VentaSerializer, RegistrarVentaSerializer, VehiculoSerializer, RegistrarClienteVehiculoSerializer
)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora


class IslaViewSet(viewsets.ModelViewSet):
    queryset = Isla.objects.prefetch_related('lados').all()
    serializer_class = IslaSerializer
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


class LadoViewSet(viewsets.ModelViewSet):
    queryset = Lado.objects.select_related('isla').all()
    serializer_class = LadoSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'surtidores.ver'


class TipoCombustibleViewSet(viewsets.ModelViewSet):
    queryset = TipoCombustible.objects.filter(activo=True)
    serializer_class = TipoCombustibleSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'surtidores.ver'


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
            usuario_rol=self.request.user.nombre_rol,
            accion='CREAR',
            estado='EXITO',
            modulo_afectado='Ventas',
            descripcion=f'Abrió turno en Isla {serializer.instance.isla.numero}',
            ip_address=getattr(self.request, 'ip_address', None),
            user_agent=getattr(self.request, 'user_agent', '')[:500]
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cerrar(self, request, pk=None):
        turno = self.get_object()

        if turno.estado == 'CERRADO':
            return Response({'error': 'Este turno ya está cerrado'}, status=status.HTTP_400_BAD_REQUEST)
        if turno.operador != request.user and not request.user.is_superuser:
            return Response({'error': 'No puedes cerrar el turno de otro operador'}, status=status.HTTP_403_FORBIDDEN)

        turno.estado = 'CERRADO'
        turno.fecha_cierre = timezone.now()
        turno.monto_final = request.data.get('monto_final', 0)
        turno.observaciones = request.data.get('observaciones', '')
        turno.save()

        Bitacora.objects.create(
            usuario=request.user,
            usuario_email=request.user.email,
            usuario_nombre=request.user.nombre,
            usuario_rol=request.user.nombre_rol,
            accion='EDITAR',
            estado='EXITO',
            modulo_afectado='Ventas',
            descripcion=f'Cerró turno {turno.id} en Isla {turno.isla.numero}',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )

        return Response(TurnoSerializer(turno).data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mi_turno(self, request):
        try:
            turno = Turno.objects.get(operador=request.user, estado='ABIERTO')
            return Response(TurnoSerializer(turno).data)
        except Turno.DoesNotExist:
            return Response({'turno': None})
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def resumen(self, request):
        fecha = request.query_params.get('fecha', None)
        horario = request.query_params.get('horario', None)

        turnos = Turno.objects.select_related('operador', 'isla').all()

        if fecha:
            turnos = turnos.filter(fecha_apertura__date=fecha)
        else:
            turnos = turnos.filter(fecha_apertura__date=timezone.now().date())

        if horario:
            turnos = turnos.filter(horario=horario)

        data = []
        for turno in turnos:
            ventas = Venta.objects.filter(turno=turno, estado='COMPLETADA')
            total_ventas = sum(v.total for v in ventas)
            total_litros = sum(v.litros for v in ventas)
            data.append({
                'id': turno.id,
                'operador': turno.operador.nombre,
                'isla': turno.isla.numero,
                'horario': turno.get_horario_display(),
                'horario_codigo': turno.horario,
                'estado': turno.estado,
                'fecha_apertura': turno.fecha_apertura,
                'fecha_cierre': turno.fecha_cierre,
                'total_ventas': float(total_ventas),
                'total_litros': float(total_litros),
                'cantidad_ventas': ventas.count(),
            })

        return Response(data)

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

        try:
            turno = Turno.objects.get(operador=request.user, estado='ABIERTO')
        except Turno.DoesNotExist:
            return Response({'error': 'No tienes un turno abierto'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lado = Lado.objects.get(id=data['lado_id'], isla=turno.isla, activo=True)
        except Lado.DoesNotExist:
            return Response({'error': 'Lado no válido para tu isla asignada'}, status=status.HTTP_400_BAD_REQUEST)

        tipo_combustible = TipoCombustible.objects.get(id=data['tipo_combustible_id'])
        precio_unitario = tipo_combustible.precio_litro

        es_lleno = data.get('es_lleno', False)

        if es_lleno:
            # Para "lleno" el total lo define el surtidor al terminar,
            # por ahora registramos litros=0 y total=0 como despacho abierto.
            # Si quieres bloquearlo puedes retornar error aquí hasta tener integración con surtidor.
            litros = None
            total = None
        else:
            monto_bs = data['monto_bs']
            litros = round(monto_bs / precio_unitario, 3)
            total = monto_bs

        cliente = None
        if data.get('cliente_id'):
            try:
                cliente = Cliente.objects.get(id=data['cliente_id'], activo=True)
                if data['metodo_pago'] == 'CREDITO_FLEET' and total is not None:
                    if total > cliente.saldo_credito:
                        return Response(
                            {'error': f'Saldo insuficiente. Disponible: Bs. {cliente.saldo_credito}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    cliente.saldo_credito -= total
                    cliente.save()
            except Cliente.DoesNotExist:
                return Response({'error': 'Cliente no encontrado'}, status=status.HTTP_400_BAD_REQUEST)

        numero_comprobante = f"VTA-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        venta = Venta.objects.create(
            turno=turno,
            lado=lado,
            tipo_combustible=tipo_combustible,
            cliente=cliente,
            litros=litros if litros is not None else 0,
            precio_unitario=precio_unitario,
            total=total if total is not None else 0,
            metodo_pago=data['metodo_pago'],
            numero_comprobante=numero_comprobante,
            created_by=request.user
        )

        desc = f'Lleno - {tipo_combustible.get_tipo_display()}' if es_lleno else \
            f'Registró venta de {litros} Lt de {tipo_combustible.get_tipo_display()} - Bs. {total}'

        Bitacora.objects.create(
            usuario=request.user,
            usuario_email=request.user.email,
            usuario_nombre=request.user.nombre,
            usuario_rol=request.user.nombre_rol,
            accion='CREAR',
            estado='EXITO',
            modulo_afectado='Ventas',
            descripcion=desc,
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )

        return Response(VentaSerializer(venta).data, status=status.HTTP_201_CREATED)
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def anular(self, request, pk=None):
        venta = self.get_object()
        if venta.estado == 'ANULADA':
            return Response({'error': 'Esta venta ya está anulada'}, status=status.HTTP_400_BAD_REQUEST)
        venta.estado = 'ANULADA'
        venta.save()
        if venta.metodo_pago == 'CREDITO_FLEET' and venta.cliente:
            venta.cliente.saldo_credito += venta.total
            venta.cliente.save()
        return Response({'mensaje': 'Venta anulada correctamente'})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mi_turno_ventas(self, request):
        try:
            turno = Turno.objects.get(operador=request.user, estado='ABIERTO')
            ventas = Venta.objects.filter(turno=turno, estado='COMPLETADA')
            return Response(VentaSerializer(ventas, many=True).data)
        except Turno.DoesNotExist:
            return Response({'ventas': [], 'mensaje': 'No tienes turno abierto'})
class VehiculoViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def buscar_placa(self, request):
        placa = request.query_params.get('placa', '').upper().strip()
        if not placa:
            return Response({'error': 'Debes ingresar una placa'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            vehiculo = Vehiculo.objects.select_related('cliente').get(placa=placa, activo=True)
            return Response({
                'encontrado': True,
                'vehiculo': VehiculoSerializer(vehiculo).data
            })
        except Vehiculo.DoesNotExist:
            return Response({'encontrado': False})

    @action(detail=False, methods=['post'])
    def registrar_cliente_vehiculo(self, request):
        serializer = RegistrarClienteVehiculoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        with transaction.atomic():
            cliente = Cliente.objects.create(
                nombre=data['nombre'],
                nit=data.get('nit') or None,
                telefono=data.get('telefono') or None,
            )
            vehiculo = Vehiculo.objects.create(
                cliente=cliente,
                placa=data['placa'],
                marca=data.get('marca') or None,
                modelo=data.get('modelo') or None,
                color=data.get('color') or None,
            )
        return Response({
            'encontrado': True,
            'vehiculo': VehiculoSerializer(vehiculo).data
        }, status=status.HTTP_201_CREATED)
class SucursalViewSet(viewsets.ModelViewSet):
    queryset = Sucursal.objects.all()
    serializer_class = SucursalSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'sucursales.ver'

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='sucursales.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='sucursales.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='sucursales.eliminar')]
        return super().get_permissions()

    def perform_create(self, serializer):
        sucursal = serializer.save()
        # Crear islas y lados automáticamente
        for i in range(1, sucursal.cantidad_islas + 1):
            isla = Isla.objects.create(
                numero=i,
                sucursal=sucursal,
                estado='ACTIVO'
            )
            Lado.objects.create(isla=isla, lado='A', activo=True)
            Lado.objects.create(isla=isla, lado='B', activo=True)        
        
"""ViewSets para la aplicación de ventas y POS.

Define los ViewSets para gestionar islas, lados, tipos de combustible, turnos,
clientes, ventas, vehículos, sucursales y consolidación de caja.
"""

from rest_framework import viewsets, status
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction, IntegrityError
import uuid
import re

from .models import Turno, Cliente, Venta, Isla, Lado, TipoCombustible, Sucursal, Vehiculo, CompraCombustible

from .serializers import (
    SucursalSerializer, IslaSerializer, LadoSerializer, TipoCombustibleSerializer,
    TurnoSerializer, ClienteSerializer, VentaSerializer, RegistrarVentaSerializer,
    TicketVentaSerializer, VehiculoSerializer, RegistrarClienteVehiculoSerializer,
    ConsolidacionCajaSerializer, CompraCombustibleSerializer

)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora
from usuarios.models import Usuario, Rol
from .client_linking import resolve_cliente_for_sale, resolve_cliente_for_usuario


class PreciosCombustibleView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        combustibles = TipoCombustible.objects.filter(activo=True).order_by('tipo')
        data = []
        for combustible in combustibles:
            unidad = 'mm3' if combustible.tipo == 'GNV' else 'Lt'
            data.append({
                'codigo': combustible.tipo,
                'nombre': combustible.get_tipo_display(),
                'precio_unitario': str(combustible.precio_litro),
                'unidad': unidad,
                'updated_at': combustible.updated_at,
            })
        return Response(data)

class ComprasViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):
    serializer_class = CompraCombustibleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CompraCombustible.objects.filter(
            created_by=self.request.user
        ).select_related('tipo_combustible')

    def list(self, request, *args, **kwargs):
        items = []
        seen = set()

        compras = self.get_queryset()
        compras_data = CompraCombustibleSerializer(compras, many=True, context={'request': request}).data
        for compra in compras_data:
            key = f"compra:{compra.get('id')}"
            if key in seen:
                continue
            seen.add(key)
            items.append(compra)

        cliente = resolve_cliente_for_usuario(
            request.user,
            create_if_missing=(
                (not request.user.is_staff) and
                (not request.user.is_superuser) and
                (request.user.sucursal_id is None)
            ),
        )

        ventas = Venta.objects.filter(
            created_by=request.user,
            estado='COMPLETADA',
        ).select_related('tipo_combustible')

        if cliente is not None:
            ventas = (ventas | Venta.objects.filter(
                cliente_id=cliente.id,
                estado='COMPLETADA',
            ).select_related('tipo_combustible'))

        for venta in ventas:
            unidad = 'mm3' if venta.tipo_combustible.tipo == 'GNV' else 'Lt'
            observacion = ''
            key = f"venta:{venta.id}"
            if key in seen:
                continue
            seen.add(key)
            items.append({
                'id': venta.id,
                'tipo_combustible': venta.tipo_combustible.tipo,
                'cantidad': str(venta.litros),
                'unidad': unidad,
                'precio_unitario': str(venta.precio_unitario),
                'total': str(venta.total),
                'fecha_hora': venta.fecha_hora.isoformat(),
                'observacion': observacion,
                'combustible_detalle': {'nombre': venta.tipo_combustible.get_tipo_display()},
            })

        items.sort(key=lambda x: x.get('fecha_hora', ''), reverse=True)
        page = self.paginate_queryset(items)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(items)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        compra = serializer.save()
        return Response(CompraCombustibleSerializer(compra, context={'request': request}).data, status=status.HTTP_201_CREATED)

class IslaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar islas con lados activos y control de permisos."""
    queryset = Isla.objects.prefetch_related('lados').all()
    serializer_class = IslaSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'surtidores.ver'

    def get_permissions(self):
        """Asigna permisos específicos según la acción."""
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='surtidores.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='surtidores.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='surtidores.eliminar')]
        return super().get_permissions()


class LadoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar lados de islas con referencia a su isla."""
    queryset = Lado.objects.select_related('isla').all()
    serializer_class = LadoSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'surtidores.ver'


class TipoCombustibleViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar tipos de combustible activos."""
    queryset = TipoCombustible.objects.filter(activo=True)
    serializer_class = TipoCombustibleSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'surtidores.ver'


class TurnoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar turnos de operadores con apertura y cierre."""
    queryset = Turno.objects.all()
    serializer_class = TurnoSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'turnos.ver'

    def get_permissions(self):
        """Asigna permisos específicos según la acción."""
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='turnos.abrir')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='turnos.cerrar')]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Crea un turno para el operador actual validando que no tenga uno abierto."""
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
            modulo_afectado='Venta y POS',
            descripcion='Apertura de turno',
            ip_address=getattr(self.request, 'ip_address', None),
            user_agent=getattr(self.request, 'user_agent', '')[:500]
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cerrar(self, request, pk=None):
        """Cierra un turno registrando el monto final y observaciones."""
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
            modulo_afectado='Venta y POS',
            descripcion='Cierre de turno',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )

        return Response(TurnoSerializer(turno).data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mi_turno(self, request):
        """Obtiene el turno abierto del usuario actual."""
        try:
            turno = Turno.objects.get(operador=request.user, estado='ABIERTO')
            return Response(TurnoSerializer(turno).data)
        except Turno.DoesNotExist:
            return Response({'turno': None})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def resumen(self, request):
        """Obtiene resumen de turnos con detalles de ventas agrupadas por tipo de combustible."""
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

            # Litros agrupados por tipo de combustible
            litros_por_tipo = {}
            for v in ventas:
                tipo = v.tipo_combustible.get_tipo_display()
                unidad = 'mm3' if v.tipo_combustible.tipo == 'GNV' else 'Lt'
                key = f"{tipo}"
                if key not in litros_por_tipo:
                    litros_por_tipo[key] = {'cantidad': 0, 'unidad': unidad}
                litros_por_tipo[key]['cantidad'] += float(v.litros)

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
                'litros_por_tipo': litros_por_tipo,
            })

        return Response(data)

class ClienteViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar clientes activos con creación automática de credenciales."""
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'clientes.ver'

    def get_queryset(self):
        qs = Cliente.objects.filter(activo=True).select_related('usuario').order_by(
            '-usuario_id',
            '-email',
            'nombre',
            'id',
        )
        # Multi-tenant: solo clientes con ventas en la sucursal del usuario
        sucursal_id = getattr(self.request.user, 'sucursal_id', None)
        if sucursal_id:
            ids_clientes = Venta.objects.filter(
                turno__sucursal_id=sucursal_id,
                cliente__isnull=False,
            ).values_list('cliente_id', flat=True).distinct()
            qs = qs.filter(id__in=ids_clientes)
        return qs

    def get_permissions(self):
        """Asigna permisos específicos según la acción."""
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='clientes.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='clientes.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='clientes.eliminar')]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """Crea un nuevo cliente e genera credenciales automáticas si se proporciona CI."""
        ci = request.data.get('ci', '').strip()

        # Crear el cliente normalmente
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cliente = serializer.save()

        # Crear credenciales automáticas si viene el CI
        credenciales = None
        if ci:
            try:
                # Generar email desde el nombre
                nombre_limpio = cliente.nombre.strip().lower()
                nombre_limpio = re.sub(r'[^a-záéíóúñ\s]', '', nombre_limpio)
                partes = nombre_limpio.split()
                primer_nombre = partes[0] if partes else 'cliente'
                email_generado = f"{primer_nombre}@estacion.com"

                # Si ya existe ese email agregar número
                base_email = email_generado
                contador = 1
                while Usuario.objects.filter(email=email_generado).exists():
                    email_generado = f"{base_email.replace('@', f'{contador}@')}"
                    contador += 1

                # Obtener rol Cliente
                rol_cliente = Rol.objects.filter(
                    nombre__iexact='cliente'
                ).first()

                # Crear usuario
                usuario = Usuario.objects.create_user(
                    email=email_generado,
                    nombre=cliente.nombre,
                    password=ci,
                    created_by=request.user
                )

                if rol_cliente:
                    usuario.roles.add(rol_cliente)

                cliente.usuario = usuario

                credenciales = {
                    'email': email_generado,
                    'password': ci,
                }

                if not cliente.email:
                    cliente.email = email_generado
                    cliente.save(update_fields=['email', 'usuario'])
                else:
                    cliente.save(update_fields=['usuario'])

                # Registrar en bitácora
                Bitacora.objects.create(
                    usuario=request.user,
                    usuario_email=request.user.email,
                    usuario_nombre=request.user.nombre,
                    usuario_rol=request.user.nombre_rol,
                    accion='CREAR',
                    estado='EXITO',
                    modulo_afectado='Usuarios',
                    descripcion=f'Credenciales creadas automáticamente para cliente {cliente.nombre}',
                    ip_address=getattr(request, 'ip_address', None),
                    user_agent=getattr(request, 'user_agent', '')[:500]
                )

            except Exception as e:
                # Si falla la creación de credenciales no afecta el registro del cliente
                credenciales = {'error': str(e)}

        response_data = serializer.data
        if credenciales:
            response_data = dict(serializer.data)
            response_data['credenciales'] = credenciales

        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, HasPermiso])
    def por_sucursal(self, request):
        """Obtiene clientes filtrados por sucursal."""
        sucursal_id = request.query_params.get('sucursal_id')
        if not sucursal_id:
            return Response({'error': 'Debes proporcionar sucursal_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        clientes = self.queryset.filter(sucursal_id=sucursal_id)
        serializer = self.get_serializer(clientes, many=True)
        return Response(serializer.data)


class VentaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar ventas con validación de turno, lado y combustible."""
    queryset = Venta.objects.all()
    serializer_class = VentaSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'ventas.ver'

    def get_permissions(self):
        """Asigna permisos específicos según la acción."""
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='ventas.registrar')]
        return super().get_permissions()

    @transaction.atomic
    def create(self, request):
        """Registra una nueva venta con validación de datos y actualización de crédito."""
        serializer = RegistrarVentaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        client_request_id = data.get('client_request_id')
        if client_request_id:
            existente = Venta.objects.filter(created_by=request.user, client_request_id=client_request_id).first()
            if existente:
                return Response(VentaSerializer(existente).data, status=status.HTTP_200_OK)

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
                cliente = resolve_cliente_for_sale(cliente)
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

        try:
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
                created_by=request.user,
                client_request_id=client_request_id,
            )
        except IntegrityError:
            if client_request_id:
                existente = Venta.objects.filter(created_by=request.user, client_request_id=client_request_id).first()
                if existente:
                    return Response(VentaSerializer(existente).data, status=status.HTTP_200_OK)
            raise

        desc = f'Lleno - {tipo_combustible.get_tipo_display()}' if es_lleno else \
            f'Registró venta de {litros} Lt de {tipo_combustible.get_tipo_display()} - Bs. {total}'

        Bitacora.objects.create(
            usuario=request.user,
            usuario_email=request.user.email,
            usuario_nombre=request.user.nombre,
            usuario_rol=request.user.nombre_rol,
            accion='CREAR',
            estado='EXITO',
            modulo_afectado='Venta y POS',
            descripcion='Registro de venta',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )

        return Response(VentaSerializer(venta).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def anular(self, request, pk=None):
        """Anula una venta y revierte el crédito si aplica."""
        venta = self.get_object()
        if venta.estado == 'ANULADA':
            return Response({'error': 'Esta venta ya está anulada'}, status=status.HTTP_400_BAD_REQUEST)
        venta.estado = 'ANULADA'
        venta.save()
        if venta.metodo_pago == 'CREDITO_FLEET' and venta.cliente:
            venta.cliente.saldo_credito += venta.total
            venta.cliente.save()

        Bitacora.objects.create(
            usuario=request.user,
            usuario_email=request.user.email,
            usuario_nombre=request.user.nombre,
            usuario_rol=request.user.nombre_rol,
            accion='ELIMINAR',
            estado='EXITO',
            modulo_afectado='Venta y POS',
            descripcion='Anulación de venta',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )

        return Response({'mensaje': 'Venta anulada correctamente'})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mi_turno_ventas(self, request):
        """Obtiene las ventas completadas del turno abierto del usuario."""
        try:
            turno = Turno.objects.get(operador=request.user, estado='ABIERTO')
            ventas = Venta.objects.filter(turno=turno, estado='COMPLETADA')
            return Response(VentaSerializer(ventas, many=True).data)
        except Turno.DoesNotExist:
            return Response({'ventas': [], 'mensaje': 'No tienes turno abierto'})

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def ticket(self, request, pk=None):
        """Obtiene el ticket/comprobante de una venta específica."""
        venta = self.get_object()
        serializer = TicketVentaSerializer(venta)
        return Response(serializer.data)
class VehiculoViewSet(GenericViewSet):
    """ViewSet para gestionar vehículos y búsqueda por placa."""
    queryset = Vehiculo.objects.select_related('cliente').all()
    serializer_class = VehiculoSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def buscar_placa(self, request):
        """Busca un vehículo por su número de placa."""
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

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def registrar_cliente_vehiculo(self, request):
        """Registra un nuevo cliente con su vehículo e crea credenciales automáticas si se proporciona CI."""
        serializer = RegistrarClienteVehiculoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        ci = data.get('ci', '').strip() if data.get('ci') else ''

        with transaction.atomic():
            # Crear cliente
            cliente = Cliente.objects.create(
                nombre=data['nombre'],
                nit=data.get('nit') or None,
                telefono=data.get('telefono') or None,
            )
            
            # Crear vehículo asociado
            vehiculo = Vehiculo.objects.create(
                cliente=cliente,
                placa=data['placa'],
                marca=data.get('marca') or None,
                modelo=data.get('modelo') or None,
                color=data.get('color') or None,
            )

            # Crear credenciales automáticas si se proporciona CI
            credenciales = None
            if ci:
                try:
                    # Generar email desde primer nombre, normalizando caracteres especiales
                    nombre_limpio = cliente.nombre.strip().lower()
                    nombre_limpio = re.sub(r'[áäà]', 'a', nombre_limpio)
                    nombre_limpio = re.sub(r'[éëè]', 'e', nombre_limpio)
                    nombre_limpio = re.sub(r'[íïì]', 'i', nombre_limpio)
                    nombre_limpio = re.sub(r'[óöò]', 'o', nombre_limpio)
                    nombre_limpio = re.sub(r'[úüù]', 'u', nombre_limpio)
                    nombre_limpio = re.sub(r'[ñ]', 'n', nombre_limpio)
                    nombre_limpio = re.sub(r'[^a-z\s]', '', nombre_limpio)
                    partes = nombre_limpio.split()
                    primer_nombre = partes[0] if partes else 'cliente'

                    email_generado = f"{primer_nombre}@estacion.com"

                    # Evitar emails duplicados añadiendo número
                    base_email = primer_nombre
                    contador = 1
                    while Usuario.objects.filter(email=email_generado).exists():
                        email_generado = f"{base_email}{contador}@estacion.com"
                        contador += 1

                    # Obtener rol de cliente
                    rol_cliente = Rol.objects.filter(nombre__iexact='cliente').first()

                    # Crear usuario con credenciales automáticas
                    usuario = Usuario.objects.create_user(
                        email=email_generado,
                        nombre=cliente.nombre,
                        password=ci,
                        created_by=request.user
                    )

                    if rol_cliente:
                        usuario.roles.add(rol_cliente)

                    cliente.usuario = usuario

                    credenciales = {
                        'email': email_generado,
                        'password': ci,
                    }

                    if not cliente.email:
                        cliente.email = email_generado
                        cliente.save(update_fields=['email', 'usuario'])
                    else:
                        cliente.save(update_fields=['usuario'])

                    # Registrar acción en bitácora
                    Bitacora.objects.create(
                        usuario=request.user,
                        usuario_email=request.user.email,
                        usuario_nombre=request.user.nombre,
                        usuario_rol=request.user.nombre_rol,
                        accion='CREAR',
                        estado='EXITO',
                        modulo_afectado='Usuarios',
                        descripcion=f'Credenciales creadas para cliente {cliente.nombre} - {email_generado}',
                        ip_address=getattr(request, 'ip_address', None),
                        user_agent=getattr(request, 'user_agent', '')[:500]
                    )

                except Exception as e:
                    credenciales = {'error': str(e)}

        response_data = {
            'encontrado': True,
            'vehiculo': VehiculoSerializer(vehiculo).data,
        }
        if credenciales:
            response_data['credenciales'] = credenciales

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, HasPermiso])
    def ticket(self, request, pk=None):
        venta = self.get_object()
        serializer = TicketVentaSerializer(venta)
        return Response(serializer.data)

class SucursalViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar sucursales con creación automática de islas y lados."""
    queryset = Sucursal.objects.all()
    serializer_class = SucursalSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'sucursales.ver'

    def get_permissions(self):
        """Asigna permisos específicos según la acción."""
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='sucursales.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='sucursales.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='sucursales.eliminar')]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Crea la sucursal y genera automáticamente sus islas y lados."""
        sucursal = serializer.save()
        # Crear islas y lados automáticamente según la cantidad de islas configurada
        for i in range(1, sucursal.cantidad_islas + 1):
            isla = Isla.objects.create(
                numero=i,
                sucursal=sucursal,
                estado='ACTIVO'
            )
            # Cada isla tiene dos lados: A y B
            Lado.objects.create(isla=isla, lado='A', activo=True)
            Lado.objects.create(isla=isla, lado='B', activo=True)        


class ConsolidacionCajaViewSet(viewsets.GenericViewSet):
    """ViewSet para gestionar la consolidación de caja y reportes de cierre de turnos.
    
    Proporciona reportes de turnos cerrados con indicadores de facturas,
    diferencias de caja y permite consolidar turnos específicos.
    """
    queryset = Turno.objects.all()
    serializer_class = ConsolidacionCajaSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'turnos.ver'
    
    def list(self, request):
        """Lista todos los turnos cerrados y NO consolidados con indicadores de caja."""
        # Obtener solo turnos cerrados Y no consolidados
        turnos_qs = Turno.objects.filter(
            estado='CERRADO', 
            consolidado=False
        ).select_related(
            'operador', 
            'isla', 
            'isla__sucursal',
            'sucursal'
        ).prefetch_related('ventas')
        
        # Serializar con consolidación de datos
        serializer = ConsolidacionCajaSerializer(turnos_qs, many=True)
        data_tabla = serializer.data

        # Calcular indicadores agregados
        total_facturas_emitidas = sum(item['total_facturas'] for item in data_tabla)
        monto_faltantes_total = sum(abs(item['diferencia']) for item in data_tabla if item['diferencia'] < 0)
        turnos_pendientes_count = turnos_qs.count()

        # Retornar respuesta con indicadores y tabla
        return Response({
            'indicadores': {
                'turnos_pendientes': turnos_pendientes_count,
                'total_facturas': total_facturas_emitidas,
                'monto_faltantes': monto_faltantes_total,
            },
            'tabla': data_tabla
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, HasPermiso])
    def consolidar(self, request, pk=None):
        """Consolida un turno específico marcándolo como consolidado y registrando en bitácora."""
        turno = Turno.objects.get(pk=pk)
        
        # Validar que el turno esté cerrado
        if turno.estado != 'CERRADO':
            return Response(
                {'error': 'Solo se pueden consolidar turnos cerrados'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Usar transacción atómica para asegurar integridad
        with transaction.atomic():
            # Marcar turno como consolidado
            turno.consolidado = True
            turno.save()

            # Registrar en bitácora
            Bitacora.objects.create(
                usuario=request.user,
                usuario_email=request.user.email,
                usuario_nombre=request.user.nombre,
                usuario_rol=request.user.nombre_rol,
                accion='CREAR',
                estado='EXITO',
                modulo_afectado='Venta y POS',
                descripcion=f'Consolidación de Caja - Turno #{turno.id}',
                ip_address=getattr(request, 'ip_address', None),
                user_agent=getattr(request, 'user_agent', '')[:500]
            )
        
        return Response({'mensaje': 'Turno consolidado correctamente'})

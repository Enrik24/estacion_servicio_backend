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
from usuarios import models
from django.db.models import Max
from .models import Turno, Cliente, Venta, Isla, Lado, TipoCombustible, Sucursal, Vehiculo, CompraCombustible, EmpresaCliente


from .serializers import (
    SucursalSerializer, IslaSerializer, LadoSerializer, TipoCombustibleSerializer,
    TurnoSerializer, ClienteSerializer, VentaSerializer, RegistrarVentaSerializer,
    TicketVentaSerializer, VehiculoSerializer, RegistrarClienteVehiculoSerializer,

    ConsolidacionCajaSerializer, CompraCombustibleSerializer

)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora ,registrar_bitacora
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
                'id': combustible.id,
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
    def get_queryset(self):
            user = self.request.user
            if user.is_superuser:
                return Isla.objects.prefetch_related('lados').all()
            if user.empresa:
                qs = Isla.objects.prefetch_related('lados').filter(sucursal__empresa=user.empresa)
                if user.sucursal:
                    qs = qs.filter(sucursal=user.sucursal)
                return qs
            return Isla.objects.none()
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
    queryset = Lado.objects.select_related('isla').all()
    serializer_class = LadoSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'surtidores.ver'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            qs = Lado.objects.select_related('isla').all()
        elif user.empresa:
            qs = Lado.objects.select_related('isla').filter(isla__sucursal__empresa=user.empresa)
            if user.sucursal:
                qs = qs.filter(isla__sucursal=user.sucursal)
        else:
            return Lado.objects.none()

        # Filtrar por isla si viene en query params
        isla_id = self.request.query_params.get('isla')
        if isla_id:
            qs = qs.filter(isla_id=isla_id)

        return qs
class TipoCombustibleViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar tipos de combustible activos."""
    queryset = TipoCombustible.objects.filter(activo=True)
    serializer_class = TipoCombustibleSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'surtidores.ver'
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return TipoCombustible.objects.filter(activo=True)
        if user.empresa:
            return TipoCombustible.objects.filter(activo=True, empresa=user.empresa)
        return TipoCombustible.objects.none()
    def perform_update(self, serializer):
        tipo = serializer.save()
        registrar_bitacora(
            self.request,
            accion='EDITAR',
            modulo='Sucursales',
            descripcion=f'Actualizó precio de {tipo.get_tipo_display()} a Bs. {tipo.precio_litro}/Lt',
        )

class TurnoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar turnos de operadores con apertura y cierre."""
    queryset = Turno.objects.all()
    serializer_class = TurnoSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'turnos.ver'
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Turno.objects.all()
        if user.empresa:
            qs = Turno.objects.filter(operador__empresa=user.empresa)
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                qs = qs.filter(isla__sucursal=user.sucursal)
            return qs
        return Turno.objects.none()
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

        registrar_bitacora(
            self.request,
            accion='CREAR',
            descripcion='Apertura de turno',
            modulo='Venta y POS'
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

        registrar_bitacora(
            request,
            accion='EDITAR',
            estado='EXITO',
            modulo='Venta y POS',
            descripcion='Cierre de turno',
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
        fecha = request.query_params.get('fecha', None)
        horario = request.query_params.get('horario', None)
        user = request.user

        if user.empresa:
            turnos = Turno.objects.select_related('operador', 'isla').filter(
                operador__empresa=user.empresa
            )
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                turnos = turnos.filter(isla__sucursal=user.sucursal)
        else:
            turnos = Turno.objects.none()

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
    queryset = Cliente.objects.filter(activo=True)

    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'clientes.ver'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Cliente.objects.filter(activo=True)
        if user.empresa:
            return Cliente.objects.filter(
                activo=True,
                empresa_clientes__empresa=user.empresa
            ).distinct()
        return Cliente.objects.none()

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

                registrar_bitacora(
                    request,
                    accion='CREAR',
                    modulo='Usuarios',
                    descripcion=f'Credenciales creadas automáticamente para cliente {cliente.nombre}',
                )

            except Exception as e:
                # Si falla la creación de credenciales no afecta el registro del cliente
                credenciales = {'error': str(e)}

        response_data = serializer.data
        if credenciales:
            response_data = dict(serializer.data)
            response_data['credenciales'] = credenciales
       
        if request.user.empresa:
            EmpresaCliente.objects.get_or_create(
                empresa=request.user.empresa,
                cliente=cliente
            )
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
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Venta.objects.all()
        if user.empresa:
            qs = Venta.objects.filter(turno__operador__empresa=user.empresa)
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                qs = qs.filter(turno__isla__sucursal=user.sucursal)
            return qs
        return Venta.objects.none()
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

        # Verificar estado del surtidor
        from monitoreo.models import EstadoSurtidor
        estado_surtidor = EstadoSurtidor.objects.filter(lado=lado).first()
        if estado_surtidor and estado_surtidor.estado != 'ACTIVO':
            return Response(
                {'error': f'El Lado {lado.lado} de la Isla {lado.isla.numero} está {estado_surtidor.estado}. No se puede registrar una venta.'},
                status=status.HTTP_400_BAD_REQUEST
            )

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
        # Descontar litros del tanque correspondiente
        try:
            from inventario.models import Tanque
            tanque = Tanque.objects.filter(
                sucursal=turno.isla.sucursal,
                tipo_combustible=tipo_combustible,
                activo=True
            ).first()
            if tanque and litros:
                tanque.nivel_actual = max(0, float(tanque.nivel_actual) - float(litros))
                tanque.save()
                # Notificar si nivel crítico
            if tanque.en_alerta:
                from utils.onesignal import notificar_nivel_critico
                notificar_nivel_critico(tanque)
        except Exception:
            pass

        desc = f'Lleno - {tipo_combustible.get_tipo_display()}' if es_lleno else \
            f'Registró venta de {litros} Lt de {tipo_combustible.get_tipo_display()} - Bs. {total}'

        registrar_bitacora(
            request,
            accion='CREAR',
            descripcion=desc,
            modulo='Venta y POS'
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

        registrar_bitacora(
            request,
            accion='ELIMINAR',
            descripcion='Anulación de venta',
            modulo='Venta y POS'
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
        placa = request.query_params.get('placa', '').upper().strip()
        if not placa:
            return Response({'error': 'Debes ingresar una placa'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            vehiculo = Vehiculo.objects.select_related('cliente').get(placa=placa, activo=True)
            
            # Verificar si el cliente está registrado en esta empresa
            if request.user.empresa:
                registrado_en_empresa = EmpresaCliente.objects.filter(
                    empresa=request.user.empresa,
                    cliente=vehiculo.cliente
                ).exists()
                
                return Response({
                    'encontrado': True,
                    'registrado_en_empresa': registrado_en_empresa,
                    'vehiculo': VehiculoSerializer(vehiculo).data
                })
            
            return Response({'encontrado': True, 'registrado_en_empresa': False, 'vehiculo': VehiculoSerializer(vehiculo).data})
        
        except Vehiculo.DoesNotExist:
            return Response({'encontrado': False})
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def registrar_en_empresa(self, request):
        cliente_id = request.data.get('cliente_id')
        if not cliente_id:
            return Response({'error': 'cliente_id requerido'}, status=400)
        try:
            cliente = Cliente.objects.get(id=cliente_id, activo=True)
            if request.user.empresa:
                EmpresaCliente.objects.get_or_create(
                    empresa=request.user.empresa,
                    cliente=cliente
                )
            return Response({'mensaje': 'Cliente registrado en la empresa correctamente'})
        except Cliente.DoesNotExist:
            return Response({'error': 'Cliente no encontrado'}, status=404)
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
                    # Buscar si ya existe un usuario asociado a este cliente por nombre similar
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

                    email_base = f"{primer_nombre}@estacion.com"
                    usuario_existente = Usuario.objects.filter(
                        nombre__iexact=cliente.nombre
                    ).first()

                    if usuario_existente:
                        # Ya tiene credenciales, no crear nuevas
                        credenciales = {
                            'email': usuario_existente.email,
                            'ya_existia': True,
                            'mensaje': 'El cliente ya tiene credenciales en el sistema'
                        }
                    else:
                        # Crear nuevas credenciales
                        email_generado = email_base
                        base_email = primer_nombre
                        contador = 1
                        while Usuario.objects.filter(email=email_generado).exists():
                            email_generado = f"{base_email}{contador}@estacion.com"
                            contador += 1

                        rol_cliente = Rol.objects.filter(nombre__iexact='cliente').first()

                        usuario = Usuario.objects.create_user(
                            email=email_generado,
                            nombre=cliente.nombre,
                            password=ci,
                            created_by=request.user
                        )

                        if rol_cliente:
                            usuario.roles.add(rol_cliente)

                        credenciales = {
                            'email': email_generado,
                            'password': ci,
                            'ya_existia': False,
                        }
                    registrar_bitacora(
                        request,
                        accion='CREAR',
                        modulo='Usuarios',
                        descripcion=f'Credenciales creadas para cliente {cliente.nombre} - {email_generado}',
                    )

                except Exception as e:
                    credenciales = {'error': str(e)}

        response_data = {
            'encontrado': True,
            'vehiculo': VehiculoSerializer(vehiculo).data,
        }
        if credenciales:
            response_data['credenciales'] = credenciales
        if request.user.empresa:
            EmpresaCliente.objects.get_or_create(
                empresa=request.user.empresa,
                cliente=cliente
            )
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
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Sucursal.objects.all()
        if user.empresa:
            qs = Sucursal.objects.filter(empresa=user.empresa)
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                qs = qs.filter(id=user.sucursal.id)
            return qs
        return Sucursal.objects.none()
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
        tipos = self.request.data.get('tipos_combustible', [])
        sucursal = serializer.save(empresa=self.request.user.empresa)
        if tipos:
            sucursal.tipos_combustible.set(tipos)
        ultimo_numero = Isla.objects.aggregate(max_num=Max('numero'))['max_num'] or 0
        for i in range(1, sucursal.cantidad_islas + 1):
            isla = Isla.objects.create(numero=i, sucursal=sucursal, estado='ACTIVO')
            Lado.objects.create(isla=isla, lado='A', activo=True)
            Lado.objects.create(isla=isla, lado='B', activo=True)
        registrar_bitacora(self.request, accion='CREAR', descripcion=f'Creó la sucursal: {sucursal.nombre}', modulo='Sucursales')

    def perform_update(self, serializer):
        tipos = self.request.data.get('tipos_combustible', [])
        sucursal = serializer.save()
        if tipos:
            sucursal.tipos_combustible.set(tipos)
        registrar_bitacora(self.request, accion='EDITAR', descripcion=f'Editó la sucursal: {sucursal.nombre}', modulo='Sucursales')

    def perform_destroy(self, instance):
        registrar_bitacora(
            self.request,
            accion='ELIMINAR',
            modulo='Sucursales',
            descripcion=f'Eliminó la sucursal: {instance.nombre}',
        )
        instance.delete()

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
        user = request.user
        if user.empresa:
            turnos_qs = Turno.objects.filter(
                estado='CERRADO',
                consolidado=False,
                operador__empresa=user.empresa
            ).select_related('operador', 'isla', 'isla__sucursal', 'sucursal').prefetch_related('ventas')
            # Filtrar por sucursal si es gerente
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                turnos_qs = turnos_qs.filter(isla__sucursal=user.sucursal)
        else:
            turnos_qs = Turno.objects.none()

        serializer = ConsolidacionCajaSerializer(turnos_qs, many=True)
        data_tabla = serializer.data

        total_facturas_emitidas = sum(item['total_facturas'] for item in data_tabla)
        monto_faltantes_total = sum(abs(item['diferencia']) for item in data_tabla if item['diferencia'] < 0)
        turnos_pendientes_count = turnos_qs.count()

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
        turno = Turno.objects.get(pk=pk)
        user = request.user

        # Verificar que el turno pertenece a la empresa del usuario
        if not user.is_superuser:
            if turno.operador.empresa != user.empresa:
                return Response({'error': 'Sin permiso'}, status=403)
            
            # Si es gerente solo puede consolidar turnos de su sucursal
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                if turno.isla.sucursal != user.sucursal:
                    return Response({'error': 'No puedes consolidar turnos de otra sucursal'}, status=403)

        if turno.estado != 'CERRADO':
            return Response(
                {'error': 'Solo se pueden consolidar turnos cerrados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            turno.consolidado = True
            turno.save()
            registrar_bitacora(
                request,
                accion='CREAR',
                modulo='Venta y POS',
                descripcion=f'Consolidación de Caja - Turno #{turno.id}',
            )
        return Response({'mensaje': 'Turno consolidado correctamente'})


# COMPLETAR PERFIL CLIENTE WEB
from .serializers import CompletarPerfilClienteSerializer

class CompletarPerfilClienteAPIView(APIView):
    """
    Endpoint: PUT /ventas/completar-perfil/

    Permite al usuario autenticado completar su perfil de cliente web por primera vez.
    Se usa cuando un usuario se registra desde la app/web y todavía no tiene datos
    completos (nombre real, NIT, teléfono, vehículo). Recibe todos esos datos en un
    solo request y los persiste de forma atómica.

    Flujo:
      1. Busca (o crea) el registro Cliente vinculado al Usuario autenticado.
      2. Valida los datos enviados con CompletarPerfilClienteSerializer.
      3. Actualiza el nombre en el Usuario y, opcionalmente, cambia la contraseña.
      4. Sincroniza nombre, email, NIT y teléfono en el registro Cliente.
      5. Crea o actualiza el Vehículo con la placa proporcionada.

    Requiere: autenticación JWT.
    Responde: datos actualizados del cliente y del vehículo.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        # Obtener o crear el registro Cliente vinculado al usuario autenticado.
        # Si el usuario no tiene un Cliente asociado, resolve_cliente_for_usuario
        # lo crea automáticamente (create_if_missing=True).
        cliente = resolve_cliente_for_usuario(request.user, create_if_missing=True)
        if not cliente:
            return Response(
                {'error': 'No se pudo resolver el perfil de cliente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validar los datos del body usando el serializer dedicado.
        # Se pasa el cliente en el contexto para que el serializer pueda
        # hacer validaciones que dependan del cliente existente (ej. placa).
        serializer = CompletarPerfilClienteSerializer(
            data=request.data,
            context={'cliente': cliente},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # --- Actualizar Usuario ---
        # Sincronizamos el nombre en el modelo Usuario para que coincida con el Cliente.
        # Si se envió una nueva contraseña, se actualiza de forma segura con set_password
        # (que aplica hashing automático).
        usuario = request.user
        usuario.nombre = data['nombre']
        new_password = data.get('password')
        if new_password:
            usuario.set_password(new_password)
            usuario.save(update_fields=['nombre', 'password'])
        else:
            usuario.save(update_fields=['nombre'])

        # --- Actualizar Cliente (sincronizado con Usuario) ---
        # El email del Cliente se obtiene del email del Usuario para mantener consistencia.
        cliente.nombre = data['nombre']
        cliente.email = (usuario.email or '').strip().lower() or None
        cliente.nit = data.get('nit') or None
        cliente.telefono = data.get('telefono') or None
        cliente.save(update_fields=['nombre', 'email', 'nit', 'telefono'])

        # --- Crear o actualizar Vehículo ---
        # update_or_create usa la placa como clave única: si ya existe ese vehículo
        # lo actualiza; si no, lo crea. Así se evitan duplicados por placa.
        vehiculo, created = Vehiculo.objects.update_or_create(
            placa=data['placa'],
            defaults={
                'cliente': cliente,
                'marca': data.get('marca') or None,
                'modelo': data.get('modelo') or None,
                'color': data.get('color') or None,
                'activo': True,
            },
        )

        from .serializers import VehiculoSerializer
        return Response({
            'mensaje': 'Perfil completado exitosamente.',
            'cliente': {
                'id': cliente.id,
                'nombre': cliente.nombre,
                'email': cliente.email,
                'nit': cliente.nit,
                'telefono': cliente.telefono,
            },
            'vehiculo': VehiculoSerializer(vehiculo).data,
        }, status=status.HTTP_200_OK)


# PREPAGO
import stripe
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import FileResponse, Http404
from rest_framework.parsers import JSONParser
from .models import OrdenPrepago
from .serializers import OrdenPrepagoSerializer, CrearOrdenPrepagoSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class CrearPrepagoAPIView(APIView):
    """
    Endpoint: POST /ventas/prepago/crear/

    Inicia el flujo de pago anticipado de combustible desde la app del cliente.
    El cliente elige el tipo de combustible y cuánto dinero quiere cargar.
    Esta view calcula los litros equivalentes, crea un PaymentIntent en Stripe
    (pasarela de pago) y registra la orden en la base de datos con estado PENDIENTE.

    El frontend recibe el 'client_secret' de Stripe para completar el pago
    directamente desde el dispositivo del cliente sin que el monto pase por
    nuestro servidor (flujo Stripe Elements / PaymentSheet).

    Flujo completo:
      1. Validar datos (tipo_combustible_id, monto_total).
      2. Obtener precio actual del combustible desde la BD.
      3. Calcular litros = monto_total / precio_por_litro  (2 decimales).
      4. Resolver el Cliente vinculado al usuario autenticado.
      5. Crear PaymentIntent en Stripe con monto en centavos (USD).
      6. Guardar OrdenPrepago en BD con estado='PENDIENTE' y el ID del PaymentIntent.
      7. Devolver el client_secret al frontend para que complete el pago.

    Requiere: autenticación JWT.
    El pago real lo confirma el webhook de Stripe (StripeWebhookAPIView).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CrearOrdenPrepagoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        tipo_combustible_id = data['tipo_combustible_id']
        monto_total = data['monto_total']

        # Obtener tipo de combustible y precio actual desde la BD.
        # Si está inactivo o no existe se rechaza el request.
        try:
            tipo_combustible = TipoCombustible.objects.get(id=tipo_combustible_id, activo=True)
        except TipoCombustible.DoesNotExist:
            return Response({'error': 'Tipo de combustible no encontrado o inactivo.'}, status=status.HTTP_400_BAD_REQUEST)

        precio = tipo_combustible.precio_litro

        # Calcular cuántos litros equivale el monto pagado.
        # Se usa Decimal para evitar errores de punto flotante en cálculos monetarios.
        litros = (Decimal(str(monto_total)) / precio).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Resolver el registro Cliente del usuario autenticado.
        # Si todavía no tiene un Cliente asociado, se crea uno automáticamente.
        cliente = resolve_cliente_for_usuario(request.user, create_if_missing=True)
        if not cliente:
            return Response({'error': 'No se pudo resolver el cliente.'}, status=status.HTTP_400_BAD_REQUEST)

        # Crear PaymentIntent en Stripe.
        # Stripe trabaja con la unidad mínima de la moneda (centavos para USD),
        # por eso se multiplica el monto por 100.
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(float(monto_total) * 100),  # Stripe usa centavos
                currency='usd',
                metadata={
                    # Metadata opcional visible en el dashboard de Stripe
                    'cliente_email': cliente.email or '',
                    'tipo_combustible': tipo_combustible.get_tipo_display(),
                },
            )

            # Crear la OrdenPrepago en la BD vinculada al PaymentIntent.
            # Estado inicial = PENDIENTE hasta que Stripe confirme el pago vía webhook.
            orden = OrdenPrepago.objects.create(
                cliente=cliente,
                tipo_combustible=tipo_combustible,
                precio_por_litro=precio,
                monto_total=monto_total,
                litros=litros,
                estado='PENDIENTE',
                stripe_payment_intent_id=intent.id,
            )

            # Devolver el client_secret al frontend.
            # El frontend usa este secret para presentar la pantalla de pago de Stripe.
            return Response({
                'client_secret': intent.client_secret,
                'orden_id': orden.id,
                'numero_orden': orden.numero_orden,
                'litros': str(orden.litros),
                'precio_por_litro': str(orden.precio_por_litro),
            })

        except Exception as e:
            logger.error(f"Error al crear PaymentIntent: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookAPIView(APIView):
    """
    Endpoint: POST /ventas/prepago/webhook-stripe/

    Receptor de eventos enviados por Stripe cuando cambia el estado de un pago.
    Stripe llama a esta URL automáticamente desde sus servidores (no el frontend),
    por eso no requiere autenticación de usuario pero sí debe estar registrada
    en el dashboard de Stripe.

    El decorador @csrf_exempt es necesario porque Stripe no envía el token CSRF
    de Django; en su lugar la seguridad se delega a la firma del webhook de Stripe
    (pendiente de implementar con stripe.Webhook.construct_event si se requiere
    mayor seguridad en producción).

    Eventos manejados:
      - payment_intent.succeeded  → el cliente pagó exitosamente.
      - payment_intent.payment_failed → el pago fue rechazado o falló.

    Flujo para pago exitoso (_handle_success):
      1. Leer el ID del PaymentIntent del payload.
      2. Buscar la OrdenPrepago con ese PI en estado PENDIENTE o PROCESANDO_PAGO.
      3. Cambiar estado de la orden a PAGADO.
      4. Generar el comprobante PDF de la orden.
      5. Enviar el comprobante por email al cliente.
      6. Registrar la operación en bitácora.

    Flujo para pago fallido (_handle_failure):
      1. Buscar la OrdenPrepago por PI.
      2. Cambiar estado a FALLIDO para que el cliente sepa que debe reintentar.

    Siempre devuelve HTTP 200 a Stripe (incluso en errores internos) para evitar
    que Stripe reintente el webhook indefinidamente.
    """
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        payload = request.data
        event_type = payload.get('type')

        # Despachar al manejador correcto según el tipo de evento de Stripe
        if event_type == 'payment_intent.succeeded':
            self._handle_success(payload, request)
        elif event_type == 'payment_intent.payment_failed':
            self._handle_failure(payload)

        # Siempre retornar 200 para que Stripe no reintente el webhook
        return Response(status=status.HTTP_200_OK)

    def _handle_success(self, payload, request):
        """Procesa un pago exitoso: actualiza la orden, genera PDF y envía email."""
        payment_intent = payload.get('data', {}).get('object', {})
        pi_id = payment_intent.get('id')

        # Buscar la orden en BD. Si no existe (ej. webhook duplicado) solo loggeamos.
        try:
            orden = OrdenPrepago.objects.get(
                stripe_payment_intent_id=pi_id,
                estado__in=['PENDIENTE', 'PROCESANDO_PAGO'],
            )
        except OrdenPrepago.DoesNotExist:
            logger.warning(f"Webhook: Orden no encontrada para PI {pi_id}")
            return

        # Marcar la orden como PAGADO en la BD
        orden.estado = 'PAGADO'
        orden.save()

        # Generar el comprobante PDF y guardarlo en media/comprobantes/
        # Si falla la generación del PDF la orden ya quedó PAGADO (no se revierte)
        try:
            from utils.pdf_generator import generar_comprobante_pdf
            generar_comprobante_pdf(orden)
        except Exception as e:
            logger.error(f"Error generando PDF para orden {orden.numero_orden}: {e}")

        # Enviar el comprobante por email al cliente
        # Igual que el PDF: si falla el email la orden sigue siendo válida
        try:
            from utils.email_sender import enviar_email_comprobante
            enviar_email_comprobante(orden)
        except Exception as e:
            logger.error(f"Error enviando email para orden {orden.numero_orden}: {e}")

        # Registrar la operación en la bitácora del sistema para auditoría
        registrar_bitacora(
            request=None,  # No hay usuario autenticado en el webhook, viene de Stripe
            accion='CREAR',
            modulo='Ventas',
            descripcion=f'PREPAGO_CREADO - Orden {orden.numero_orden} - Bs. {orden.monto_total} - Cliente {orden.cliente.nombre}',
        )

    def _handle_failure(self, payload):
        """Procesa un pago fallido: marca la orden como FALLIDO."""
        payment_intent = payload.get('data', {}).get('object', {})
        pi_id = payment_intent.get('id')

        try:
            orden = OrdenPrepago.objects.get(
                stripe_payment_intent_id=pi_id,
                estado__in=['PENDIENTE', 'PROCESANDO_PAGO'],
            )
            orden.estado = 'FALLIDO'
            orden.save()
            logger.info(f"Orden {orden.numero_orden} marcada como FALLIDO")
        except OrdenPrepago.DoesNotExist:
            logger.warning(f"Webhook failure: Orden no encontrada para PI {pi_id}")


class MisOrdenesPrepagoAPIView(APIView):
    """
    Endpoint: GET /ventas/prepago/mis-ordenes/

    Devuelve el historial de órdenes de prepago del cliente autenticado,
    ordenadas de la más reciente a la más antigua.

    Se usa en la pantalla "Mis Prepagos" de la app del cliente para que pueda
    ver el estado de todos sus pagos (PENDIENTE, PAGADO, DESPACHADO, VENCIDO, etc.)
    y descargar los comprobantes PDF de los que ya fueron pagados.

    Si el usuario no tiene un Cliente asociado en el sistema (caso raro),
    devuelve una lista vacía en lugar de error para no romper la UI.

    Requiere: autenticación JWT.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Resolver el Cliente vinculado al usuario autenticado.
        # A diferencia de crear prepago, aquí NO creamos el cliente si no existe
        # (create_if_missing=False por defecto), solo consultamos.
        cliente = resolve_cliente_for_usuario(request.user)
        if not cliente:
            return Response([])

        # Traer todas las órdenes del cliente, más recientes primero
        ordenes = OrdenPrepago.objects.filter(cliente=cliente).order_by('-fecha_creacion')
        serializer = OrdenPrepagoSerializer(ordenes, many=True, context={'request': request})
        return Response(serializer.data)


class DescargarComprobantePDFAPIView(APIView):
    """
    Endpoint: GET /ventas/prepago/<orden_id>/comprobante/

    Permite al cliente autenticado descargar el comprobante PDF de una
    orden de prepago que ya fue pagada (o despachada/vencida).

    Seguridad:
      - Solo el dueño de la orden puede descargarla (se filtra por cliente).
      - Solo se permite descargar órdenes en estado PAGADO, DESPACHADO o VENCIDO.
        Una orden PENDIENTE o FALLIDO no tiene comprobante válido.

    Si el PDF no existe en el almacenamiento (por ejemplo, si falló la generación
    en el webhook), se intenta regenerar en el momento antes de servir el archivo.

    Devuelve el archivo como descarga (Content-Disposition: attachment) con el
    nombre 'comprobante_<numero_orden>.pdf'.

    Requiere: autenticación JWT.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, orden_id):
        # Resolver el cliente del usuario autenticado para verificar propiedad
        cliente = resolve_cliente_for_usuario(request.user)
        if not cliente:
            raise Http404

        # Buscar la orden verificando que pertenece a este cliente y tiene
        # un estado que garantiza que el pago fue procesado
        try:
            orden = OrdenPrepago.objects.get(id=orden_id, cliente=cliente, estado__in=['PAGADO', 'DESPACHADO', 'VENCIDO'])
        except OrdenPrepago.DoesNotExist:
            raise Http404

        # Si el PDF no existe en disco, intentar regenerarlo ahora
        if not orden.comprobante_pdf:
            try:
                from utils.pdf_generator import generar_comprobante_pdf
                generar_comprobante_pdf(orden)
            except Exception:
                return Response({'error': 'No se pudo generar el comprobante.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Servir el archivo PDF como descarga al navegador/app
        return FileResponse(
            orden.comprobante_pdf.open('rb'),
            as_attachment=True,
            filename=f"comprobante_{orden.numero_orden}.pdf",
        )

class ValidarPrepagoAPIView(APIView):
    """
    Endpoint: GET /ventas/prepago/<numero_orden>/validar/

    Usado por el operador en el POS para verificar una orden de prepago
    ANTES de despachar el combustible. El operador escanea el QR del cliente
    (que contiene el numero_orden) y llama a este endpoint para saber si
    la orden es válida y cuántos litros debe cargar.

    Validaciones que realiza:
      1. La orden existe en el sistema.
      2. La orden no ha expirado (fecha_expiracion). Si expiró, la marca
         automáticamente como VENCIDA para mantener consistencia en la BD.
      3. El estado de la orden es exactamente 'PAGADO' (ni PENDIENTE, ni
         DESPACHADO, ni FALLIDO, etc.).

    Si todo está bien devuelve los datos de la orden para que el operador
    confirme la identidad del cliente y el combustible a despachar.

    Requiere: autenticación JWT (el operador debe estar logueado).
    No modifica datos si la orden es válida (operación de solo lectura).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, numero_orden):
        # Buscar la orden por número (el QR contiene este número)
        try:
            orden = OrdenPrepago.objects.get(numero_orden=numero_orden)
        except OrdenPrepago.DoesNotExist:
            return Response({"detail": "La orden de prepago no existe."}, status=status.HTTP_404_NOT_FOUND)

        # Verificar expiración: si ya venció y aún figura como PAGADO, actualizarla
        if timezone.now() > orden.fecha_expiracion and orden.estado not in ['VENCIDO', 'DESPACHADO', 'RECHAZADO']:
            orden.estado = 'VENCIDO'
            orden.save()
            return Response({"detail": "La orden de prepago ha expirado."}, status=status.HTTP_400_BAD_REQUEST)

        # Solo las órdenes en estado PAGADO son válidas para despachar
        if orden.estado != 'PAGADO':
            return Response({"detail": f"La orden no es válida para despacho. Estado actual: {orden.get_estado_display()}"}, status=status.HTTP_400_BAD_REQUEST)

        # Devolver los datos relevantes para que el operador confirme el despacho
        return Response({
            "numero_orden": orden.numero_orden,
            "cliente_nombre": orden.cliente.nombre,
            "cliente_ci": orden.cliente.nit,
            "tipo_combustible": orden.tipo_combustible.get_tipo_display(),
            "litros": orden.litros,
            "monto_total": orden.monto_total,
            "fecha_expiracion": orden.fecha_expiracion
        })

class DespacharPrepagoAPIView(APIView):
    """
    Endpoint: POST /ventas/prepago/<numero_orden>/despachar/

    Ejecuta el despacho físico del combustible pre-pagado. Lo llama el operador
    desde el POS después de validar la orden con ValidarPrepagoAPIView y cargar
    el combustible al vehículo.

    Body requerido:
      - lado_id (int): el lado del surtidor que se usó para el despacho.

    Validaciones:
      1. El operador tiene un turno abierto.
      2. El lado_id pertenece a la isla del turno del operador.
      3. La orden existe y no ha expirado.
      4. La orden está en estado PAGADO (no despachada ni fallida).

    Operaciones que realiza (todo en una transacción atómica):
      1. Crea una Venta normal vinculada a la OrdenPrepago con metodo_pago='PREPAGO'.
      2. Descuenta los litros del Tanque correspondiente en inventario.
      3. Dispara una notificación si el tanque queda en nivel crítico.
      4. Cambia el estado de la OrdenPrepago a 'DESPACHADO'.
      5. Registra la operación en bitácora.

    El uso de select_for_update() en la consulta de la orden previene que dos
    operadores intenten despachar la misma orden simultáneamente (race condition).

    Requiere: autenticación JWT + turno abierto.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, numero_orden):
        # Validar que venga el lado_id en el body
        lado_id = request.data.get('lado_id')
        if not lado_id:
            return Response({"detail": "El lado_id es requerido."}, status=status.HTTP_400_BAD_REQUEST)

        # El operador debe tener un turno abierto para poder despachar
        try:
            turno = Turno.objects.get(operador=request.user, estado='ABIERTO')
        except Turno.DoesNotExist:
            return Response({"detail": "No tienes un turno abierto para despachar."}, status=status.HTTP_400_BAD_REQUEST)

        # El lado debe pertenecer a la isla asignada al turno del operador
        try:
            lado = Lado.objects.get(id=lado_id, isla=turno.isla, activo=True)
        except Lado.DoesNotExist:
            return Response({"detail": "El lado especificado no es válido para tu isla asignada."}, status=status.HTTP_400_BAD_REQUEST)

        # select_for_update bloquea la fila en la BD durante esta transacción,
        # impidiendo que otro operador despache la misma orden al mismo tiempo.
        try:
            orden = OrdenPrepago.objects.select_for_update().get(numero_orden=numero_orden)
        except OrdenPrepago.DoesNotExist:
            return Response({"detail": "La orden de prepago no existe."}, status=status.HTTP_404_NOT_FOUND)

        # Verificar expiración (puede haber expirado entre la validación y el despacho)
        if timezone.now() > orden.fecha_expiracion and orden.estado not in ['VENCIDO', 'DESPACHADO', 'RECHAZADO']:
            orden.estado = 'VENCIDO'
            orden.save()
            return Response({"detail": "La orden ha expirado."}, status=status.HTTP_400_BAD_REQUEST)

        # Doble verificación del estado para evitar despachos duplicados
        if orden.estado != 'PAGADO':
            return Response({"detail": f"La orden no es válida para despacho. Estado actual: {orden.get_estado_display()}"}, status=status.HTTP_400_BAD_REQUEST)

        # Generar número de comprobante único para la Venta creada
        numero_comprobante = f"VTA-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        # Crear la Venta asociada a esta orden de prepago.
        # El precio y litros vienen de la orden (precio bloqueado al momento del pago).
        venta = Venta.objects.create(
            turno=turno,
            lado=lado,
            tipo_combustible=orden.tipo_combustible,
            cliente=orden.cliente,
            litros=orden.litros,
            precio_unitario=orden.precio_por_litro,
            total=orden.monto_total,
            metodo_pago='PREPAGO',
            numero_comprobante=numero_comprobante,
            created_by=request.user,
            orden_prepago=orden   # Vínculo directo a la OrdenPrepago
        )

        # Descontar litros del tanque de inventario correspondiente.
        # Se envuelve en try/except para que un error de inventario no bloquee
        # el despacho (el combustible ya fue entregado físicamente).
        try:
            from inventario.models import Tanque
            tanque = Tanque.objects.filter(
                sucursal=turno.isla.sucursal,
                tipo_combustible=orden.tipo_combustible,
                activo=True
            ).first()
            if tanque and orden.litros:
                tanque.nivel_actual = max(0, float(tanque.nivel_actual) - float(orden.litros))
                tanque.save()
            # Si el nivel quedó crítico, notificar al gerente/administrador
            if tanque and tanque.en_alerta:
                from utils.onesignal import notificar_nivel_critico
                notificar_nivel_critico(tanque)
        except Exception:
            pass  # No bloquear el despacho por errores de inventario

        # Marcar la orden como despachada para que no pueda usarse nuevamente
        orden.estado = 'DESPACHADO'
        orden.save()

        from usuarios.views import registrar_bitacora
        registrar_bitacora(
            request,
            accion='CREAR',
            descripcion=f"Despacho Prepago {orden.numero_orden} - {orden.litros} Lt",
            modulo='Venta y POS'
        )

        return Response(
            {"detail": "Despacho realizado con éxito.", "venta_id": venta.id, "numero_comprobante": venta.numero_comprobante},
            status=status.HTTP_201_CREATED
        )


class OrdenesPrepagoOperadorAPIView(APIView):
    """
    Endpoint: GET /ventas/prepago/operador/ordenes/

    Lista las órdenes de prepago que el operador puede ver y despachar
    desde el POS. Pensado para la pantalla de "Cola de Prepagos" en el
    panel del operador.

    Filtros disponibles (query params):
      - estado=PAGADO       (default) → solo las listas para despachar
      - estado=TODOS        → todas excepto DESPACHADO y RECHAZADO

    Seguridad multi-empresa:
      - Si el usuario pertenece a una empresa, solo ve órdenes cuyo tipo de
        combustible pertenece a esa empresa. Así un operador de empresa A
        nunca ve los prepagos de empresa B.
      - Los superusuarios ven todas las órdenes.

    Expiración automática:
      Antes de devolver los resultados, el endpoint detecta y marca como
      VENCIDAS las órdenes que ya superaron su fecha_expiracion pero aún
      figuraban como PAGADO. Esto evita que el operador vea órdenes caducadas.

    Los resultados se ordenan por fecha_expiracion ascendente para que el
    operador atienda primero las que están por vencer.

    Requiere: autenticación JWT.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Construir queryset base con datos relacionados para evitar N+1 queries
        qs = OrdenPrepago.objects.select_related(
            'cliente', 'tipo_combustible'
        )

        # Filtrar por empresa del operador a través del tipo de combustible.
        # Un operador solo puede despachar combustibles de su empresa.
        if user.empresa:
            qs = qs.filter(tipo_combustible__empresa=user.empresa)
        elif not user.is_superuser:
            # Usuario sin empresa y sin superuser: no ve ninguna orden
            return Response([])

        # Filtrar por estado — por defecto solo PAGADO (listas para despachar)
        estado = request.query_params.get('estado', 'PAGADO')
        if estado == 'TODOS':
            # Mostrar todo excepto las ya finalizadas
            qs = qs.exclude(estado__in=['DESPACHADO', 'RECHAZADO'])
        else:
            qs = qs.filter(estado=estado)

        # Marcar como VENCIDO las que ya expiraron pero siguen en PAGADO.
        # Se hace en bulk para no hacer un save() individual por cada una.
        ahora = timezone.now()
        vencidas = qs.filter(estado='PAGADO', fecha_expiracion__lt=ahora)
        if vencidas.exists():
            vencidas.update(estado='VENCIDO')
            # Excluir las recién vencidas del resultado para no mostrarlas
            qs = qs.exclude(id__in=vencidas.values_list('id', flat=True))

        # Ordenar de la que vence más pronto a la que vence más tarde
        qs = qs.order_by('fecha_expiracion')

        serializer = OrdenPrepagoSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


# ── ENDPOINT PÚBLICO: Sucursales para Landing Page ────────────────────────────

class SucursalesPublicasAPIView(APIView):
    """
    Endpoint público (sin autenticación) para la landing page.
    Devuelve todas las sucursales activas con sus coordenadas y
    disponibilidad de combustible por tanque.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from inventario.models import Tanque

        sucursales = Sucursal.objects.filter(estado='ACTIVA').prefetch_related(
            'tanques__tipo_combustible'
        )

        resultado = []
        for suc in sucursales:
            combustibles = []
            for tanque in suc.tanques.filter(activo=True):
                nivel_actual = float(tanque.nivel_actual)
                nivel_minimo = float(tanque.nivel_minimo_alerta)
                capacidad = float(tanque.capacidad_maxima)

                if nivel_actual <= 0:
                    disponibilidad = 'sin_stock'
                elif nivel_actual <= nivel_minimo:
                    disponibilidad = 'bajo'
                else:
                    disponibilidad = 'disponible'

                combustibles.append({
                    'tipo': tanque.tipo_combustible.tipo,
                    'nombre': tanque.tipo_combustible.get_tipo_display(),
                    'disponibilidad': disponibilidad,
                    'porcentaje_nivel': round((nivel_actual / capacidad * 100), 1) if capacidad > 0 else 0,
                })

            resultado.append({
                'id': suc.id,
                'nombre': suc.nombre,
                'direccion': suc.direccion,
                'telefono': suc.telefono,
                'latitud': float(suc.latitud) if suc.latitud is not None else None,
                'longitud': float(suc.longitud) if suc.longitud is not None else None,
                'tiene_gnv': suc.tiene_gnv,
                'combustibles': combustibles,
            })

        return Response(resultado)

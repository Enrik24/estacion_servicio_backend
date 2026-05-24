"""ViewSets para la aplicación de ventas y POS.

Define los ViewSets para gestionar islas, lados, tipos de combustible, turnos,
clientes, ventas, vehículos, sucursales y consolidación de caja.
"""

from rest_framework import viewsets, status
from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
import uuid
import re

from usuarios import models
from django.db.models import Max
from .models import Turno, Cliente, Venta, Isla, Lado, TipoCombustible, Sucursal, Vehiculo,EmpresaCliente

from .serializers import (
    ConsolidacionCajaSerializer, SucursalSerializer, IslaSerializer, LadoSerializer, TipoCombustibleSerializer,
    TurnoSerializer, ClienteSerializer, VentaSerializer, RegistrarVentaSerializer, VehiculoSerializer, RegistrarClienteVehiculoSerializer,
    TicketVentaSerializer
)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora ,registrar_bitacora
from usuarios.models import Usuario, Rol

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
    """ViewSet para gestionar lados de islas con referencia a su isla."""
    queryset = Lado.objects.select_related('isla').all()
    serializer_class = LadoSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'surtidores.ver'
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Lado.objects.select_related('isla').all()
        if user.empresa:
            qs = Lado.objects.select_related('isla').filter(isla__sucursal__empresa=user.empresa)
            if user.sucursal:
                qs = qs.filter(isla__sucursal=user.sucursal)
            return qs
        return Lado.objects.none()


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


            registrar_bitacora(
                request,
                accion='CREAR',
                modulo='Venta y POS',
                descripcion=f'Consolidación de Caja - Turno #{turno.id}',
            )
        
        return Response({'mensaje': 'Turno consolidado correctamente'})
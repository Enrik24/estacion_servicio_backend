from django.db import models
from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django_filters.rest_framework import DjangoFilterBackend

from .models import Usuario, Rol, Permiso, LimiteConsumo
from .serializers import (
    UsuarioSerializer, UsuarioMeSerializer, RolSerializer,
    PermisoSerializer, CambiarPasswordSerializer, LimiteConsumoSerializer,
    ValidarConsumoSerializer, ClienteVentasSerializer
)
from ventas.models import Cliente as VentasCliente, Venta
from utils.permissions import HasPermiso
from seguridad.models import Bitacora  # ← Importado de seguridad

# CRUD USUARIOS
class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('id')
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'usuarios.ver'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'roles']
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='usuarios.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='usuarios.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='usuarios.eliminar')]
        return super().get_permissions()
    
    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()
        
        request = self.request
        Bitacora.objects.create(
            usuario=request.user,
            usuario_email=request.user.email,
            usuario_nombre=request.user.nombre,
            usuario_rol=request.user.nombre_rol,
            accion='ELIMINAR',
            estado='EXITO',
            modulo_afectado='Administración y Seguridad',
            descripcion='Eliminó al usuario: {instance.email}',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = UsuarioMeSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_me(self, request):
        serializer = UsuarioMeSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def cambiar_password(self, request):
        serializer = CambiarPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data['password_actual']):
                return Response(
                    {'error': 'Contraseña actual incorrecta'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.set_password(serializer.validated_data['password_nuevo'])
            user.save()
            
            Bitacora.objects.create(
                usuario=user,
                usuario_email=user.email,
                usuario_nombre=user.nombre,
                usuario_rol=user.nombre_rol,
                accion='EDITAR',
                estado='EXITO',
                modulo_afectado='Administración y Seguridad',
                descripcion='Actualizó su contraseña exitosamente',
                ip_address=getattr(request, 'ip_address', None),
                user_agent=getattr(request, 'user_agent', '')[:500]
            )
            
            return Response({'mensaje': 'Contraseña actualizada correctamente'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# CRUD ROLES
class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.prefetch_related('permisos').order_by('id')
    serializer_class = RolSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'roles.ver'
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='roles.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='roles.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='roles.eliminar')]
        return super().get_permissions()
    
    @action(detail=True, methods=['get'])
    def permisos(self, request, pk=None):
        rol = self.get_object()
        permisos = rol.permisos.all()
        serializer = PermisoSerializer(permisos, many=True)
        return Response(serializer.data)

# CRUD PERMISOS
class PermisoViewSet(viewsets.ModelViewSet):
    queryset = Permiso.objects.all().order_by('id')
    serializer_class = PermisoSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'permisos.ver'
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='permisos.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='permisos.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='permisos.eliminar')]
        return super().get_permissions()


class ClienteViewSet(viewsets.ModelViewSet):
    serializer_class = ClienteVentasSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'clientes.ver'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['activo']

    def get_queryset(self):
        queryset = VentasCliente.objects.all().order_by('nombre')
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(nombre__icontains=search) |
                models.Q(email__icontains=search) |
                models.Q(nit__icontains=search)
            )
        return queryset

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='clientes.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='clientes.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='clientes.eliminar')]
        return super().get_permissions()

    def perform_destroy(self, instance):
        instance.activo = False
        instance.save(update_fields=['activo'])


class LimiteConsumoViewSet(viewsets.ModelViewSet):
    queryset = LimiteConsumo.objects.select_related('cliente').all()
    serializer_class = LimiteConsumoSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'limites_consumo.ver'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['cliente', 'tipo', 'unidad', 'is_active']

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='limites_consumo.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='limites_consumo.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='limites_consumo.eliminar')]
        elif self.action == 'validar_consumo':
            return [IsAuthenticated(), HasPermiso(permiso='limites_consumo.validar')]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(cliente__nombre__icontains=search) |
                models.Q(cliente__email__icontains=search)
            )
        return queryset

    @action(detail=False, methods=['post'])
    def validar_consumo(self, request):
        serializer = ValidarConsumoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cliente_id = data['cliente_id']
        unidad = data['unidad']
        valor_consumo = data['valor_consumo']
        fecha = data['fecha']
        tipo = data.get('tipo')

        limites = LimiteConsumo.objects.filter(
            cliente_id=cliente_id,
            unidad=unidad,
            is_active=True,
        ).filter(
            models.Q(fecha_inicio__isnull=True) | models.Q(fecha_inicio__lte=fecha),
            models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=fecha),
        )
        if tipo:
            limites = limites.filter(tipo=tipo)

        for limite in limites:
            if valor_consumo > limite.valor:
                return Response(
                    {
                        'permitido': False,
                        'mensaje': (
                            f"Consumo rechazado: excede el límite {limite.tipo.lower()} "
                            f"({limite.valor} {limite.unidad.lower()})."
                        ),
                        'limite_id': limite.id,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response({'permitido': True, 'mensaje': 'Consumo dentro de los límites configurados.'})

    @action(detail=False, methods=['get'])
    def resumen_consumo(self, request):
        cliente_id = request.query_params.get('cliente_id')
        if not cliente_id:
            return Response(
                {'detail': 'cliente_id es requerido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cliente = VentasCliente.objects.get(id=cliente_id)
        except VentasCliente.DoesNotExist:
            return Response({'detail': 'Cliente no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        hoy = timezone.localdate()
        periodos = {
            'DIARIO': Venta.objects.filter(
                cliente_id=cliente.id,
                estado='COMPLETADA',
                fecha_hora__date=hoy,
            ),
            'MENSUAL': Venta.objects.filter(
                cliente_id=cliente.id,
                estado='COMPLETADA',
                fecha_hora__year=hoy.year,
                fecha_hora__month=hoy.month,
            ),
        }

        resumen = {}
        for tipo, ventas_qs in periodos.items():
            limite = (
                LimiteConsumo.objects.filter(
                    cliente_id=cliente.id,
                    tipo=tipo,
                    is_active=True,
                )
                .filter(
                    models.Q(fecha_inicio__isnull=True) | models.Q(fecha_inicio__lte=hoy),
                    models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=hoy),
                )
                .order_by('-updated_at')
                .first()
            )

            if limite and limite.unidad == 'LITROS':
                consumo = ventas_qs.aggregate(valor=Sum('litros'))['valor'] or 0
            else:
                consumo = ventas_qs.aggregate(valor=Sum('total'))['valor'] or 0

            if not limite:
                resumen[tipo] = {
                    'limite_configurado': None,
                    'consumo_acumulado': float(consumo),
                    'saldo_restante': None,
                    'unidad': 'MONTO',
                    'estado': 'SIN_LIMITE',
                }
                continue

            saldo = limite.valor - consumo
            excedido = saldo < 0
            resumen[tipo] = {
                'limite_configurado': float(limite.valor),
                'consumo_acumulado': float(consumo),
                'saldo_restante': float(max(saldo, 0)),
                'unidad': limite.unidad,
                'estado': 'EXCEDIDO' if excedido else 'DENTRO_LIMITE',
            }

        return Response(
            {
                'cliente_id': cliente.id,
                'cliente_nombre': cliente.nombre,
                'resumen': resumen,
            }
        )

# LOGIN/LOGOUT
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    email = request.data.get('email')
    password = request.data.get('password')

    # Normaliza para evitar fallos por espacios/case.
    if isinstance(email, str):
        email = email.strip().lower()
    
    user = authenticate(request, username=email, password=password)
    rol_obj = user.roles.first()
    nombres_del_rol = rol_obj.nombre if rol_obj else "Sin rol"
    if user:
        if not user.is_active:
            Bitacora.objects.create(
                usuario=user,
                usuario_email=user.email,
                usuario_nombre=user.nombre,
                usuario_rol=nombres_del_rol,
                accion='LOGIN',
                estado='ERROR',
                modulo_afectado='Administración y Seguridad',
                descripcion='Intento de inicio de sesión fallido',
                ip_address=getattr(request, 'ip_address', None),
                user_agent=getattr(request, 'user_agent', '')[:500] 
            )
            return Response({'error': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)
        
        refresh = RefreshToken.for_user(user)
        
        Bitacora.objects.create(
            usuario=user,
            usuario_email=user.email,
            usuario_nombre=user.nombre,
            usuario_rol=user.nombre_rol,
            accion='LOGIN',
            estado='EXITO',
            modulo_afectado='Administración y Seguridad',
            descripcion='Inicio de sesión exitoso',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )
        
        roles_ids = list(user.roles.values_list('id', flat=True))
        roles_detalle = [
            {'id': rol.id, 'nombre': rol.nombre}
            for rol in user.roles.all()
        ]
        
        return Response({
            'requested_email': email,
            'authenticated_email': user.email,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'nombre': user.nombre,
                'roles': roles_ids,
                'roles_detalle': roles_detalle,
            }
        })
    
    Bitacora.objects.create(
        usuario=None,
        usuario_email=email,
        usuario_nombre='Intento fallido',
        usuario_rol='Sin rol',
        accion='LOGIN',
        estado='ERROR',
        modulo_afectado='Administración y Seguridad',
        descripcion='Intento de inicio de sesión fallido',
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500]
    )
    
    return Response({'error': 'Credenciales inválidas', 'requested_email': email}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    Bitacora.objects.create(
        usuario=request.user,
        usuario_email=request.user.email,
        usuario_nombre=request.user.nombre,
        usuario_rol=request.user.nombre_rol,
        accion='LOGOUT',
        estado='EXITO',
        modulo_afectado='Administración y Seguridad',
        descripcion='Cierre de sesión exitoso',
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500]
    )
    return Response({'mensaje': 'Sesión cerrada correctamente'})

@api_view(['POST'])
@permission_classes([IsAuthenticated, HasPermiso])
def asignar_roles(request, pk):
    try:
        usuario = Usuario.objects.get(pk=pk)
    except Usuario.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=404)
    
    roles_ids = request.data.get('roles', [])
    usuario.roles.set(roles_ids)

    roles_nombres = ", ".join([r.nombre for r in usuario.roles.all()])
    
    Bitacora.objects.create(
        usuario=request.user,
        usuario_email=request.user.email,
        usuario_nombre=request.user.nombre,
        usuario_rol=request.user.nombre_rol,
        accion='EDITAR',
        estado='EXITO',
        modulo_afectado='Administración y Seguridad',
        descripcion=f'Asignó el rol de "{roles_nombres}" al usuario {usuario.email}',
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500]
    )
    
    return Response({'mensaje': 'Roles asignados correctamente'})

asignar_roles.permiso_requerido = 'usuarios.asignar_roles'

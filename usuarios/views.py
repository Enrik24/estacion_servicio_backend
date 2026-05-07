from django.utils import timezone
from django.db import models
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
    ValidarConsumoSerializer
)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora  # ← Importado de seguridad


def registrar_bitacora(request, accion, estado='EXITO', usuario_objetivo=None):
    usuario_log = request.user if request.user.is_authenticated else None
    Bitacora.objects.create(
        usuario=usuario_log,
        usuario_email=getattr(usuario_log, 'email', None),
        usuario_nombre=getattr(usuario_log, 'nombre', None),
        accion=accion,
        estado=estado,
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500]
    )

# CRUD USUARIOS
class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
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
            accion='ELIMINAR',
            estado='EXITO',
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
                accion='EDITAR',
                estado='EXITO',
                ip_address=getattr(request, 'ip_address', None),
                user_agent=getattr(request, 'user_agent', '')[:500]
            )
            
            return Response({'mensaje': 'Contraseña actualizada correctamente'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# CRUD ROLES
class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.prefetch_related('permisos')
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
    queryset = Permiso.objects.all()
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
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'clientes.ver'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']

    def get_queryset(self):
        queryset = Usuario.objects.filter(roles__nombre__iexact='Cliente').distinct().prefetch_related('roles')
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(models.Q(nombre__icontains=search) | models.Q(email__icontains=search))
        return queryset

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='clientes.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='clientes.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='clientes.eliminar')]
        return super().get_permissions()

    def _obtener_rol_cliente(self):
        rol_cliente = Rol.objects.filter(nombre__iexact='Cliente').first()
        if not rol_cliente:
            raise ValueError("No existe el rol 'Cliente'. Ejecuta el seed inicial.")
        return rol_cliente

    def perform_create(self, serializer):
        usuario = serializer.save()
        usuario.roles.set([self._obtener_rol_cliente()])
        registrar_bitacora(self.request, accion='CREAR')

    def perform_update(self, serializer):
        usuario = serializer.save()
        usuario.roles.set([self._obtener_rol_cliente()])
        registrar_bitacora(self.request, accion='EDITAR')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        registrar_bitacora(self.request, accion='ELIMINAR')


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
                models.Q(cliente__nombre__icontains=search)
                | models.Q(cliente__email__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save()
        registrar_bitacora(self.request, accion='CREAR')

    def perform_update(self, serializer):
        serializer.save()
        registrar_bitacora(self.request, accion='EDITAR')

    def perform_destroy(self, instance):
        instance.delete()
        registrar_bitacora(self.request, accion='ELIMINAR')

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
                registrar_bitacora(request, accion='EDITAR', estado='ERROR')
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

        registrar_bitacora(request, accion='EDITAR', estado='EXITO')
        return Response({'permitido': True, 'mensaje': 'Consumo dentro de los límites configurados.'})

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
    
    if user:
        if not user.is_active:
            Bitacora.objects.create(
                usuario=user,
                usuario_email=user.email,
                usuario_nombre=user.nombre,
                accion='LOGIN',
                estado='ERROR',
                ip_address=getattr(request, 'ip_address', None),
                user_agent=getattr(request, 'user_agent', '')[:500]
            )
            return Response({'error': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)
        
        refresh = RefreshToken.for_user(user)
        
        Bitacora.objects.create(
            usuario=user,
            usuario_email=user.email,
            usuario_nombre=user.nombre,
            accion='LOGIN',
            estado='EXITO',
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
        accion='LOGIN',
        estado='ERROR',
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
        accion='LOGOUT',
        estado='EXITO',
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
    
    return Response({'mensaje': 'Roles asignados correctamente'})

asignar_roles.permiso_requerido = 'usuarios.asignar_roles'

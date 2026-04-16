from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django_filters.rest_framework import DjangoFilterBackend

from .models import Usuario, Rol, Permiso
from .serializers import (
    UsuarioSerializer, UsuarioMeSerializer, RolSerializer, 
    PermisoSerializer, CambiarPasswordSerializer
)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora
from seguridad.bitacora_utils import registrar_bitacora, detectar_dispositivo, obtener_ip_cliente

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
    
    def create(self, request, *args, **kwargs):
        """POST - Crear usuario"""
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == 201:
            registrar_bitacora(
                usuario=request.user,
                accion='CREATE',
                modulo_afectado='Usuarios',
                descripcion=f'Se creó un nuevo usuario: {request.data.get("email")}',
                request=request,
                detalles={
                    'usuario_id': response.data.get('id'),
                    'email': request.data.get('email'),
                    'nombre': request.data.get('nombre', ''),
                }
            )
        
        return response
    
    def update(self, request, *args, **kwargs):
        """PUT/PATCH - Actualizar usuario"""
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        
        registrar_bitacora(
            usuario=request.user,
            accion='UPDATE',
            modulo_afectado='Usuarios',
            descripcion=f'Se actualizó el usuario: {instance.email}',
            request=request,
            detalles={
                'usuario_id': instance.id,
                'email': instance.email,
                'campos_modificados': list(request.data.keys()),
            }
        )
        
        return response
    
    def perform_destroy(self, instance):
        """Eliminar (desactivar) usuario"""
        instance.is_active = False
        instance.save()
        
        registrar_bitacora(
            usuario=self.request.user,
            accion='DELETE',
            modulo_afectado='Usuarios',
            descripcion=f'Se eliminó el usuario: {instance.email}',
            request=self.request,
            detalles={
                'usuario_id': instance.id,
                'email': instance.email,
            }
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
            
            registrar_bitacora(
                usuario=user,
                accion='UPDATE',
                modulo_afectado='Usuarios',
                descripcion=f'Cambió su contraseña: {user.email}',
                request=request,
                detalles={'usuario_id': user.id, 'email': user.email}
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
    
    def create(self, request, *args, **kwargs):
        """POST - Crear rol"""
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == 201:
            registrar_bitacora(
                usuario=request.user,
                accion='CREATE',
                modulo_afectado='Roles',
                descripcion=f'Se creó un nuevo rol: {request.data.get("nombre")}',
                request=request,
                detalles={
                    'rol_id': response.data.get('id'),
                    'nombre': request.data.get('nombre', ''),
                }
            )
        
        return response
    
    def update(self, request, *args, **kwargs):
        """PUT/PATCH - Actualizar rol"""
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        
        registrar_bitacora(
            usuario=request.user,
            accion='UPDATE',
            modulo_afectado='Roles',
            descripcion=f'Se actualizó el rol: {instance.nombre}',
            request=request,
            detalles={
                'rol_id': instance.id,
                'nombre': instance.nombre,
                'campos_modificados': list(request.data.keys()),
            }
        )
        
        return response
    
    def perform_destroy(self, instance):
        """Eliminar rol"""
        registrar_bitacora(
            usuario=self.request.user,
            accion='DELETE',
            modulo_afectado='Roles',
            descripcion=f'Se eliminó el rol: {instance.nombre}',
            request=self.request,
            detalles={'rol_id': instance.id, 'nombre': instance.nombre}
        )
        super().perform_destroy(instance)
    
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
    
    def create(self, request, *args, **kwargs):
        """POST - Crear permiso"""
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == 201:
            registrar_bitacora(
                usuario=request.user,
                accion='CREATE',
                modulo_afectado='Permisos',
                descripcion=f'Se creó un nuevo permiso: {request.data.get("codigo")}',
                request=request,
                detalles={
                    'permiso_id': response.data.get('id'),
                    'codigo': request.data.get('codigo', ''),
                }
            )
        
        return response
    
    def update(self, request, *args, **kwargs):
        """PUT/PATCH - Actualizar permiso"""
        instance = self.get_object()
        response = super().update(request, *args, **kwargs)
        
        registrar_bitacora(
            usuario=request.user,
            accion='UPDATE',
            modulo_afectado='Permisos',
            descripcion=f'Se actualizó el permiso: {instance.codigo}',
            request=request,
            detalles={
                'permiso_id': instance.id,
                'codigo': instance.codigo,
                'campos_modificados': list(request.data.keys()),
            }
        )
        
        return response
    
    def perform_destroy(self, instance):
        """Eliminar permiso"""
        registrar_bitacora(
            usuario=self.request.user,
            accion='DELETE',
            modulo_afectado='Permisos',
            descripcion=f'Se eliminó el permiso: {instance.codigo}',
            request=self.request,
            detalles={'permiso_id': instance.id, 'codigo': instance.codigo}
        )
        super().perform_destroy(instance)

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
            registrar_bitacora(
                usuario=user,
                accion='LOGIN',
                modulo_afectado='Autenticación',
                descripcion=f'Intento de login en usuario inactivo: {user.email}',
                request=request,
                detalles={'usuario_id': user.id, 'email': user.email, 'motivo': 'Usuario inactivo'}
            )
            return Response({'error': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)
        
        refresh = RefreshToken.for_user(user)
        
        registrar_bitacora(
            usuario=user,
            accion='LOGIN',
            modulo_afectado='Autenticación',
            descripcion=f'Se inició sesión: {user.email}',
            request=request,
            detalles={'usuario_id': user.id, 'email': user.email}
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
    
    registrar_bitacora(
        usuario=None,
        accion='LOGIN',
        modulo_afectado='Autenticación',
        descripcion=f'Intento fallido de login: {email}',
        request=request,
        detalles={'email': email, 'motivo': 'Credenciales inválidas'}
    )
    
    return Response({'error': 'Credenciales inválidas', 'requested_email': email}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    registrar_bitacora(
        usuario=request.user,
        accion='LOGOUT',
        modulo_afectado='Autenticación',
        descripcion=f'Se cerró sesión: {request.user.email}',
        request=request,
        detalles={'usuario_id': request.user.id, 'email': request.user.email}
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
    
    registrar_bitacora(
        usuario=request.user,
        accion='UPDATE',
        modulo_afectado='Usuarios',
        descripcion=f'Se asignaron roles al usuario: {usuario.email}',
        request=request,
        detalles={
            'usuario_id': usuario.id,
            'email': usuario.email,
            'roles_asignados': roles_ids
        }
    )
    
    return Response({'mensaje': 'Roles asignados correctamente'})

asignar_roles.permiso_requerido = 'usuarios.asignar_roles'
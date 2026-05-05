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
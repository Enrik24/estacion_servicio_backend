from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend

from .models import Usuario, Rol, Permiso, PasswordResetToken
from .serializers import (
    UsuarioSerializer, UsuarioMeSerializer, RolSerializer,
    PermisoSerializer, CambiarPasswordSerializer
)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora


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

    if isinstance(email, str):
        email = email.strip().lower()

    user = authenticate(request, username=email, password=password)
    rol_obj = user.roles.first() if user else None
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


# RECUPERACIÓN DE CONTRASEÑA
@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """
    POST /api/auth/request-reset/
    Solicita un enlace de recuperación de contraseña por email.
    Siempre retorna el mismo mensaje para no revelar si el email existe.
    """
    email = request.data.get('email', '')

    if isinstance(email, str):
        email = email.strip().lower()

    if not email:
        return Response(
            {'error': 'El campo email es requerido.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    usuario = Usuario.objects.filter(email=email).first()

    if usuario:
        reset_token = PasswordResetToken.objects.create(usuario=usuario)
        link = f"{settings.FRONTEND_URL}/reset-password/{reset_token.token}"

        asunto = "Recuperación de contraseña - SurtidorBolivia"
        cuerpo = (
            f"Hola {usuario.nombre},\n\n"
            f"Recibimos una solicitud para restablecer la contraseña de tu cuenta.\n\n"
            f"Haz clic en el siguiente enlace para crear una nueva contraseña:\n"
            f"{link}\n\n"
            f"⚠️ Este enlace expirará en 1 hora y solo puede usarse una vez.\n\n"
            f"Si no solicitaste este cambio, puedes ignorar este mensaje. "
            f"Tu contraseña actual seguirá siendo la misma.\n\n"
            f"— Equipo SurtidorBolivia"
        )

        try:
            send_mail(
                subject=asunto,
                message=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[usuario.email],
                fail_silently=False,
            )
        except Exception:
            reset_token.delete()
            return Response(
                {'error': 'No se pudo enviar el email. Intenta nuevamente más tarde.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        Bitacora.objects.create(
            usuario=usuario,
            usuario_email=usuario.email,
            usuario_nombre=usuario.nombre,
            usuario_rol=usuario.nombre_rol,
            accion='RECUPERACION_CONTRASENA',
            estado='EXITO',
            modulo_afectado='Administración y Seguridad',
            descripcion='Solicitó recuperación de contraseña. Email enviado exitosamente.',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )

    return Response(
        {'mensaje': 'Si el email está registrado, recibirás un enlace de recuperación en tu bandeja de entrada.'},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request, token):
    """
    POST /api/auth/reset-password/<uuid:token>/
    Restablece la contraseña usando el token de recuperación.
    """
    password = request.data.get('password', '')

    if not password or len(password) < 8:
        return Response(
            {'error': 'La contraseña debe tener al menos 8 caracteres.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        reset_token = PasswordResetToken.objects.select_related('usuario').get(token=token)
    except PasswordResetToken.DoesNotExist:
        return Response(
            {'error': 'Token de recuperación inválido.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not reset_token.is_valid():
        return Response(
            {'error': 'El enlace de recuperación ha expirado o ya fue utilizado.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    usuario = reset_token.usuario
    usuario.password = make_password(password)
    usuario.save(update_fields=['password'])

    reset_token.used = True
    reset_token.save(update_fields=['used'])

    Bitacora.objects.create(
        usuario=usuario,
        usuario_email=usuario.email,
        usuario_nombre=usuario.nombre,
        usuario_rol=usuario.nombre_rol,
        accion='RECUPERACION_CONTRASENA',
        estado='EXITO',
        modulo_afectado='Administración y Seguridad',
        descripcion='Contraseña restablecida exitosamente mediante enlace de recuperación.',
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500]
    )

    return Response(
        {'mensaje': 'Contraseña actualizada correctamente. Ya puedes iniciar sesión.'},
        status=status.HTTP_200_OK
    )


# AUTO-REGISTRO
@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """
    POST /api/auth/register/
    Permite a un usuario registrarse sin autenticación.
    No asigna roles — el administrador los asigna después.
    """
    nombre = request.data.get('nombre', '').strip()
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')

    if not nombre or not email or not password:
        return Response(
            {'error': 'Los campos nombre, email y password son requeridos.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(password) < 8:
        return Response(
            {'error': 'La contraseña debe tener al menos 8 caracteres.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if Usuario.objects.filter(email=email).exists():
        return Response(
            {'error': 'El email ya está registrado.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    usuario = Usuario.objects.create(nombre=nombre, email=email)
    usuario.set_password(password)
    usuario.save()

    Bitacora.objects.create(
        usuario=usuario,
        usuario_email=usuario.email,
        usuario_nombre=usuario.nombre,
        usuario_rol='Sin rol',
        accion='CREAR',
        estado='EXITO',
        modulo_afectado='Administración y Seguridad',
        descripcion='Nuevo usuario registrado mediante auto-registro.',
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500]
    )

    return Response(
        {
            'id': usuario.id,
            'nombre': usuario.nombre,
            'email': usuario.email,
        },
        status=status.HTTP_201_CREATED
    )

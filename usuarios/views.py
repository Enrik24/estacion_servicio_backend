from django.utils import timezone
from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend

from .models import Usuario, Rol, Permiso, PasswordResetToken, LimiteConsumo, EmailVerificationToken
from .serializers import (
    UsuarioSerializer, UsuarioMeSerializer, RolSerializer,
    PermisoSerializer, CambiarPasswordSerializer, LimiteConsumoSerializer,
    ValidarConsumoSerializer

)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora
from ventas.client_linking import resolve_cliente_for_usuario



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


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'true', '1', 'si', 'sí', 'yes', 'on'}
    return False


def _mask_email(email):
    if not email or '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked_local = local[0] + '*'
    else:
        masked_local = local[:2] + '*' * max(1, len(local) - 2)
    return f'{masked_local}@{domain}'


def _ensure_cliente_para_usuario(usuario):
    return resolve_cliente_for_usuario(usuario, create_if_missing=True)


def _send_verification_email(usuario, verification_token):
    verification_link = f"{settings.FRONTEND_URL}/verify-account/{verification_token.token}"
    asunto = "Verifica tu cuenta - SurtidorBolivia"
    cuerpo = (
        f"Hola {usuario.nombre},\n\n"
        f"Tu cuenta fue creada correctamente. Para activar el acceso debes verificar tu correo.\n\n"
        f"Haz clic en el siguiente enlace:\n"
        f"{verification_link}\n\n"
        f"Este enlace expira en 24 horas y solo puede usarse una vez.\n\n"
        f"Si no creaste esta cuenta, ignora este mensaje.\n\n"
        f"— Equipo SurtidorBolivia"
    )
    send_mail(
        subject=asunto,
        message=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email],
        fail_silently=False,
    )
    return verification_link


def _verification_response(usuario, verification_token):
    response_data = {
        'id': usuario.id,
        'nombre': usuario.nombre,
        'email': usuario.email,
        'email_mascara': _mask_email(usuario.email),
        'verification_required': True,
        'mensaje': 'Cuenta creada. Revisa tu correo para verificarla antes de iniciar sesión.',
    }
    if settings.DEBUG:
        response_data['verification_token'] = str(verification_token.token)
        response_data['verification_url'] = f"{settings.FRONTEND_URL}/verify-account/{verification_token.token}"
    return response_data

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

        if not user.email_verificado:
            Bitacora.objects.create(
                usuario=user,
                usuario_email=user.email,
                usuario_nombre=user.nombre,
                usuario_rol=nombres_del_rol,
                accion='LOGIN',
                estado='ERROR',
                modulo_afectado='Administración y Seguridad',
                descripcion='Intento de inicio de sesión con cuenta pendiente de verificación.',
                ip_address=getattr(request, 'ip_address', None),
                user_agent=getattr(request, 'user_agent', '')[:500]
            )
            return Response(
                {
                    'error': 'Debes verificar tu cuenta antes de iniciar sesión.',
                    'verification_required': True,
                    'email_mascara': _mask_email(user.email),
                },
                status=status.HTTP_403_FORBIDDEN
            )

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
    Crea una cuenta de cliente pendiente de verificación por correo.
    """
    nombre = request.data.get('nombre', '').strip()
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')
    password_confirmacion = request.data.get('password_confirmacion', '')
    acepta_politica_privacidad = _parse_bool(request.data.get('acepta_politica_privacidad', False))

    if not nombre or not email or not password:
        return Response(
            {'error': 'Los campos nombre, email y password son requeridos.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(nombre) < 2:
        return Response(
            {'error': 'El nombre debe tener al menos 2 caracteres.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if password != password_confirmacion:
        return Response(
            {'error': 'Las contraseñas no coinciden.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not acepta_politica_privacidad:
        return Response(
            {'error': 'Debes aceptar la política de privacidad para crear la cuenta.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_email(email)
    except DjangoValidationError:
        return Response(
            {'error': 'El correo electrónico no es válido.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_password(password)
    except DjangoValidationError as exc:
        return Response(
            {'error': ' '.join(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST
        )

    if Usuario.objects.filter(email=email).exists():
        Bitacora.objects.create(
            usuario=None,
            usuario_email=email,
            usuario_nombre=nombre or 'Registro fallido',
            usuario_rol='Sin rol',
            accion='CREAR',
            estado='ERROR',
            modulo_afectado='Administración y Seguridad',
            descripcion='Intento de registro rechazado por email duplicado.',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )
        return Response(
            {'error': 'El email ya está registrado.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with transaction.atomic():
            usuario = Usuario.objects.create(
                nombre=nombre,
                email=email,
                email_verificado=False,
                acepta_politica_privacidad_at=timezone.now(),
            )
            usuario.set_password(password)
            usuario.save(update_fields=['password', 'email_verificado', 'acepta_politica_privacidad_at'])

            rol_cliente = Rol.objects.filter(nombre__iexact='Cliente').first()
            if rol_cliente:
                usuario.roles.add(rol_cliente)

            _ensure_cliente_para_usuario(usuario)
            verification_token = EmailVerificationToken.objects.create(usuario=usuario)

            email_enviado = True
            try:
                _send_verification_email(usuario, verification_token)
            except Exception:
                if settings.DEBUG:
                    email_enviado = False
                else:
                    raise
    except Exception:
        Bitacora.objects.create(
            usuario=None,
            usuario_email=email,
            usuario_nombre=nombre,
            usuario_rol='Sin rol',
            accion='CREAR',
            estado='ERROR',
            modulo_afectado='Administración y Seguridad',
            descripcion='Falló el registro del cliente al generar o enviar la verificación de cuenta.',
            ip_address=getattr(request, 'ip_address', None),
            user_agent=getattr(request, 'user_agent', '')[:500]
        )
        return Response(
            {'error': 'No se pudo completar el registro en este momento. Intenta nuevamente más tarde.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    Bitacora.objects.create(
        usuario=usuario,
        usuario_email=usuario.email,
        usuario_nombre=usuario.nombre,
        usuario_rol=usuario.nombre_rol,
        accion='CREAR',
        estado='EXITO',
        modulo_afectado='Administración y Seguridad',
        descripcion='Nuevo cliente registrado mediante auto-registro con verificación de cuenta pendiente.' if email_enviado else 'Nuevo cliente registrado en modo desarrollo; verificación pendiente con token generado localmente.',
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500]
    )

    return Response(
        _verification_response(usuario, verification_token),
        status=status.HTTP_201_CREATED
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_account(request, token):
    try:
        verification_token = EmailVerificationToken.objects.select_related('usuario').get(token=token)
    except EmailVerificationToken.DoesNotExist:
        return Response(
            {'error': 'Token de verificación inválido.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not verification_token.is_valid():
        return Response(
            {'error': 'El enlace de verificación ha expirado o ya fue utilizado.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    usuario = verification_token.usuario
    usuario.email_verificado = True
    usuario.email_verificado_at = timezone.now()
    usuario.save(update_fields=['email_verificado', 'email_verificado_at'])

    verification_token.used = True
    verification_token.save(update_fields=['used'])

    Bitacora.objects.create(
        usuario=usuario,
        usuario_email=usuario.email,
        usuario_nombre=usuario.nombre,
        usuario_rol=usuario.nombre_rol,
        accion='EDITAR',
        estado='EXITO',
        modulo_afectado='Administración y Seguridad',
        descripcion='Cuenta de cliente verificada correctamente.',
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500]
    )

    return Response(
        {'mensaje': 'Cuenta verificada correctamente. Ya puedes iniciar sesión.'},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_email(request):
    email = request.data.get('email', '')
    if isinstance(email, str):
        email = email.strip().lower()

    if not email:
        return Response(
            {'error': 'El campo email es requerido.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    usuario = Usuario.objects.filter(email=email).first()
    if not usuario or usuario.email_verificado:
        return Response(
            {'mensaje': 'Si la cuenta existe y está pendiente, se enviará un nuevo enlace de verificación.'},
            status=status.HTTP_200_OK
        )

    verification_token = EmailVerificationToken.objects.create(usuario=usuario)
    try:
        _send_verification_email(usuario, verification_token)
        email_enviado = True
    except Exception:
        if not settings.DEBUG:
            return Response(
                {'error': 'No se pudo reenviar el correo de verificación. Intenta nuevamente más tarde.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        email_enviado = False

    Bitacora.objects.create(
        usuario=usuario,
        usuario_email=usuario.email,
        usuario_nombre=usuario.nombre,
        usuario_rol=usuario.nombre_rol,
        accion='EDITAR',
        estado='EXITO',
        modulo_afectado='Administración y Seguridad',
        descripcion='Reenvío de verificación de cuenta solicitado.' if email_enviado else 'Reenvío de verificación generado localmente en modo desarrollo.',
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500]
    )

    response_data = {
        'mensaje': 'Si la cuenta existe y está pendiente, se enviará un nuevo enlace de verificación.'
    }
    if settings.DEBUG:
        response_data['verification_token'] = str(verification_token.token)
        response_data['verification_url'] = f"{settings.FRONTEND_URL}/verify-account/{verification_token.token}"
    return Response(response_data, status=status.HTTP_200_OK)
asignar_roles.permiso_requerido = 'usuarios.asignar_roles'

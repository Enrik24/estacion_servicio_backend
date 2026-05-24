from django.utils import timezone
from django.db import models
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

from .models import Usuario, Rol, Permiso, LimiteConsumo,PasswordResetToken,Empresa
from .serializers import (
    UsuarioSerializer, UsuarioMeSerializer, RolSerializer,
    PermisoSerializer, CambiarPasswordSerializer, LimiteConsumoSerializer,
    ValidarConsumoSerializer, EmpresaSerializer, CrearEmpresaSerializer

)
from utils.permissions import HasPermiso
from seguridad.models import Bitacora,registrar_bitacora

# CRUD USUARIOS
class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('id')
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'usuarios.ver'
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'roles']
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Usuario.objects.all().order_by('id')
        if user.empresa:
            qs = Usuario.objects.filter(empresa=user.empresa).order_by('id')
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                qs = qs.filter(sucursal=user.sucursal)
            return qs
        return Usuario.objects.none()
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), HasPermiso(permiso='usuarios.crear')]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), HasPermiso(permiso='usuarios.editar')]
        elif self.action == 'destroy':
            return [IsAuthenticated(), HasPermiso(permiso='usuarios.eliminar')]
        return super().get_permissions()
    def perform_create(self, serializer):
        usuario = serializer.save(empresa=self.request.user.empresa)
        registrar_bitacora(
            self.request,
            accion='CREAR',
            modulo='Administración y Seguridad',
            descripcion=f'Creó el usuario: {usuario.email}',
        )

    def perform_update(self, serializer):
        usuario = serializer.save()
        registrar_bitacora(
            self.request,
            accion='EDITAR',
            modulo='Administración y Seguridad',
            descripcion=f'Editó el usuario: {usuario.email}',
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()

        request = self.request
        registrar_bitacora(
            request,
            accion='ELIMINAR',
            modulo='Administración y Seguridad',
            descripcion=f'Eliminó al usuario: {instance.email}',
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
                request,
                accion='EDITAR',
                modulo='Administración y Seguridad',
                descripcion='Cambió su contraseña',
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
    
class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all().order_by('-created_at')
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        if not self.request.user.is_superuser:
            return Empresa.objects.none()
        return super().get_queryset()

    def create(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Solo el super admin puede crear empresas'}, status=403)

        serializer = CrearEmpresaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        from django.db import transaction
        with transaction.atomic():
            empresa = Empresa.objects.create(
                nombre=data['nombre'],
                nit=data.get('nit') or None,
                telefono=data.get('telefono') or None,
                email=data.get('email') or None,
                direccion=data.get('direccion') or None,
                plan=data.get('plan', 'BASICO'),
                latitud=request.data.get('latitud') or None,
                longitud=request.data.get('longitud') or None,
            )

            # Crear tipos de combustible
            tipos_combustible = request.data.get('tipos_combustible', {})
            from ventas.models import TipoCombustible
            for tipo, precio in tipos_combustible.items():
                TipoCombustible.objects.create(
                    tipo=tipo,
                    precio_litro=precio,
                    empresa=empresa,
                    activo=True
                )

            rol_admin, _ = Rol.objects.get_or_create(nombre='Administrador')
            admin = Usuario.objects.create(
                nombre=data['admin_nombre'],
                email=data['admin_email'],
                empresa=empresa,
                is_staff=True,
            )
            admin.set_password(data['admin_password'])
            admin.save()
            admin.roles.set([rol_admin])

        return Response({
            'empresa': EmpresaSerializer(empresa).data,
            'admin': {
                'id': admin.id,
                'nombre': admin.nombre,
                'email': admin.email,
            }
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'])
    def cambiar_estado(self, request, pk=None):
        if not request.user.is_superuser:
            return Response({'error': 'Sin permiso'}, status=403)
        empresa = self.get_object()
        estado = request.data.get('estado')
        if estado not in ['ACTIVA', 'INACTIVA', 'SUSPENDIDA']:
            return Response({'error': 'Estado inválido'}, status=400)
        empresa.estado = estado
        empresa.save()
        return Response(EmpresaSerializer(empresa).data)
    def partial_update(self, request, pk=None):
        if not request.user.is_superuser:
            return Response({'error': 'Sin permiso'}, status=403)
        
        empresa = self.get_object()
        
        campos = ['nombre', 'nit', 'telefono', 'email', 'direccion', 'plan']
        for campo in campos:
            if campo in request.data:
                setattr(empresa, campo, request.data[campo])
        empresa.save()

        if request.data.get('nuevo_admin_email'):
            from django.db import transaction
            nuevo_email = request.data['nuevo_admin_email']
            nuevo_nombre = request.data.get('nuevo_admin_nombre', '')
            nuevo_password = request.data.get('nuevo_admin_password', '')

            if Usuario.objects.filter(email=nuevo_email).exclude(empresa=empresa).exists():
                return Response({'error': 'Este email ya está registrado en otra empresa'}, status=400)

            with transaction.atomic():
                rol_admin = Rol.objects.get(nombre='Administrador')
                nuevo_admin, created = Usuario.objects.get_or_create(
                    email=nuevo_email,
                    defaults={
                        'nombre': nuevo_nombre,
                        'empresa': empresa,
                        'is_staff': True,
                        'is_active': True,
                    }
                )
                if created and nuevo_password:
                    nuevo_admin.set_password(nuevo_password)
                    nuevo_admin.save()
                nuevo_admin.roles.set([rol_admin])

        return Response(EmpresaSerializer(empresa).data)
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
            registrar_bitacora(
                request,
                accion='LOGIN',
                estado='ERROR',
                modulo='Administración y Seguridad',
                descripcion='Intento de inicio de sesión con usuario inactivo',
            )
            return Response({'error': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)

        registrar_bitacora(
            request,
            accion='LOGIN',
            modulo='Administración y Seguridad',
            descripcion='Inicio de sesión exitoso',
            usuario=user,
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
                'is_superuser': user.is_superuser,
                'empresa_id': user.empresa_id,
                'empresa_nombre': user.empresa.nombre if user.empresa else None,
                'sucursal_id': user.sucursal_id,
                'sucursal_nombre': user.sucursal.nombre if user.sucursal else None,
                'roles': roles_ids,
                'roles_detalle': roles_detalle,
            }
        })

    registrar_bitacora(
            request,
            accion='LOGIN',
            estado='ERROR',
            modulo='Administración y Seguridad',
            descripcion='Intento de inicio de sesión fallido',
    )

    return Response({'error': 'Credenciales inválidas', 'requested_email': email}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    registrar_bitacora(
        request,
        accion='LOGOUT',
        modulo='Administración y Seguridad',
        descripcion='Cierre de sesión exitoso',
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

    

    return Response({'mensaje': 'Roles asignados correctamente'})

asignar_roles.permiso_requerido = 'usuarios.asignar_roles'

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

        registrar_bitacora(
            request,
            accion='RECUPERACION_CONTRASENA',
            modulo='Administración y Seguridad',
            descripcion='Solicitó recuperación de contraseña. Email enviado exitosamente.',
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

    registrar_bitacora(
        request,
        accion='RECUPERACION_CONTRASENA',
        modulo='Administración y Seguridad',
        descripcion='Contraseña restablecida exitosamente mediante enlace de recuperación.',
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

    registrar_bitacora(
        request,
        accion='CREAR',
        modulo='Administración y Seguridad',
        descripcion='Nuevo usuario registrado mediante auto-registro.',
    )

    return Response(
        {
            'id': usuario.id,
            'nombre': usuario.nombre,
            'email': usuario.email,
        },
        status=status.HTTP_201_CREATED
    )

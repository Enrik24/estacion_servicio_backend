from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from .models import Usuario, Rol, Permiso, LimiteConsumo
from ventas.models import Cliente as VentasCliente


def _usuario_tiene_rol_cliente(roles):
    return any((getattr(rol, 'nombre', '') or '').strip().lower() == 'cliente' for rol in roles)


def _norm_text(value):
    value = (value or "").strip()
    return value or None


def _norm_email(value):
    value = _norm_text(value)
    return value.lower() if value else None


def _norm_phone(value):
    value = _norm_text(value)
    return value


def _is_system_nit(value):
    value = (value or "").strip().upper()
    return value.startswith("USR")


def _upsert_cliente_ventas_desde_usuario(usuario):
    email = _norm_email(usuario.email)
    telefono = _norm_phone(getattr(usuario, "telefono", None))
    nombre = _norm_text(usuario.nombre) or "Cliente"

    cliente = None
    if email:
        cliente = VentasCliente.objects.filter(email__iexact=email).order_by("id").first()

    if not cliente:
        filtros = VentasCliente.objects.filter(nombre__iexact=nombre)
        if telefono:
            filtros = filtros.filter(telefono=telefono)
        cliente = filtros.order_by("id").first()

    if not cliente:
        cliente = VentasCliente(email=email)

    cliente.email = email
    cliente.nombre = nombre
    if telefono:
        cliente.telefono = telefono
    cliente.activo = bool(usuario.is_active)
    if _is_system_nit(cliente.nit):
        cliente.nit = None
    cliente.save()

    # Evitar duplicados en selector de ventas:
    # si hay más clientes con mismo email, desactivamos extras.
    if email:
        duplicados = VentasCliente.objects.filter(email__iexact=email).exclude(id=cliente.id)
        duplicados.update(activo=False)

class PermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permiso
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class RolSerializer(serializers.ModelSerializer):
    permisos_detalle = PermisoSerializer(source='permisos', many=True, read_only=True)
    permisos = serializers.PrimaryKeyRelatedField(
        queryset=Permiso.objects.all(), 
        many=True, 
        required=False
    )
    
    class Meta:
        model = Rol
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def create(self, validated_data):
        permisos = validated_data.pop('permisos', [])
        request = self.context.get('request')
        
        rol = Rol.objects.create(**validated_data)
        if permisos:
            rol.permisos.set(permisos)
            
        if request and request.user.is_authenticated:
            rol.created_by = request.user
            rol.updated_by = request.user
            rol.save()
            
        return rol
    
    def update(self, instance, validated_data):
        permisos = validated_data.pop('permisos', None)
        request = self.context.get('request')
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if permisos is not None:
            instance.permisos.set(permisos)
            
        if request and request.user.is_authenticated:
            instance.updated_by = request.user
            
        instance.save()
        return instance


class UsuarioSerializer(serializers.ModelSerializer):
    roles_detalle = RolSerializer(source='roles', many=True, read_only=True)
    roles = serializers.PrimaryKeyRelatedField(queryset=Rol.objects.all(), many=True, required=False)
    permisos = serializers.SerializerMethodField()
    # DRF no infiere automáticamente campos no-model. Sin esto, el `password`
    # enviado desde el frontend no llega a `validated_data` y el usuario queda
    # con una contraseña inutilizable, fallando el login.
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    
    class Meta:
        model = Usuario
        fields = [
            'id', 'nombre', 'email', 'is_active', 'is_staff',
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'roles', 'roles_detalle', 'permisos',
            'password'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def get_permisos(self, obj):
        permisos = set()
        for rol in obj.roles.all():
            for permiso in rol.permisos.all():
                permisos.add(permiso.codigo)
        return list(permisos)

    def create(self, validated_data):
        roles_data = validated_data.pop('roles', [])
        request = self.context.get('request')
        password = validated_data.pop('password', None)
        
        if not password:
            raise serializers.ValidationError({'password': 'La contraseña es obligatoria.'})

        usuario = Usuario.objects.create(**validated_data)
        usuario.set_password(password)
        usuario.save()
            
        if roles_data:
            usuario.roles.set(roles_data)

        if _usuario_tiene_rol_cliente(roles_data):
            _upsert_cliente_ventas_desde_usuario(usuario)
            
        if request and request.user.is_authenticated:
            usuario.created_by = request.user
            usuario.updated_by = request.user
            usuario.save()
            
        return usuario

    def update(self, instance, validated_data):
        roles_data = validated_data.pop('roles', None)
        request = self.context.get('request')
        
        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            else:
                setattr(instance, attr, value)
        
        if roles_data is not None:
            instance.roles.set(roles_data)
            roles_actuales = roles_data
        else:
            roles_actuales = instance.roles.all()
            
        if request and request.user.is_authenticated:
            instance.updated_by = request.user
            
        instance.save()
        if _usuario_tiene_rol_cliente(roles_actuales):
            _upsert_cliente_ventas_desde_usuario(instance)
        return instance


class UsuarioMeSerializer(serializers.ModelSerializer):
    roles = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    roles_detalle = RolSerializer(source='roles', many=True, read_only=True)
    permisos = serializers.SerializerMethodField()
    
    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'email', 'is_active', 'roles', 'roles_detalle', 'permisos']
    
    def get_permisos(self, obj):
        permisos = set()
        for rol in obj.roles.all():
            for permiso in rol.permisos.all():
                permisos.add(permiso.codigo)
        return list(permisos)


class CambiarPasswordSerializer(serializers.Serializer):
    password_actual = serializers.CharField(required=True)
    password_nuevo = serializers.CharField(required=True, min_length=8)
    password_confirmacion = serializers.CharField(required=True)

    def validate(self, data):
        if data['password_nuevo'] != data['password_confirmacion']:
            raise serializers.ValidationError("Las contraseñas nuevas no coinciden")
        return data


class ClienteSimpleSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(source='activo')

    class Meta:
        model = VentasCliente
        fields = ['id', 'nombre', 'email', 'nit', 'is_active']


class ClienteVentasSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(source='activo')

    class Meta:
        model = VentasCliente
        fields = ['id', 'nombre', 'email', 'nit', 'telefono', 'is_active']

    def create(self, validated_data):
        validated_data['activo'] = validated_data.get('activo', True)
        return super().create(validated_data)


class LimiteConsumoSerializer(serializers.ModelSerializer):
    cliente_detalle = ClienteSimpleSerializer(source='cliente', read_only=True)

    class Meta:
        model = LimiteConsumo
        fields = [
            'id', 'cliente', 'cliente_detalle', 'tipo', 'unidad', 'valor',
            'is_active', 'fecha_inicio', 'fecha_fin',
            'created_at', 'updated_at', 'created_by', 'updated_by',
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)

        cliente = attrs.get('cliente') or (instance.cliente if instance else None)
        tipo = attrs.get('tipo') or (instance.tipo if instance else None)
        valor = attrs.get('valor')
        if valor is None and instance:
            valor = instance.valor
        fecha_inicio = attrs.get('fecha_inicio')
        if fecha_inicio is None and instance:
            fecha_inicio = instance.fecha_inicio
        fecha_fin = attrs.get('fecha_fin')
        if fecha_fin is None and instance:
            fecha_fin = instance.fecha_fin
        is_active = attrs.get('is_active')
        if is_active is None:
            is_active = instance.is_active if instance else True

        if valor is None or Decimal(str(valor)) <= 0:
            raise serializers.ValidationError({'valor': 'El valor del límite debe ser mayor a 0.'})

        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            raise serializers.ValidationError({'fecha_fin': 'La fecha fin debe ser mayor o igual a la fecha inicio.'})

        if cliente and tipo and is_active:
            conflicto = LimiteConsumo.objects.filter(
                cliente=cliente,
                tipo=tipo,
                is_active=True,
            )
            if instance:
                conflicto = conflicto.exclude(id=instance.id)
            if conflicto.exists():
                raise serializers.ValidationError(
                    {'tipo': 'Ya existe un límite activo de este tipo para el cliente seleccionado.'}
                )

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        limite = LimiteConsumo.objects.create(**validated_data)
        if request and request.user.is_authenticated:
            limite.created_by = request.user
            limite.updated_by = request.user
            limite.save(update_fields=['created_by', 'updated_by'])
        return limite

    def update(self, instance, validated_data):
        request = self.context.get('request')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if request and request.user.is_authenticated:
            instance.updated_by = request.user
        instance.save()
        return instance


class ValidarConsumoSerializer(serializers.Serializer):
    cliente_id = serializers.IntegerField(required=True)
    unidad = serializers.ChoiceField(choices=LimiteConsumo.UNIDADES)
    valor_consumo = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    tipo = serializers.ChoiceField(choices=LimiteConsumo.TIPOS, required=False)
    fecha = serializers.DateField(required=False)

    def validate(self, attrs):
        cliente_id = attrs['cliente_id']
        if not VentasCliente.objects.filter(id=cliente_id, activo=True).exists():
            raise serializers.ValidationError({'cliente_id': 'Cliente no encontrado.'})
        attrs['fecha'] = attrs.get('fecha') or timezone.localdate()
        return attrs


class PrediccionConsumoRequestSerializer(serializers.Serializer):
    cliente_id = serializers.IntegerField(required=True)
    tipo_periodo = serializers.ChoiceField(choices=LimiteConsumo.TIPOS, required=False, default='DIARIO')
    unidad = serializers.ChoiceField(choices=LimiteConsumo.UNIDADES, required=False, default='MONTO')
    dias = serializers.IntegerField(required=False, min_value=1, max_value=31, default=7)

    def validate_cliente_id(self, value):
        if not VentasCliente.objects.filter(id=value, activo=True).exists():
            raise serializers.ValidationError('Cliente no encontrado.')
        return value

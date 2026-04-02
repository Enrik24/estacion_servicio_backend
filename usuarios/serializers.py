from rest_framework import serializers
from .models import Usuario, Rol, Permiso

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
            
        if request and request.user.is_authenticated:
            instance.updated_by = request.user
            
        instance.save()
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
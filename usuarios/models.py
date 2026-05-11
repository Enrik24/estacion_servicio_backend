from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from datetime import timedelta
import uuid
from .managers import UsuarioManager


class Permiso(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=100, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permisos_creados'
    )
    updated_by = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permisos_actualizados'
    )

    class Meta:
        db_table = 'permisos'
        verbose_name = 'Permiso'
        verbose_name_plural = 'Permisos'
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Rol(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    permisos = models.ManyToManyField(Permiso, related_name='roles', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roles_creados'
    )
    updated_by = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roles_actualizados'
    )

    class Meta:
        db_table = 'roles'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.nombre


class Usuario(AbstractBaseUser, PermissionsMixin):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    email = models.EmailField(unique=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios_creados'
    )
    updated_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios_actualizados'
    )

    roles = models.ManyToManyField(Rol, related_name='usuarios', blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre']

    objects = UsuarioManager()

    sucursal = models.ForeignKey(
        'ventas.Sucursal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios'
    )

    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.nombre} ({self.email})"

    @property
    def nombre_rol(self):
        rol = self.roles.first()
        if rol:
            return rol.nombre
        return "Sin rol"

    def tiene_permiso(self, codigo_permiso):
        """Verifica si el usuario tiene un permiso específico a través de sus roles"""
        if self.is_superuser:
            return True
        return self.roles.filter(permisos__codigo=codigo_permiso).exists()


class LimiteConsumo(models.Model):
    TIPOS = [
        ('DIARIO', 'Diario'),
        ('SEMANAL', 'Semanal'),
        ('MENSUAL', 'Mensual'),
    ]
    UNIDADES = [
        ('LITROS', 'Litros'),
        ('MONTO', 'Monto'),
    ]

    id = models.BigAutoField(primary_key=True)
    cliente = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='limites_consumo',
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    unidad = models.CharField(max_length=10, choices=UNIDADES)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='limites_creados',
    )
    updated_by = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='limites_actualizados',
    )

    class Meta:
        db_table = 'limites_consumo'
        verbose_name = 'Límite de Consumo'
        verbose_name_plural = 'Límites de Consumo'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'tipo'],
                condition=Q(is_active=True),
                name='uq_limite_activo_cliente_tipo',
            ),
        ]

    def __str__(self):
        return f"{self.cliente.email} - {self.tipo} ({self.unidad}: {self.valor})"
class PasswordResetToken(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    token = models.UUIDField(unique=True, editable=False, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at

    class Meta:
        db_table = 'password_reset_tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f"Token de {self.usuario.email} - {'válido' if self.is_valid() else 'inválido'}"

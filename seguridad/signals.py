# Signals para registrar automáticamente cambios en la bitácora
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from usuarios.models import Usuario, Rol, Permiso
from .models import Bitacora
from .bitacora_utils import registrar_bitacora


@receiver(post_save, sender=Usuario)
def registrar_cambios_usuario(sender, instance, created, **kwargs):
    """
    Registra automáticamente creaciones y actualizaciones de usuarios.
    Nota: El usuario actual debe estar disponible en el contexto de request.
    Por eso preferimos registrar desde las vistas en lugar de signals.
    """
    # Los signals NO tienen acceso a request, por lo que preferimos
    # hacerlo desde las vistas donde sí tenemos acceso a request
    pass


@receiver(post_save, sender=Rol)
def registrar_cambios_rol(sender, instance, created, **kwargs):
    """Registra cambios en roles"""
    pass


@receiver(post_save, sender=Permiso)
def registrar_cambios_permiso(sender, instance, created, **kwargs):
    """Registra cambios en permisos"""
    pass

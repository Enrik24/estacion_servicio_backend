# Signals si los necesitas después
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from usuarios.models import Usuario, Rol, Permiso
from .models import Bitacora

# Implementar según necesidad
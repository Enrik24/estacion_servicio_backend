from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    """No-op: el campo 'usuario' ya se crea en 0001_initial.

    Anteriormente esta migracion intentaba AddField('bitacora', 'usuario'),
    lo que causaba 'column usuario_id already exists' en despliegues limpios.
    Se deja vacia para no romper el historial de proyectos que ya la aplicaron.
    """

    dependencies = [
        ('seguridad', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = []

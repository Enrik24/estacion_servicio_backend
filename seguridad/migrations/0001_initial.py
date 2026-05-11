import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Bitacora',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('usuario_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('usuario_nombre', models.CharField(blank=True, max_length=150, null=True)),
                ('usuario_rol', models.CharField(blank=True, max_length=150, null=True)),
                ('accion', models.CharField(choices=[('LOGIN', 'Inicio de sesión'), ('LOGOUT', 'Cierre de sesión'), ('CREAR', 'Creación'), ('EDITAR', 'Edición'), ('ELIMINAR', 'Eliminación')], max_length=20)),
                ('estado', models.CharField(choices=[('EXITO', 'Éxito'), ('ERROR', 'Error')], max_length=20)),
                ('modulo_afectado', models.CharField(blank=True, max_length=150, null=True)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=500, null=True)),
                ('fecha_hora', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Bitácora',
                'verbose_name_plural': 'Bitácoras',
                'db_table': 'bitacora',
                'ordering': ['-fecha_hora'],
            },
        ),
    ]

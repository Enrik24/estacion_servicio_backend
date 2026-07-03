from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0007_sucursal_tipos_combustible'),
        ('usuarios', '0006_empresa_latitud_empresa_longitud'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='puntos_acumulados',
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name='ConfiguracionPuntos',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('activo', models.BooleanField(default=True)),
                ('puntos_por_litro', models.DecimalField(decimal_places=2, default=1, max_digits=6)),
                ('valor_punto_bs', models.DecimalField(decimal_places=4, default=0.10, max_digits=6)),
                ('minimo_canje', models.IntegerField(default=100)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('empresa', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='config_puntos',
                    to='usuarios.empresa',
                )),
            ],
            options={
                'db_table': 'configuracion_puntos',
                'verbose_name': 'Configuración de Puntos',
                'verbose_name_plural': 'Configuraciones de Puntos',
            },
        ),
        migrations.CreateModel(
            name='MovimientoPuntos',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('tipo', models.CharField(choices=[
                    ('ACUMULACION', 'Acumulación por venta'),
                    ('CANJE', 'Canje en venta'),
                    ('AJUSTE', 'Ajuste manual'),
                    ('REVERSA', 'Reversa por anulación'),
                ], max_length=15)),
                ('puntos', models.IntegerField()),
                ('saldo_despues', models.IntegerField()),
                ('descripcion', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='movimientos_puntos',
                    to='ventas.cliente',
                )),
                ('venta', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='movimientos_puntos',
                    to='ventas.venta',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='movimientos_puntos_registrados',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'movimientos_puntos',
                'verbose_name': 'Movimiento de Puntos',
                'verbose_name_plural': 'Movimientos de Puntos',
                'ordering': ['-created_at'],
            },
        ),
    ]

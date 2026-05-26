from django.db import migrations, models
import django.db.models.deletion


def _es_usuario_cliente(usuario):
    return (
        usuario is not None and
        not usuario.is_staff and
        not usuario.is_superuser and
        getattr(usuario, 'sucursal_id', None) is None
    )


def backfill_cliente_usuario(apps, schema_editor):
    Cliente = apps.get_model('ventas', 'Cliente')
    Usuario = apps.get_model('usuarios', 'Usuario')

    for usuario in Usuario.objects.all().order_by('id'):
        if not _es_usuario_cliente(usuario):
            continue

        email = (usuario.email or '').strip().lower()
        cliente = Cliente.objects.filter(usuario_id=usuario.id).first()
        if cliente is None and email:
            cliente = Cliente.objects.filter(email__iexact=email).order_by('id').first()
        if cliente is None:
            coincidencias_nombre = Cliente.objects.filter(nombre__iexact=usuario.nombre).order_by('id')
            if coincidencias_nombre.count() == 1:
                cliente = coincidencias_nombre.first()

        if cliente is None:
            Cliente.objects.create(
                nombre=usuario.nombre,
                email=email or None,
                activo=True,
                usuario_id=usuario.id,
            )
            continue

        updates = []
        if cliente.usuario_id != usuario.id:
            cliente.usuario_id = usuario.id
            updates.append('usuario')
        if email and cliente.email != email:
            cliente.email = email
            updates.append('email')
        if not cliente.activo:
            cliente.activo = True
            updates.append('activo')
        if updates:
            cliente.save(update_fields=updates)


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_usuario_acepta_politica_privacidad_at_and_more'),
        ('ventas', '0003_venta_client_request_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='usuario',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cliente_ventas',
                to='usuarios.usuario',
            ),
        ),
        migrations.RunPython(backfill_cliente_usuario, migrations.RunPython.noop),
    ]

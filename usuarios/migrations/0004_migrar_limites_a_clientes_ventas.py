from django.db import migrations, models
import django.db.models.deletion


def asegurar_clientes_ventas_para_limites(apps, schema_editor):
    LimiteConsumo = apps.get_model("usuarios", "LimiteConsumo")
    Usuario = apps.get_model("usuarios", "Usuario")
    ClienteVentas = apps.get_model("ventas", "Cliente")

    ids_clientes = (
        LimiteConsumo.objects.exclude(cliente_id__isnull=True)
        .values_list("cliente_id", flat=True)
        .distinct()
    )

    for cliente_id in ids_clientes:
        if ClienteVentas.objects.filter(id=cliente_id).exists():
            continue

        usuario = Usuario.objects.filter(id=cliente_id).first()
        nombre = usuario.nombre if usuario else f"Cliente {cliente_id}"
        nit = f"MIG{cliente_id:06d}"
        if ClienteVentas.objects.filter(nit=nit).exists():
            nit = None

        ClienteVentas.objects.create(
            id=cliente_id,
            nombre=nombre,
            nit=nit,
            activo=True,
            limite_credito=0,
            saldo_credito=0,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0003_vehiculo"),
        ("usuarios", "0003_limiteconsumo_and_more"),
    ]

    operations = [
        migrations.RunPython(
            asegurar_clientes_ventas_para_limites,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="limiteconsumo",
            name="cliente",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="limites_consumo",
                to="ventas.cliente",
            ),
        ),
    ]

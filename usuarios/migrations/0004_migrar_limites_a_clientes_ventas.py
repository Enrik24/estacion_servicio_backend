from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0003_vehiculo"),
        ("usuarios", "0003_limiteconsumo_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="limiteconsumo",
                    name="cliente",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="limites_consumo",
                        to="ventas.cliente",
                    ),
                ),
            ],
            database_operations=[],  # FK y constraint ya existen en DB
        ),
    ]

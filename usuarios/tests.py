from django.test import TestCase
from usuarios.models import Usuario, Rol, LimiteConsumo
from usuarios.serializers import LimiteConsumoSerializer


class LimiteConsumoSerializerTest(TestCase):
    def setUp(self):
        self.rol_cliente = Rol.objects.create(nombre='Cliente', descripcion='Rol cliente')
        self.cliente = Usuario.objects.create(nombre='Cliente Demo', email='cliente@demo.com')
        self.cliente.roles.set([self.rol_cliente])

    def test_no_permite_limites_activos_duplicados_por_tipo(self):
        LimiteConsumo.objects.create(
            cliente=self.cliente,
            tipo='DIARIO',
            unidad='LITROS',
            valor='100.00',
            is_active=True,
        )
        serializer = LimiteConsumoSerializer(data={
            'cliente': self.cliente.id,
            'tipo': 'DIARIO',
            'unidad': 'MONTO',
            'valor': '200.00',
            'is_active': True,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_valida_rango_de_fechas(self):
        serializer = LimiteConsumoSerializer(data={
            'cliente': self.cliente.id,
            'tipo': 'SEMANAL',
            'unidad': 'LITROS',
            'valor': '50.00',
            'is_active': True,
            'fecha_inicio': '2026-04-20',
            'fecha_fin': '2026-04-10',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('fecha_fin', serializer.errors)

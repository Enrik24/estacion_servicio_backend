import uuid

from rest_framework.test import APITestCase

from usuarios.models import Usuario
from .models import Sucursal, Isla, Lado, Turno, TipoCombustible, Venta, Cliente


class VentaIdempotenciaTests(APITestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            email='test_admin@estacion.com',
            nombre='Test Admin',
            password='test1234',
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.user)

        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Test',
            direccion='Dir Test',
            telefono='0',
            nit='0',
            cantidad_islas=1,
            tiene_gnv=False,
            estado='ACTIVA',
        )
        self.isla = Isla.objects.create(numero=99, sucursal=self.sucursal, estado='ACTIVO')
        self.lado = Lado.objects.create(isla=self.isla, lado='A', activo=True)
        self.turno = Turno.objects.create(
            operador=self.user,
            isla=self.isla,
            horario='MANANA',
            estado='ABIERTO',
            monto_inicial=0,
            sucursal=self.sucursal,
        )
        self.tipo = TipoCombustible.objects.create(
            tipo='GASOLINA_ESPECIAL',
            precio_litro=6.96,
            activo=True,
        )

    def test_crear_venta_con_idempotencia_no_duplica(self):
        request_id = uuid.uuid4()
        payload = {
            'lado_id': self.lado.id,
            'tipo_combustible_id': self.tipo.id,
            'monto_bs': '100.00',
            'metodo_pago': 'EFECTIVO',
            'es_lleno': False,
            'client_request_id': str(request_id),
        }

        res1 = self.client.post('/api/ventas/', payload, format='json')
        self.assertIn(res1.status_code, [200, 201])
        venta_id_1 = res1.data.get('id')

        res2 = self.client.post('/api/ventas/', payload, format='json')
        self.assertEqual(res2.status_code, 200)
        venta_id_2 = res2.data.get('id')

        self.assertEqual(venta_id_1, venta_id_2)
        self.assertEqual(Venta.objects.filter(created_by=self.user, client_request_id=request_id).count(), 1)


class ComprasSincronizacionTests(APITestCase):
    def setUp(self):
        self.operador = Usuario.objects.create_user(
            email='operador@estacion.com',
            nombre='Operador',
            password='test1234',
            is_superuser=True,
        )
        self.cliente_user = Usuario.objects.create_user(
            email='cliente@app.com',
            nombre='Cliente App',
            password='test1234',
        )

        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Test 2',
            direccion='Dir Test',
            telefono='0',
            nit='1',
            cantidad_islas=1,
            tiene_gnv=False,
            estado='ACTIVA',
        )
        self.isla = Isla.objects.create(numero=98, sucursal=self.sucursal, estado='ACTIVO')
        self.lado = Lado.objects.create(isla=self.isla, lado='A', activo=True)
        self.turno = Turno.objects.create(
            operador=self.operador,
            isla=self.isla,
            horario='MANANA',
            estado='ABIERTO',
            monto_inicial=0,
            sucursal=self.sucursal,
        )
        self.tipo = TipoCombustible.objects.create(
            tipo='GASOLINA_PREMIUM',
            precio_litro=11.00,
            activo=True,
        )

    def test_historial_movil_incluye_venta_web_del_cliente(self):
        self.client.force_authenticate(user=self.cliente_user)
        res1 = self.client.get('/api/compras/')
        self.assertEqual(res1.status_code, 200)

        from ventas.models import Cliente
        cliente = Cliente.objects.filter(email=self.cliente_user.email).first()
        self.assertIsNotNone(cliente)

        Venta.objects.create(
            turno=self.turno,
            lado=self.lado,
            tipo_combustible=self.tipo,
            cliente=cliente,
            litros=9.091,
            precio_unitario=self.tipo.precio_litro,
            total=100,
            metodo_pago='EFECTIVO',
            numero_comprobante='TEST-SYNC-1',
            created_by=self.operador,
        )

        res2 = self.client.get('/api/compras/')
        self.assertEqual(res2.status_code, 200)
        data = res2.data
        results = data if isinstance(data, list) else data.get('results', [])
        self.assertTrue(any(str(item.get('total')) == '100' or str(item.get('total')) == '100.00' for item in results))

    def test_registrar_venta_con_cliente_duplicado_la_asocia_al_cliente_vinculado(self):
        cliente_canonico = Cliente.objects.create(
            nombre='alexander',
            email='alex.prueba@example.com',
            activo=True,
            usuario=self.cliente_user,
        )
        cliente_duplicado = Cliente.objects.create(
            nombre='alexander',
            activo=True,
        )

        self.client.force_authenticate(user=self.operador)
        response = self.client.post(
            '/api/ventas/',
            {
                'lado_id': self.lado.id,
                'tipo_combustible_id': self.tipo.id,
                'monto_bs': '120.00',
                'metodo_pago': 'EFECTIVO',
                'cliente_id': cliente_duplicado.id,
                'es_lleno': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        venta = Venta.objects.get(id=response.data['id'])
        self.assertEqual(venta.cliente_id, cliente_canonico.id)

        self.client.force_authenticate(user=self.cliente_user)
        historial = self.client.get('/api/compras/')
        self.assertEqual(historial.status_code, 200)
        results = historial.data if isinstance(historial.data, list) else historial.data.get('results', [])
        self.assertTrue(any(str(item.get('total')) in {'120', '120.00'} for item in results))

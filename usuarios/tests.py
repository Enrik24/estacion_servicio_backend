from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from seguridad.models import Bitacora
from usuarios.models import Usuario, Rol, LimiteConsumo, EmailVerificationToken
from usuarios.serializers import LimiteConsumoSerializer
from ventas.models import Cliente



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

@override_settings(FRONTEND_URL='http://localhost:5173')
class RegistroClienteTests(APITestCase):
    def setUp(self):
        self.rol_cliente = Rol.objects.create(nombre='Cliente', descripcion='Rol cliente')
        self.payload = {
            'nombre': 'Fer Cliente',
            'email': 'fer.prueba@example.com',
            'password': 'ClaveSegura123!',
            'password_confirmacion': 'ClaveSegura123!',
            'acepta_politica_privacidad': True,
        }

    @patch('usuarios.views.send_mail', return_value=1)
    def test_registro_crea_usuario_cliente_y_token_de_verificacion(self, _send_mail):
        response = self.client.post('/api/auth/register/', self.payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['verification_required'])

        usuario = Usuario.objects.get(email='fer.prueba@example.com')
        self.assertFalse(usuario.email_verificado)
        self.assertIsNotNone(usuario.acepta_politica_privacidad_at)
        self.assertTrue(usuario.roles.filter(nombre='Cliente').exists())
        cliente = Cliente.objects.get(email='fer.prueba@example.com')
        self.assertEqual(cliente.usuario_id, usuario.id)
        self.assertTrue(EmailVerificationToken.objects.filter(usuario=usuario).exists())
        self.assertTrue(
            Bitacora.objects.filter(
                usuario_email='fer.prueba@example.com',
                accion='CREAR',
                estado='EXITO',
            ).exists()
        )

    def test_registro_rechaza_sin_consentimiento(self):
        payload = dict(self.payload)
        payload['acepta_politica_privacidad'] = False

        response = self.client.post('/api/auth/register/', payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('política de privacidad', response.data['error'])

    def test_registro_rechaza_email_duplicado(self):
        Usuario.objects.create_user(
            email='fer.prueba@example.com',
            nombre='Fer Existente',
            password='ClaveSegura123!',
        )

        response = self.client.post('/api/auth/register/', self.payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error'], 'El email ya está registrado.')
        self.assertTrue(
            Bitacora.objects.filter(
                usuario_email='fer.prueba@example.com',
                accion='CREAR',
                estado='ERROR',
            ).exists()
        )

    @patch('usuarios.views.send_mail', return_value=1)
    def test_login_bloqueado_hasta_verificar_cuenta(self, _send_mail):
        self.client.post('/api/auth/register/', self.payload, format='json')

        response = self.client.post(
            '/api/auth/login/',
            {'email': 'fer.prueba@example.com', 'password': 'ClaveSegura123!'},
            format='json'
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.data['verification_required'])

    @patch('usuarios.views.send_mail', return_value=1)
    def test_verificar_cuenta_habilita_login(self, _send_mail):
        self.client.post('/api/auth/register/', self.payload, format='json')
        usuario = Usuario.objects.get(email='fer.prueba@example.com')
        token = EmailVerificationToken.objects.get(usuario=usuario)

        verify_response = self.client.post(f'/api/auth/verify-account/{token.token}/', format='json')
        login_response = self.client.post(
            '/api/auth/login/',
            {'email': 'fer.prueba@example.com', 'password': 'ClaveSegura123!'},
            format='json'
        )

        self.assertEqual(verify_response.status_code, 200)
        usuario.refresh_from_db()
        token.refresh_from_db()
        self.assertTrue(usuario.email_verificado)
        self.assertTrue(token.used)
        self.assertEqual(login_response.status_code, 200)

    @override_settings(DEBUG=False)
    @patch('usuarios.views.send_mail', side_effect=Exception('smtp down'))
    def test_registro_revierte_si_falla_envio_en_produccion(self, _send_mail):
        response = self.client.post('/api/auth/register/', self.payload, format='json')

        self.assertEqual(response.status_code, 500)
        self.assertFalse(Usuario.objects.filter(email='fer.prueba@example.com').exists())
        self.assertFalse(Cliente.objects.filter(email='fer.prueba@example.com').exists())


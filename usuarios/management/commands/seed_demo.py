"""Seed masivo para poblar el sistema con datos realistas.

Crea multiples empresas (tenants), cada una con:
  - 1 administrador de empresa
  - 2 sucursales con lat/lng
  - Islas, lados, tanques por sucursal
  - 1 gerente y 3 operadores por sucursal
  - 15 clientes con vehiculos por empresa
  - Configuracion de puntos activa
  - Historial de N dias con turnos cerrados y ventas realistas
  - Ultimo dia con un turno ABIERTO por sucursal para que puedas registrar mas

Uso:
    python manage.py seed_demo
    python manage.py seed_demo --empresas 4 --dias 15
    python manage.py seed_demo --wipe   # borra tenants demo previos

Requisitos:
    Antes de correr, ejecuta: python manage.py seed
    (necesita los roles Administrador / Gerente / Operador ya creados)
"""

import random
import uuid
from datetime import datetime, timedelta, time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from usuarios.models import Empresa, Usuario, Rol
from ventas.models import (
    TipoCombustible, Sucursal, Isla, Lado, Turno, Cliente, Vehiculo,
    Venta, EmpresaCliente, ConfiguracionPuntos,
)
from inventario.models import Tanque, DescargaCombustible
from monitoreo.models import EstadoSurtidor
from ventas import puntos_service


# ── Datos de referencia ─────────────────────────────────────────────────────

EMPRESAS_DEMO = [
    {
        'nombre': 'GasBol S.A.',
        'nit': '2000000001',
        'telefono': '3-1111111',
        'email': 'contacto@gasbol.com.bo',
        'direccion': 'Av. Cristo Redentor, Santa Cruz',
        'plan': 'PROFESIONAL',
        'lat': -17.7833, 'lng': -63.1821,
        'dominio': 'gasbol',
    },
    {
        'nombre': 'PetroCruz Ltda.',
        'nit': '2000000002',
        'telefono': '2-2222222',
        'email': 'info@petrocruz.bo',
        'direccion': 'Calle Comercio, La Paz',
        'plan': 'ENTERPRISE',
        'lat': -16.5000, 'lng': -68.1500,
        'dominio': 'petrocruz',
    },
    {
        'nombre': 'YPFB Andina Norte',
        'nit': '2000000003',
        'telefono': '4-3333333',
        'email': 'norte@ypfb-andina.bo',
        'direccion': 'Av. Blanco Galindo km 6, Cochabamba',
        'plan': 'PROFESIONAL',
        'lat': -17.3895, 'lng': -66.1568,
        'dominio': 'ypfbnorte',
    },
    {
        'nombre': 'BoliGas Corp.',
        'nit': '2000000004',
        'telefono': '4-4444444',
        'email': 'ventas@boligas.bo',
        'direccion': 'Calle Bolivar, Sucre',
        'plan': 'BASICO',
        'lat': -19.0333, 'lng': -65.2627,
        'dominio': 'boligas',
    },
]

SUCURSALES_POR_EMPRESA = [
    [
        {'sufijo': 'Centro', 'direccion': 'Av. Uruguay 100', 'lat_off': 0.001, 'lng_off': 0.001},
        {'sufijo': 'Sur', 'direccion': 'Av. Doble Via La Guardia', 'lat_off': -0.02, 'lng_off': 0.01},
    ],
    [
        {'sufijo': 'El Alto', 'direccion': 'Av. Juan Pablo II', 'lat_off': 0.05, 'lng_off': -0.03},
        {'sufijo': 'Zona Sur', 'direccion': 'Calacoto', 'lat_off': -0.04, 'lng_off': 0.02},
    ],
    [
        {'sufijo': 'Cala Cala', 'direccion': 'Av. America', 'lat_off': 0.01, 'lng_off': 0.01},
        {'sufijo': 'Quillacollo', 'direccion': 'Av. Blanco Galindo km 13', 'lat_off': -0.03, 'lng_off': -0.05},
    ],
    [
        {'sufijo': 'Central', 'direccion': 'Plaza 25 de Mayo', 'lat_off': 0.001, 'lng_off': 0.001},
        {'sufijo': 'Ruta 5', 'direccion': 'Ingreso Sur', 'lat_off': -0.01, 'lng_off': 0.02},
    ],
]

NOMBRES_PERSONAS = [
    'Juan Perez', 'Maria Lopez', 'Carlos Vaca', 'Sofia Rojas', 'Luis Mendoza',
    'Ana Torres', 'Diego Flores', 'Camila Cruz', 'Pedro Aguilar', 'Rosa Vargas',
    'Andres Ortiz', 'Lucia Castro', 'Ricardo Salinas', 'Elena Vidal', 'Jorge Rico',
    'Patricia Ibanez', 'Fernando Suarez', 'Isabel Guerra', 'Manuel Rios', 'Silvia Paz',
    'Roberto Melgar', 'Carmen Bejarano', 'Oscar Aponte', 'Veronica Cuellar', 'Javier Nava',
    'Miguel Angel Soto', 'Gabriela Peredo', 'Nestor Chumacero', 'Andrea Barba', 'Ivan Duran',
]

EMPRESAS_CLIENTE = [
    'Transportes Ruta Real', 'Logistica Andina', 'Distribuidora Cruceña',
    'Constructora del Sur', 'Servicios Petroleros SRL', 'Cooperativa 24 de Septiembre',
    'Taxis El Rapido', 'Buses Trans Bolivia',
]

MARCAS_VEHICULO = ['Toyota', 'Nissan', 'Suzuki', 'Chevrolet', 'Hyundai', 'Ford', 'Mitsubishi', 'Kia']
MODELOS_VEHICULO = ['Hilux', 'Corolla', 'Sentra', 'Grand Vitara', 'Aveo', 'Accent', 'Ranger', 'L200', 'Sportage']
COLORES = ['Blanco', 'Negro', 'Gris', 'Rojo', 'Azul', 'Plata']

TIPOS_COMBUSTIBLE_BASE = [
    {'tipo': 'GASOLINA_ESPECIAL', 'precio_litro': Decimal('6.96')},
    {'tipo': 'GASOLINA_PREMIUM', 'precio_litro': Decimal('11.00')},
    {'tipo': 'DIESEL', 'precio_litro': Decimal('9.80')},
]

METODOS_PAGO_PONDERADOS = (
    ['EFECTIVO'] * 55 +
    ['TARJETA'] * 15 +
    ['QR'] * 20 +
    ['CREDITO_FLEET'] * 10
)


def rand_placa():
    letras = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ', k=3))
    numeros = ''.join(random.choices('0123456789', k=4))
    return f'{numeros}-{letras}'


def rand_nit():
    return ''.join(random.choices('0123456789', k=random.choice([7, 8, 9, 10])))


def rand_telefono():
    return f'{random.choice([6, 7])}{random.randint(1000000, 9999999)}'


class Command(BaseCommand):
    help = 'Seed masivo con multiples tenants, sucursales, clientes y ventas historicas'

    def add_arguments(self, parser):
        parser.add_argument('--empresas', type=int, default=3,
                            help='Cantidad de empresas a crear (max 4)')
        parser.add_argument('--dias', type=int, default=7,
                            help='Dias de historial de ventas')
        parser.add_argument('--ventas-por-turno', type=int, default=18,
                            help='Ventas promedio por turno')
        parser.add_argument('--wipe', action='store_true',
                            help='Borra ventas/turnos/clientes/sucursales de empresas demo antes de crear')

    def handle(self, *args, **opts):
        n_empresas = min(opts['empresas'], len(EMPRESAS_DEMO))
        n_dias = opts['dias']
        vpt = opts['ventas_por_turno']
        wipe = opts['wipe']

        self.stdout.write(self.style.NOTICE(
            f'\n=== Seed demo: {n_empresas} empresas, {n_dias} dias historial, ~{vpt} ventas/turno ===\n'
        ))

        # Verificar prerequisitos
        for rname in ['Administrador', 'Gerente', 'Operador']:
            if not Rol.objects.filter(nombre=rname).exists():
                self.stdout.write(self.style.ERROR(
                    f'Rol "{rname}" no existe. Corre primero: python manage.py seed'
                ))
                return

        self.rol_admin = Rol.objects.get(nombre='Administrador')
        self.rol_gerente = Rol.objects.get(nombre='Gerente')
        self.rol_operador = Rol.objects.get(nombre='Operador')

        empresas_seleccionadas = EMPRESAS_DEMO[:n_empresas]

        if wipe:
            self._wipe(empresas_seleccionadas)

        random.seed(42)  # reproducible

        # Diccionario que rastrea todos los usuarios generados por empresa
        # {empresa_nombre: [{'rol': str, 'nombre': str, 'email': str, 'password': str, 'sucursal': str}]}
        self.credenciales_por_empresa = {}

        with transaction.atomic():
            for idx, emp_data in enumerate(empresas_seleccionadas):
                self.stdout.write(self.style.MIGRATE_HEADING(
                    f'\n[{idx+1}/{n_empresas}] Creando "{emp_data["nombre"]}"...'
                ))
                self.credenciales_por_empresa[emp_data['nombre']] = []

                empresa = self._crear_empresa(emp_data)
                admin_email = self._crear_admin_empresa(empresa, emp_data)
                self.credenciales_por_empresa[emp_data['nombre']].append({
                    'rol': 'Administrador',
                    'nombre': f'Admin {empresa.nombre}',
                    'email': admin_email,
                    'password': 'demo123',
                    'sucursal': '—',
                })

                tipos = self._crear_tipos_combustible(empresa)
                self._crear_config_puntos(empresa)
                sucursales_info = self._crear_sucursales(empresa, emp_data, idx, tipos)
                clientes = self._crear_clientes(empresa)
                self._crear_ventas_historicas(
                    empresa, sucursales_info, clientes, tipos, n_dias, vpt,
                )

                self.stdout.write(self.style.SUCCESS(
                    f'  OK "{emp_data["nombre"]}" — admin: {admin_email} / demo123'
                ))

        self._imprimir_resumen(empresas_seleccionadas)
        self._exportar_credenciales()

    # ── Wipe ────────────────────────────────────────────────────────────────
    def _wipe(self, empresas_data):
        self.stdout.write(self.style.WARNING('Borrando datos previos de empresas demo...'))
        nombres = [e['nombre'] for e in empresas_data]
        empresas_qs = Empresa.objects.filter(nombre__in=nombres)
        for e in empresas_qs:
            Venta.objects.filter(turno__operador__empresa=e).delete()
            Turno.objects.filter(operador__empresa=e).delete()
            Tanque.objects.filter(sucursal__empresa=e).delete()
            EstadoSurtidor.objects.filter(lado__isla__sucursal__empresa=e).delete()
            Lado.objects.filter(isla__sucursal__empresa=e).delete()
            Isla.objects.filter(sucursal__empresa=e).delete()
            Sucursal.objects.filter(empresa=e).delete()
            Vehiculo.objects.filter(cliente__empresa_clientes__empresa=e).delete()
            EmpresaCliente.objects.filter(empresa=e).delete()
            Cliente.objects.filter(empresa=e).delete()
            TipoCombustible.objects.filter(empresa=e).delete()
            Usuario.objects.filter(empresa=e).exclude(is_superuser=True).delete()
        empresas_qs.delete()
        self.stdout.write(self.style.WARNING('  ...listo'))

    # ── Creacion de entidades ────────────────────────────────────────────────
    def _crear_empresa(self, data):
        empresa, _ = Empresa.objects.get_or_create(
            nombre=data['nombre'],
            defaults={
                'nit': data['nit'],
                'telefono': data['telefono'],
                'email': data['email'],
                'direccion': data['direccion'],
                'plan': data['plan'],
                'estado': 'ACTIVA',
                'latitud': Decimal(str(data['lat'])),
                'longitud': Decimal(str(data['lng'])),
            }
        )
        return empresa

    def _crear_admin_empresa(self, empresa, data):
        email = f'admin@{data["dominio"]}.bo'
        admin, _ = Usuario.objects.get_or_create(
            email=email,
            defaults={
                'nombre': f'Admin {empresa.nombre}',
                'is_staff': True,
                'is_active': True,
                'empresa': empresa,
            }
        )
        # Siempre resetear password para que --wipe / re-runs siempre den demo123
        admin.set_password('demo123')
        admin.empresa = empresa
        admin.is_staff = True
        admin.is_active = True
        admin.save()
        admin.roles.add(self.rol_admin)
        return email

    def _crear_tipos_combustible(self, empresa):
        tipos = {}
        for t in TIPOS_COMBUSTIBLE_BASE:
            obj, _ = TipoCombustible.objects.get_or_create(
                tipo=t['tipo'], empresa=empresa,
                defaults={'precio_litro': t['precio_litro'], 'activo': True}
            )
            tipos[t['tipo']] = obj
        return tipos

    def _crear_config_puntos(self, empresa):
        ConfiguracionPuntos.objects.get_or_create(
            empresa=empresa,
            defaults={
                'activo': True,
                'puntos_por_litro': Decimal('1.00'),
                'valor_punto_bs': Decimal('0.1000'),
                'minimo_canje': 100,
            }
        )

    def _crear_sucursales(self, empresa, emp_data, empresa_idx, tipos):
        sucursales_info = []
        sucursales_data = SUCURSALES_POR_EMPRESA[empresa_idx]
        for suc_idx, s_data in enumerate(sucursales_data):
            nombre = f'{empresa.nombre.split()[0]} {s_data["sufijo"]}'
            sucursal, created = Sucursal.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'direccion': s_data['direccion'],
                    'telefono': rand_telefono(),
                    'nit': rand_nit(),
                    'cantidad_islas': 2,
                    'tiene_gnv': False,
                    'estado': 'ACTIVA',
                    'empresa': empresa,
                    'latitud': Decimal(str(emp_data['lat'] + s_data['lat_off'])),
                    'longitud': Decimal(str(emp_data['lng'] + s_data['lng_off'])),
                }
            )
            # Vincular tipos combustible a la sucursal
            sucursal.tipos_combustible.set(tipos.values())

            # Gerente
            gerente_email = f'gerente.{emp_data["dominio"]}.{suc_idx+1}@estacion.bo'
            gerente_nombre = f'Gerente {s_data["sufijo"]}'
            gerente = self._crear_usuario(
                gerente_email, gerente_nombre,
                empresa, sucursal, self.rol_gerente,
            )
            self.credenciales_por_empresa[emp_data['nombre']].append({
                'rol': 'Gerente',
                'nombre': gerente_nombre,
                'email': gerente_email,
                'password': 'demo123',
                'sucursal': nombre,
            })

            # Tanques
            for tipo_key, tipo_obj in tipos.items():
                cap = Decimal('20000') if 'DIESEL' in tipo_key else Decimal('15000')
                nivel = cap * Decimal(str(random.uniform(0.35, 0.85))).quantize(Decimal('0.01'))
                Tanque.objects.get_or_create(
                    sucursal=sucursal, tipo_combustible=tipo_obj,
                    defaults={
                        'capacidad_maxima': cap,
                        'nivel_actual': nivel,
                        'nivel_minimo_alerta': cap * Decimal('0.15'),
                        'activo': True,
                    }
                )

            # Islas + lados
            islas = []
            for numero in range(1, 3):
                isla, created_isla = Isla.objects.get_or_create(
                    sucursal=sucursal, numero=numero,
                    defaults={'estado': 'ACTIVO'}
                )
                lados = []
                for letra in ['A', 'B']:
                    lado, _ = Lado.objects.get_or_create(
                        isla=isla, lado=letra,
                        defaults={'activo': True}
                    )
                    EstadoSurtidor.objects.get_or_create(
                        lado=lado, defaults={'estado': 'ACTIVO'}
                    )
                    lados.append(lado)
                islas.append((isla, lados))

            # Operadores (3 por sucursal)
            operadores = []
            for i in range(1, 4):
                op_email = f'op{i}.{emp_data["dominio"]}.{suc_idx+1}@estacion.bo'
                op_nombre = f'Operador {i} - {s_data["sufijo"]}'
                op = self._crear_usuario(
                    op_email, op_nombre,
                    empresa, sucursal, self.rol_operador,
                )
                operadores.append(op)
                self.credenciales_por_empresa[emp_data['nombre']].append({
                    'rol': 'Operador',
                    'nombre': op_nombre,
                    'email': op_email,
                    'password': 'demo123',
                    'sucursal': nombre,
                })

            sucursales_info.append({
                'sucursal': sucursal,
                'gerente': gerente,
                'operadores': operadores,
                'islas': islas,
            })
            self.stdout.write(f'    Sucursal "{nombre}" — 2 islas, 4 lados, 3 operadores')
        return sucursales_info

    def _crear_usuario(self, email, nombre, empresa, sucursal, rol):
        usuario, _ = Usuario.objects.get_or_create(
            email=email,
            defaults={
                'nombre': nombre,
                'is_active': True,
                'empresa': empresa,
                'sucursal': sucursal,
            }
        )
        # Siempre resetear password + empresa/sucursal para que re-runs sean idempotentes
        usuario.set_password('demo123')
        usuario.empresa = empresa
        usuario.sucursal = sucursal
        usuario.is_active = True
        usuario.save()
        usuario.roles.add(rol)
        return usuario

    def _crear_clientes(self, empresa):
        clientes = []
        # 10 clientes personas + 5 clientes empresa por tenant
        personas = random.sample(NOMBRES_PERSONAS, k=10)
        empresas_cli = random.sample(EMPRESAS_CLIENTE, k=min(5, len(EMPRESAS_CLIENTE)))
        candidatos = personas + empresas_cli

        for nombre in candidatos:
            cliente, created = Cliente.objects.get_or_create(
                nombre=nombre, empresa=empresa,
                defaults={
                    'nit': rand_nit(),
                    'email': f'{nombre.split()[0].lower()}@correo.bo',
                    'telefono': rand_telefono(),
                    'limite_credito': Decimal(random.choice([0, 0, 500, 1000, 2000, 5000])),
                    'saldo_credito': Decimal(random.choice([500, 1000, 2000])),
                    'activo': True,
                }
            )
            EmpresaCliente.objects.get_or_create(empresa=empresa, cliente=cliente)

            # 1-2 vehiculos por cliente
            for _ in range(random.randint(1, 2)):
                placa = rand_placa()
                if not Vehiculo.objects.filter(placa=placa).exists():
                    Vehiculo.objects.create(
                        cliente=cliente,
                        placa=placa,
                        marca=random.choice(MARCAS_VEHICULO),
                        modelo=random.choice(MODELOS_VEHICULO),
                        color=random.choice(COLORES),
                        activo=True,
                    )
            clientes.append(cliente)
        self.stdout.write(f'    {len(clientes)} clientes con vehiculos')
        return clientes

    # ── Ventas historicas ────────────────────────────────────────────────────
    def _crear_ventas_historicas(self, empresa, sucursales_info, clientes, tipos, n_dias, vpt):
        hoy = timezone.now().date()
        horarios_config = [
            ('MANANA', time(6, 0), time(14, 0)),
            ('TARDE', time(14, 0), time(22, 0)),
            ('NOCHE', time(22, 0), time(6, 0)),
        ]
        tz = timezone.get_current_timezone()
        total_ventas = 0
        total_turnos = 0
        counter_comprobante = 0

        for dia_offset in range(n_dias, 0, -1):
            fecha = hoy - timedelta(days=dia_offset)
            for suc_info in sucursales_info:
                # Rotamos operadores por turno
                horarios = random.sample(horarios_config, k=random.choice([2, 3]))
                for h_idx, (horario_code, hora_ini, hora_fin) in enumerate(horarios):
                    operador = suc_info['operadores'][h_idx % len(suc_info['operadores'])]
                    isla, lados = random.choice(suc_info['islas'])

                    fecha_apertura = datetime.combine(fecha, hora_ini, tzinfo=tz)
                    if horario_code == 'NOCHE':
                        fecha_cierre = datetime.combine(fecha + timedelta(days=1), hora_fin, tzinfo=tz)
                    else:
                        fecha_cierre = datetime.combine(fecha, hora_fin, tzinfo=tz)

                    turno = Turno.objects.create(
                        operador=operador,
                        isla=isla,
                        horario=horario_code,
                        estado='CERRADO',
                        monto_inicial=Decimal('200'),
                        monto_final=Decimal('0'),  # se actualiza abajo
                        sucursal=suc_info['sucursal'],
                    )
                    # Sobreescribir fecha_apertura (auto_now_add)
                    Turno.objects.filter(pk=turno.pk).update(
                        fecha_apertura=fecha_apertura,
                        fecha_cierre=fecha_cierre,
                    )
                    total_turnos += 1

                    # Ventas del turno
                    n_ventas = max(5, int(random.gauss(vpt, 5)))
                    total_turno = Decimal('0')
                    for _ in range(n_ventas):
                        counter_comprobante += 1
                        lado = random.choice(lados)
                        suf_unico = uuid.uuid4().hex[:6].upper()
                        tipo = random.choice(list(tipos.values()))
                        # Distribucion realista de montos
                        monto_bs = Decimal(str(random.choice([
                            10, 20, 30, 50, 50, 80, 100, 100, 150, 200, 250, 300, 500
                        ])))
                        litros = (monto_bs / tipo.precio_litro).quantize(Decimal('0.001'))
                        metodo = random.choice(METODOS_PAGO_PONDERADOS)
                        # Cliente registrado 60% de las veces
                        cliente = random.choice(clientes) if random.random() < 0.6 else None

                        # Si metodo credito fleet pero no hay cliente o no le alcanza, cambiar
                        if metodo == 'CREDITO_FLEET':
                            if not cliente or cliente.saldo_credito < monto_bs:
                                metodo = 'EFECTIVO'

                        # Timestamp aleatorio dentro del turno
                        delta_seg = int((fecha_cierre - fecha_apertura).total_seconds())
                        offset_seg = random.randint(60, max(120, delta_seg - 60))
                        fecha_venta = fecha_apertura + timedelta(seconds=offset_seg)

                        num_comp = f'VTA-{fecha.strftime("%Y%m%d")}-{suf_unico}'

                        venta = Venta.objects.create(
                            turno=turno,
                            lado=lado,
                            tipo_combustible=tipo,
                            cliente=cliente,
                            litros=litros,
                            precio_unitario=tipo.precio_litro,
                            total=monto_bs,
                            metodo_pago=metodo,
                            estado='COMPLETADA',
                            numero_comprobante=num_comp,
                            created_by=operador,
                        )
                        Venta.objects.filter(pk=venta.pk).update(fecha_hora=fecha_venta)

                        if metodo == 'CREDITO_FLEET' and cliente:
                            cliente.saldo_credito -= monto_bs
                            cliente.save(update_fields=['saldo_credito'])

                        # Acumular puntos
                        if cliente:
                            try:
                                puntos_service.acumular_puntos(
                                    cliente, litros, empresa, venta, operador,
                                )
                            except Exception:
                                pass

                        total_turno += monto_bs
                        total_ventas += 1

                    # Actualizar monto_final del turno
                    Turno.objects.filter(pk=turno.pk).update(
                        monto_final=Decimal('200') + total_turno
                    )

                # Turno ABIERTO en el ultimo dia (para pruebas manuales)
                if dia_offset == 1:
                    operador = suc_info['operadores'][0]
                    isla_abierta, _ = suc_info['islas'][0]
                    # Verificar no exista ya un turno abierto de este operador
                    if not Turno.objects.filter(operador=operador, estado='ABIERTO').exists():
                        Turno.objects.create(
                            operador=operador,
                            isla=isla_abierta,
                            horario='MANANA',
                            estado='ABIERTO',
                            monto_inicial=Decimal('300'),
                            sucursal=suc_info['sucursal'],
                        )

        self.stdout.write(f'    {total_turnos} turnos, {total_ventas} ventas historicas')

    # ── Resumen final ────────────────────────────────────────────────────────
    def _imprimir_resumen(self, empresas_data):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 78))
        self.stdout.write(self.style.SUCCESS('  TODAS LAS CREDENCIALES (password universal: demo123)'))
        self.stdout.write(self.style.SUCCESS('=' * 78))

        for e in empresas_data:
            usuarios = self.credenciales_por_empresa.get(e['nombre'], [])
            self.stdout.write(self.style.WARNING(f'\n[{e["nombre"]}]  ({len(usuarios)} usuarios)'))
            self.stdout.write('  ' + '-' * 74)
            self.stdout.write(f'  {"ROL":<14}{"EMAIL":<38}{"SUCURSAL"}')
            self.stdout.write('  ' + '-' * 74)
            for u in usuarios:
                suc = u['sucursal'] if u['sucursal'] != '—' else ''
                self.stdout.write(f'  {u["rol"]:<14}{u["email"]:<38}{suc}')

        total_users = sum(len(u) for u in self.credenciales_por_empresa.values())
        self.stdout.write(self.style.SUCCESS(f'\nTotal usuarios generados: {total_users}'))
        self.stdout.write(self.style.SUCCESS(
            'Superadmin (del seed base): superadmin@surtidor.com / super123'
        ))

    def _exportar_credenciales(self):
        """Genera un archivo credenciales_demo.txt con toda la lista."""
        from django.conf import settings
        path = settings.BASE_DIR / 'credenciales_demo.txt'
        lines = [
            'CREDENCIALES DE DEMO — Sistema Estacion de Servicio',
            '=' * 70,
            'Password universal: demo123',
            '',
            'Superadmin del sistema:',
            '  superadmin@surtidor.com  /  super123',
            '',
        ]
        for empresa_nombre, usuarios in self.credenciales_por_empresa.items():
            lines.append('')
            lines.append(f'[{empresa_nombre}]')
            lines.append('-' * 70)
            lines.append(f'{"Rol":<15}{"Nombre":<28}{"Email":<38}{"Sucursal"}')
            lines.append('-' * 70)
            for u in usuarios:
                lines.append(
                    f'{u["rol"]:<15}{u["nombre"][:27]:<28}{u["email"]:<38}{u["sucursal"]}'
                )

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        self.stdout.write(self.style.NOTICE(
            f'\nCredenciales completas exportadas a: {path}\n'
        ))

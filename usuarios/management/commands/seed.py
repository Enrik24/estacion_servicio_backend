import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from ventas.models import (
    Isla, Lado, TipoCombustible, Sucursal, Cliente, Vehiculo,
    EmpresaCliente, Turno, Venta
)
from usuarios.models import Permiso, Rol, Usuario, Empresa
from inventario.models import Tanque, DescargaCombustible
from monitoreo.models import EstadoSurtidor
from seguridad.models import Bitacora


class Command(BaseCommand):
    help = 'Seeder principal del sistema'

    def handle(self, *args, **kwargs):
        random.seed(42)
        self.stdout.write(self.style.NOTICE('Iniciando seed...'))

        # ── Permisos ──────────────────────────────────────────────────────────
        permisos_data = [
            {'codigo': 'usuarios.ver',             'nombre': 'Ver usuarios'},
            {'codigo': 'usuarios.crear',            'nombre': 'Crear usuarios'},
            {'codigo': 'usuarios.editar',           'nombre': 'Editar usuarios'},
            {'codigo': 'usuarios.eliminar',         'nombre': 'Eliminar usuarios'},
            {'codigo': 'usuarios.asignar_roles',    'nombre': 'Asignar roles'},
            {'codigo': 'roles.ver',                 'nombre': 'Ver roles'},
            {'codigo': 'roles.crear',               'nombre': 'Crear roles'},
            {'codigo': 'roles.editar',              'nombre': 'Editar roles'},
            {'codigo': 'roles.eliminar',            'nombre': 'Eliminar roles'},
            {'codigo': 'permisos.ver',              'nombre': 'Ver permisos'},
            {'codigo': 'permisos.crear',            'nombre': 'Crear permisos'},
            {'codigo': 'permisos.editar',           'nombre': 'Editar permisos'},
            {'codigo': 'permisos.eliminar',         'nombre': 'Eliminar permisos'},
            {'codigo': 'bitacora.ver',              'nombre': 'Ver bitácora'},
            {'codigo': 'turnos.ver',                'nombre': 'Ver turnos'},
            {'codigo': 'turnos.abrir',              'nombre': 'Abrir turno'},
            {'codigo': 'turnos.cerrar',             'nombre': 'Cerrar turno'},
            {'codigo': 'ventas.ver',                'nombre': 'Ver ventas'},
            {'codigo': 'ventas.registrar',          'nombre': 'Registrar venta'},
            {'codigo': 'ventas.anular',             'nombre': 'Anular venta'},
            {'codigo': 'surtidores.ver',            'nombre': 'Ver surtidores'},
            {'codigo': 'surtidores.crear',          'nombre': 'Crear surtidores'},
            {'codigo': 'surtidores.editar',         'nombre': 'Editar surtidores'},
            {'codigo': 'surtidores.eliminar',       'nombre': 'Eliminar surtidores'},
            {'codigo': 'clientes.ver',              'nombre': 'Ver clientes'},
            {'codigo': 'clientes.crear',            'nombre': 'Crear clientes'},
            {'codigo': 'clientes.editar',           'nombre': 'Editar clientes'},
            {'codigo': 'clientes.eliminar',         'nombre': 'Eliminar clientes'},
            {'codigo': 'sucursales.ver',            'nombre': 'Ver sucursales'},
            {'codigo': 'sucursales.crear',          'nombre': 'Crear sucursales'},
            {'codigo': 'sucursales.editar',         'nombre': 'Editar sucursales'},
            {'codigo': 'sucursales.eliminar',       'nombre': 'Eliminar sucursales'},
            {'codigo': 'reportes.ver',              'nombre': 'Ver reportes'},
            {'codigo': 'backup.crear',              'nombre': 'Crear backup'},
            {'codigo': 'backup.restaurar',          'nombre': 'Restaurar backup'},
            {'codigo': 'limites_consumo.ver',       'nombre': 'Ver límites de consumo'},
            {'codigo': 'limites_consumo.crear',     'nombre': 'Crear límites de consumo'},
            {'codigo': 'limites_consumo.editar',    'nombre': 'Editar límites de consumo'},
            {'codigo': 'limites_consumo.eliminar',  'nombre': 'Eliminar límites de consumo'},
            {'codigo': 'limites_consumo.validar',   'nombre': 'Validar consumo'},
            {'codigo': 'ver.facturas',              'nombre': 'Ver Facturas'},
            {'codigo': 'bombas.ver',                'nombre': 'Ver Bombas'},
            {'codigo': 'bombas.crear',              'nombre': 'Crear Bombas'},
            {'codigo': 'bombas.editar',             'nombre': 'Editar Bombas'},
            {'codigo': 'bombas.eliminar',           'nombre': 'Eliminar Bombas'},
            {'codigo': 'combustibles.ver',          'nombre': 'Ver Combustibles'},
            {'codigo': 'combustibles.crear',        'nombre': 'Crear Combustibles'},
            {'codigo': 'combustibles.editar',       'nombre': 'Editar Combustibles'},
            {'codigo': 'combustibles.eliminar',     'nombre': 'Eliminar Combustibles'},
        ]

        permisos_creados = {}
        for p in permisos_data:
            obj, created = Permiso.objects.get_or_create(
                codigo=p['codigo'],
                defaults={'nombre': p['nombre'], 'descripcion': p['nombre']}
            )
            permisos_creados[p['codigo']] = obj
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Permiso creado: {p["codigo"]}'))

        # ── Roles ─────────────────────────────────────────────────────────────
        todos = list(permisos_creados.values())

        permisos_gerente = [permisos_creados.get(c) for c in [
            'usuarios.ver', 'usuarios.crear', 'usuarios.editar', 'usuarios.asignar_roles',
            'roles.ver', 'permisos.ver', 'bitacora.ver',
            'turnos.ver', 'turnos.abrir', 'turnos.cerrar',
            'ventas.ver', 'ventas.registrar', 'ventas.anular',
            'surtidores.ver', 'surtidores.crear', 'surtidores.editar',
            'clientes.ver', 'clientes.crear', 'clientes.editar',
            'sucursales.ver', 'sucursales.editar', 'reportes.ver',
            'limites_consumo.ver', 'limites_consumo.crear', 'limites_consumo.editar',
        ]]
        permisos_operador = [permisos_creados.get(c) for c in [
            'turnos.ver', 'turnos.abrir', 'turnos.cerrar',
            'ventas.ver', 'ventas.registrar', 'ventas.anular',
            'surtidores.ver', 'clientes.ver', 'clientes.crear',
        ]]
        permisos_auditor = [permisos_creados.get(c) for c in [
            'bitacora.ver', 'ventas.ver', 'usuarios.ver',
            'turnos.ver', 'clientes.ver', 'sucursales.ver',
            'surtidores.ver', 'reportes.ver',
        ]]
        permisos_cliente_rol = [permisos_creados.get(c) for c in [
            'ventas.ver', 'clientes.ver',
        ]]

        roles_data = [
            {'nombre': 'Administrador', 'descripcion': 'Acceso total al sistema',    'permisos': todos},
            {'nombre': 'Gerente',       'descripcion': 'Gestión de sucursal',         'permisos': permisos_gerente},
            {'nombre': 'Operador',      'descripcion': 'Registro de ventas y turnos', 'permisos': permisos_operador},
            {'nombre': 'Auditor',       'descripcion': 'Solo lectura',                'permisos': permisos_auditor},
            {'nombre': 'Cliente',       'descripcion': 'Cliente de la estación',      'permisos': permisos_cliente_rol},
        ]

        roles_creados = {}
        for r in roles_data:
            rol, created = Rol.objects.get_or_create(
                nombre=r['nombre'],
                defaults={'descripcion': r['descripcion']}
            )
            rol.permisos.set([p for p in r['permisos'] if p])
            roles_creados[r['nombre']] = rol
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Rol creado: {r["nombre"]}'))

        # ── Super Admin del sistema ───────────────────────────────────────────
        superadmin, created = Usuario.objects.get_or_create(
            email='superadmin@surtidor.com',
            defaults={'nombre': 'Super Admin', 'is_superuser': True, 'is_staff': True, 'is_active': True}
        )
        if created:
            superadmin.set_password('super123')
            superadmin.save()
            self.stdout.write(self.style.SUCCESS('  Super Admin creado'))

        # ── Enrique (super usuario personal) ─────────────────────────────────
        enrique, created = Usuario.objects.get_or_create(
            email='enriquemamani2403@gmail.com',
            defaults={
                'nombre': 'Administrador Enrique',
                'is_superuser': True,
                'is_staff': True,
                'is_active': True,
            }
        )
        if created:
            enrique.set_password('enrique123')
            enrique.save()
            self.stdout.write(self.style.SUCCESS('  Usuario Enrique creado'))

        # ── Empresa ───────────────────────────────────────────────────────────
        empresa, created = Empresa.objects.get_or_create(
            nombre='Surtidor Octano',
            defaults={
                'nit': '1000000001',
                'telefono': '3-4567890',
                'email': 'contacto@surtidoroctano.com',
                'direccion': 'Santa Cruz de la Sierra',
                'plan': 'PROFESIONAL',
                'estado': 'ACTIVA',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  Empresa creada: Surtidor Octano'))

        # Asociar Enrique a la empresa si no tiene una
        if not enrique.empresa:
            enrique.empresa = empresa
            enrique.save()
        enrique.roles.set([roles_creados['Administrador']])

        # ── Tipos de combustible ──────────────────────────────────────────────
        tipos_data = [
            {'tipo': 'GASOLINA_ESPECIAL', 'precio_litro': 6.96},
            {'tipo': 'GASOLINA_PREMIUM',  'precio_litro': 11.00},
            {'tipo': 'DIESEL',            'precio_litro': 9.80},
            {'tipo': 'GNV',               'precio_litro': 2.73},
        ]

        tipos_creados = {}
        for t in tipos_data:
            obj, created = TipoCombustible.objects.get_or_create(
                tipo=t['tipo'],
                empresa=empresa,
                defaults={'precio_litro': t['precio_litro'], 'activo': True}
            )
            tipos_creados[t['tipo']] = obj
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Combustible creado: {obj.get_tipo_display()}'))

        # ── Sucursales ────────────────────────────────────────────────────────
        sucursales_data = [
            {
                'nombre': 'Surtidor Octano - Norte',
                'direccion': 'Av. Banzer 5to Anillo, Santa Cruz',
                'telefono': '3-1234567',
                'nit': '1000000002',
                'cantidad_islas': 2,
                'tiene_gnv': False,
                'estado': 'ACTIVA',
            },
            {
                'nombre': 'Surtidor Octano - Oeste',
                'direccion': 'Av. Radial 13 6to Anillo, Santa Cruz',
                'telefono': '3-7654321',
                'nit': '1000000003',
                'cantidad_islas': 2,
                'tiene_gnv': False,
                'estado': 'ACTIVA',
            },
        ]

        sucursales_creadas = {}
        for s in sucursales_data:
            suc, created = Sucursal.objects.get_or_create(
                nombre=s['nombre'],
                defaults={
                    'direccion': s['direccion'],
                    'telefono': s['telefono'],
                    'nit': s['nit'],
                    'cantidad_islas': s['cantidad_islas'],
                    'tiene_gnv': s['tiene_gnv'],
                    'estado': s['estado'],
                    'empresa': empresa,
                }
            )
            if not created and not suc.empresa:
                suc.empresa = empresa
                suc.save()
            sucursales_creadas[s['nombre']] = suc
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Sucursal creada: {suc.nombre}'))
                for i in range(1, s['cantidad_islas'] + 1):
                    isla = Isla.objects.create(numero=i, sucursal=suc, estado='ACTIVO')
                    Lado.objects.get_or_create(isla=isla, lado='A', defaults={'activo': True})
                    Lado.objects.get_or_create(isla=isla, lado='B', defaults={'activo': True})
                    self.stdout.write(self.style.SUCCESS(f'    Isla {i} creada con lados A y B'))

        suc_norte = sucursales_creadas.get('Surtidor Octano - Norte')
        suc_oeste = sucursales_creadas.get('Surtidor Octano - Oeste')

        # ── Usuarios ──────────────────────────────────────────────────────────
        usuarios_data = [
            {
                'nombre': 'Administrador',
                'email': 'admin@estacion.com',
                'password': 'admin123',
                'is_superuser': False,
                'is_staff': True,
                'rol': 'Administrador',
                'sucursal': None,
            },
            {
                'nombre': 'Gerente Norte',
                'email': 'gerente.norte@estacion.com',
                'password': 'gerente123',
                'is_superuser': False,
                'is_staff': True,
                'rol': 'Gerente',
                'sucursal': suc_norte,
            },
            {
                'nombre': 'Gerente Oeste',
                'email': 'gerente.oeste@estacion.com',
                'password': 'gerente123',
                'is_superuser': False,
                'is_staff': True,
                'rol': 'Gerente',
                'sucursal': suc_oeste,
            },
            {
                'nombre': 'Operador Norte',
                'email': 'operador@estacion.com',
                'password': 'operador123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Operador',
                'sucursal': suc_norte,
            },
            {
                'nombre': 'Operador Oeste',
                'email': 'operador2@estacion.com',
                'password': 'operador123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Operador',
                'sucursal': suc_oeste,
            },
            {
                'nombre': 'Auditor Demo',
                'email': 'auditor@estacion.com',
                'password': 'auditor123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Auditor',
                'sucursal': None,
            },
        ]

        usuarios_creados = {}
        for u in usuarios_data:
            obj, created = Usuario.objects.get_or_create(
                email=u['email'],
                defaults={
                    'nombre': u['nombre'],
                    'is_superuser': u['is_superuser'],
                    'is_staff': u['is_staff'],
                    'is_active': True,
                    'empresa': empresa,
                    'sucursal': u['sucursal'],
                }
            )
            if created:
                obj.set_password(u['password'])
                obj.save()
                self.stdout.write(self.style.SUCCESS(f'  Usuario creado: {obj.nombre}'))
            rol = roles_creados.get(u['rol'])
            if rol:
                obj.roles.set([rol])
            usuarios_creados[u['email']] = obj

        # ── Clientes y Vehículos ──────────────────────────────────────────────
        nombres_clientes = [
            'Carlos Mamani', 'Ana Flores', 'Luis Quispe', 'Maria Condori',
            'Jorge Vargas', 'Rosa Huanca', 'Pedro Gutierrez', 'Elena Soria',
            'Miguel Apaza', 'Carmen Choque', 'Roberto Limachi', 'Patricia Mamani',
            'Fernando Ticona', 'Lucia Callisaya', 'Oscar Zenteno', 'Silvia Quispe',
            'Raul Mamani', 'Gloria Poma', 'Ivan Condori', 'Teresa Flores',
            'Hugo Tarqui', 'Beatriz Laime', 'Nelson Cusi', 'Yolanda Marca',
            'Alvaro Pinto',
        ]
        placas = [
            '1234-ABC', '5678-DEF', '9012-GHI', '3456-JKL', '7890-MNO',
            '2345-PQR', '6789-STU', '0123-VWX', '4567-YZA', '8901-BCD',
            '1357-EFG', '2468-HIJ', '3579-KLM', '4680-NOP', '5791-QRS',
            '6802-TUV', '7913-WXY', '8024-ZAB', '9135-CDE', '0246-FGH',
            '1122-IJK', '3344-LMN', '5566-OPQ', '7788-RST', '9900-UVW',
        ]
        marcas_modelos = [
            ('Toyota', 'Corolla'), ('Toyota', 'Hilux'), ('Toyota', 'RAV4'),
            ('Chevrolet', 'Sail'), ('Chevrolet', 'Spark'), ('Nissan', 'Frontier'),
            ('Hyundai', 'Tucson'), ('Kia', 'Sportage'), ('Suzuki', 'Swift'),
            ('Ford', 'Ranger'), ('Honda', 'Civic'), ('Mitsubishi', 'L200'),
        ]
        colores = ['Blanco', 'Negro', 'Gris', 'Rojo', 'Azul', 'Plata', 'Verde']
        # NITs deterministas para idempotencia
        nits = [str(1000000 + i) for i in range(len(nombres_clientes))]

        self.stdout.write(self.style.NOTICE('  Creando clientes y vehículos...'))
        clientes_creados = []

        for i, nombre in enumerate(nombres_clientes):
            cli, created = Cliente.objects.get_or_create(
                nit=nits[i],
                defaults={
                    'nombre': nombre,
                    'telefono': f'7{1000000 + i}',
                    'limite_credito': random.choice([0, 500, 1000, 2000]),
                    'saldo_credito': random.choice([0, 200, 500, 1000]),
                    'activo': True,
                    'empresa': empresa,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Cliente creado: {nombre}'))

            marca, modelo = marcas_modelos[i % len(marcas_modelos)]
            Vehiculo.objects.get_or_create(
                placa=placas[i],
                defaults={
                    'cliente': cli,
                    'marca': marca,
                    'modelo': modelo,
                    'color': colores[i % len(colores)],
                    'activo': True,
                }
            )
            EmpresaCliente.objects.get_or_create(empresa=empresa, cliente=cli)
            clientes_creados.append(cli)

        # ── Tanques (inventario) ──────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE('  Creando tanques...'))
        tanques_config = [
            # (sucursal, tipo, capacidad_max, nivel_actual, nivel_minimo_alerta)
            (suc_norte, 'GASOLINA_ESPECIAL', 20000, 14500, 2000),
            (suc_norte, 'GASOLINA_PREMIUM',  10000,  6800, 1000),
            (suc_norte, 'DIESEL',            15000, 11200, 1500),
            (suc_oeste, 'GASOLINA_ESPECIAL', 20000, 12000, 2000),
            (suc_oeste, 'GASOLINA_PREMIUM',  10000,  4500, 1000),
            (suc_oeste, 'DIESEL',            15000,  9800, 1500),
        ]
        tanques_creados = []
        for suc, tipo_key, cap_max, nivel, nivel_min in tanques_config:
            tipo_obj = tipos_creados.get(tipo_key)
            if not tipo_obj or not suc:
                continue
            tanque, created = Tanque.objects.get_or_create(
                sucursal=suc,
                tipo_combustible=tipo_obj,
                defaults={
                    'capacidad_maxima': cap_max,
                    'nivel_actual': nivel,
                    'nivel_minimo_alerta': nivel_min,
                    'activo': True,
                }
            )
            tanques_creados.append(tanque)
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f'  Tanque creado: {suc.nombre} - {tipo_obj.get_tipo_display()}'
                ))

        # ── Descargas de combustible (inventario) ─────────────────────────────
        self.stdout.write(self.style.NOTICE('  Creando descargas de combustible...'))
        operador_norte = usuarios_creados.get('operador@estacion.com')
        for tanque in tanques_creados:
            # 2 descargas por tanque en los últimos 15 días
            for dias_atras in [14, 7]:
                fecha_descarga = timezone.now() - timedelta(days=dias_atras)
                volumen = random.choice([3000, 4000, 5000])
                nivel_antes = float(tanque.nivel_actual) - volumen
                nivel_antes = max(nivel_antes, 0)
                nivel_despues = nivel_antes + volumen
                # Usamos get_or_create con campos únicos aproximados no disponibles,
                # así que filtramos manualmente para evitar duplicados
                existe = DescargaCombustible.objects.filter(
                    tanque=tanque,
                    volumen_descargado=volumen,
                    nivel_antes=nivel_antes,
                ).exists()
                if not existe and operador_norte:
                    DescargaCombustible.objects.create(
                        tanque=tanque,
                        volumen_descargado=volumen,
                        nivel_antes=nivel_antes,
                        nivel_despues=nivel_despues,
                        registrado_por=operador_norte,
                        observaciones='Descarga de demostración',
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'  Descarga creada: {tanque} - {volumen} Lt'
                    ))

        # ── Estado de surtidores (monitoreo) ──────────────────────────────────
        self.stdout.write(self.style.NOTICE('  Creando estados de surtidores...'))
        lados_todos = list(Lado.objects.all())
        for lado in lados_todos:
            EstadoSurtidor.objects.get_or_create(
                lado=lado,
                defaults={
                    'estado': 'ACTIVO',
                    'reportado_por': None,
                }
            )
        self.stdout.write(self.style.SUCCESS(f'  Estados de surtidores: {len(lados_todos)} lados procesados'))

        # ── Bitácora (seguridad) ───────────────────────────────────────────────
        self.stdout.write(self.style.NOTICE('  Creando entradas de bitácora...'))
        bitacora_entries = [
            (superadmin,    'LOGIN',    'EXITO',  'Usuarios',  'Inicio de sesión del super admin'),
            (enrique,       'LOGIN',    'EXITO',  'Usuarios',  'Inicio de sesión de Enrique'),
            (usuarios_creados.get('admin@estacion.com'),          'LOGIN',    'EXITO',  'Usuarios',  'Inicio de sesión del administrador'),
            (usuarios_creados.get('gerente.norte@estacion.com'),  'CONSULTAR','EXITO',  'Ventas',    'Consulta de ventas del día'),
            (usuarios_creados.get('operador@estacion.com'),       'CREAR',    'EXITO',  'Ventas',    'Registro de venta de combustible'),
            (usuarios_creados.get('operador2@estacion.com'),      'CREAR',    'EXITO',  'Turnos',    'Apertura de turno'),
            (usuarios_creados.get('auditor@estacion.com'),        'CONSULTAR','EXITO',  'Bitácora',  'Consulta de bitácora del sistema'),
            (None,                                                 'LOGIN',    'ERROR',  'Usuarios',  'Intento de login fallido con email desconocido'),
        ]
        for usuario_bit, accion, estado, modulo, descripcion in bitacora_entries:
            existe = Bitacora.objects.filter(
                usuario=usuario_bit,
                accion=accion,
                modulo_afectado=modulo,
                descripcion=descripcion,
            ).exists()
            if not existe:
                Bitacora.objects.create(
                    usuario=usuario_bit,
                    empresa=empresa,
                    usuario_email=getattr(usuario_bit, 'email', None),
                    usuario_nombre=getattr(usuario_bit, 'nombre', None),
                    usuario_rol=getattr(usuario_bit, 'nombre_rol', 'Sin rol') if usuario_bit else 'Sin rol',
                    accion=accion,
                    estado=estado,
                    modulo_afectado=modulo,
                    descripcion=descripcion,
                )
        self.stdout.write(self.style.SUCCESS('  Entradas de bitácora creadas'))

        # ── Turnos y Ventas (últimos 30 días) ─────────────────────────────────
        self.stdout.write(self.style.NOTICE('  Creando turnos y ventas...'))

        islas = list(Isla.objects.all())
        tipos = list(TipoCombustible.objects.filter(activo=True, empresa=empresa))
        metodos_pago = ['EFECTIVO', 'TARJETA', 'QR', 'CREDITO_FLEET']
        horarios = ['MANANA', 'TARDE', 'NOCHE']

        if not islas or not tipos:
            self.stdout.write(self.style.WARNING('  Turnos omitidos: no hay islas o tipos de combustible'))
        else:
            turnos_creados_count = 0
            ventas_creadas_count = 0

            for dias_atras in range(30, 0, -1):
                fecha = timezone.now() - timedelta(days=dias_atras)

                for _ in range(random.randint(1, 2)):
                    isla = random.choice(islas)
                    lados = list(Lado.objects.filter(isla=isla, activo=True))
                    if not lados:
                        continue

                    # Operador según sucursal de la isla
                    if isla.sucursal == suc_norte:
                        operador = usuarios_creados.get('operador@estacion.com')
                    else:
                        operador = usuarios_creados.get('operador2@estacion.com')
                    if not operador:
                        continue

                    horario = random.choice(horarios)
                    fecha_apertura = fecha.replace(
                        hour=random.randint(6, 20),
                        minute=0, second=0, microsecond=0
                    )
                    fecha_cierre = fecha_apertura + timedelta(hours=8)

                    # Evitar duplicados: un turno por isla+horario+día
                    turno = Turno.objects.filter(
                        isla=isla,
                        horario=horario,
                        fecha_apertura__year=fecha_apertura.year,
                        fecha_apertura__month=fecha_apertura.month,
                        fecha_apertura__day=fecha_apertura.day,
                    ).first()

                    if not turno:
                        turno = Turno.objects.create(
                            operador=operador,
                            isla=isla,
                            horario=horario,
                            estado='CERRADO',
                            monto_inicial=random.randint(100, 500),
                            monto_final=random.randint(500, 3000),
                            observaciones='Turno de demostración',
                        )
                        Turno.objects.filter(pk=turno.pk).update(
                            fecha_apertura=fecha_apertura,
                            fecha_cierre=fecha_cierre,
                            created_at=fecha_apertura,
                        )
                        turnos_creados_count += 1

                    for j in range(random.randint(3, 8)):
                        tipo = random.choice(tipos)
                        lado = random.choice(lados)
                        metodo = random.choice(metodos_pago)
                        monto = random.choice([50, 100, 150, 200, 250, 300])
                        litros = round(monto / float(tipo.precio_litro), 3)
                        cliente = random.choice(clientes_creados + [None, None])

                        if metodo == 'CREDITO_FLEET' and (
                            not cliente or cliente.saldo_credito < monto
                        ):
                            metodo = 'EFECTIVO'

                        comprobante = f"VTA-{turno.id}-{j + 1}"
                        venta, created = Venta.objects.get_or_create(
                            numero_comprobante=comprobante,
                            defaults={
                                'turno': turno,
                                'lado': lado,
                                'tipo_combustible': tipo,
                                'cliente': cliente,
                                'litros': litros,
                                'precio_unitario': tipo.precio_litro,
                                'total': monto,
                                'metodo_pago': metodo,
                                'estado': 'COMPLETADA',
                                'created_by': operador,
                            }
                        )
                        if created:
                            fecha_venta = fecha_apertura + timedelta(minutes=random.randint(10, 400))
                            Venta.objects.filter(pk=venta.pk).update(fecha_hora=fecha_venta)
                            ventas_creadas_count += 1

            self.stdout.write(self.style.SUCCESS(
                f'  Turnos creados: {turnos_creados_count} | Ventas creadas: {ventas_creadas_count}'
            ))

        # ── Resumen ───────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS('\n✅ Seed completado exitosamente!'))
        self.stdout.write(self.style.NOTICE(f'  Clientes/Vehículos: {len(clientes_creados)}'))
        self.stdout.write(self.style.NOTICE('\nCredenciales:'))
        self.stdout.write('  Super Admin:     superadmin@surtidor.com        / super123')
        self.stdout.write('  Enrique:         enriquemamani2403@gmail.com    / enrique123')
        self.stdout.write('  Admin:           admin@estacion.com              / admin123')
        self.stdout.write('  Gerente Norte:   gerente.norte@estacion.com      / gerente123')
        self.stdout.write('  Gerente Oeste:   gerente.oeste@estacion.com      / gerente123')
        self.stdout.write('  Operador Norte:  operador@estacion.com           / operador123')
        self.stdout.write('  Operador Oeste:  operador2@estacion.com          / operador123')
        self.stdout.write('  Auditor:         auditor@estacion.com            / auditor123')

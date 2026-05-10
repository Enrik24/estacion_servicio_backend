from django.core.management.base import BaseCommand
from django.utils import timezone
from usuarios.models import Permiso, Rol, Usuario
from ventas.models import Isla, Lado, TipoCombustible, Sucursal, Cliente, Turno, Venta


class Command(BaseCommand):
    help = 'Seeder para permisos, roles y usuarios iniciales de la gasolinera'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE('Iniciando seed...'))

        # ── Permisos ──────────────────────────────────────────────────────────
        permisos_data = [
            # Usuarios
            {'codigo': 'usuarios.ver',          'nombre': 'Ver usuarios',      'descripcion': 'Ver lista de usuarios'},
            {'codigo': 'usuarios.crear',         'nombre': 'Crear usuarios',    'descripcion': 'Crear nuevos usuarios'},
            {'codigo': 'usuarios.editar',        'nombre': 'Editar usuarios',   'descripcion': 'Editar usuarios existentes'},
            {'codigo': 'usuarios.eliminar',      'nombre': 'Eliminar usuarios', 'descripcion': 'Eliminar usuarios'},
            {'codigo': 'usuarios.asignar_roles', 'nombre': 'Asignar roles',     'descripcion': 'Asignar roles a usuarios'},

            # Roles
            {'codigo': 'roles.ver',      'nombre': 'Ver roles',      'descripcion': 'Ver lista de roles'},
            {'codigo': 'roles.crear',    'nombre': 'Crear roles',    'descripcion': 'Crear nuevos roles'},
            {'codigo': 'roles.editar',   'nombre': 'Editar roles',   'descripcion': 'Editar roles existentes'},
            {'codigo': 'roles.eliminar', 'nombre': 'Eliminar roles', 'descripcion': 'Eliminar roles'},

            # Permisos
            {'codigo': 'permisos.ver',      'nombre': 'Ver permisos',      'descripcion': 'Ver lista de permisos'},
            {'codigo': 'permisos.crear',    'nombre': 'Crear permisos',    'descripcion': 'Crear nuevos permisos'},
            {'codigo': 'permisos.editar',   'nombre': 'Editar permisos',   'descripcion': 'Editar permisos existentes'},
            {'codigo': 'permisos.eliminar', 'nombre': 'Eliminar permisos', 'descripcion': 'Eliminar permisos'},

            # Bitacora
            {'codigo': 'bitacora.ver', 'nombre': 'Ver bitácora', 'descripcion': 'Ver registro de auditoría'},

            # Turnos
            {'codigo': 'turnos.ver',    'nombre': 'Ver turnos',    'descripcion': 'Ver lista de turnos'},
            {'codigo': 'turnos.abrir',  'nombre': 'Abrir turno',   'descripcion': 'Abrir un nuevo turno'},
            {'codigo': 'turnos.cerrar', 'nombre': 'Cerrar turno',  'descripcion': 'Cerrar un turno abierto'},

            # Ventas
            {'codigo': 'ventas.ver',       'nombre': 'Ver ventas',       'descripcion': 'Ver registro de ventas'},
            {'codigo': 'ventas.registrar', 'nombre': 'Registrar venta',  'descripcion': 'Registrar nuevas ventas'},
            {'codigo': 'ventas.anular',    'nombre': 'Anular venta',     'descripcion': 'Anular ventas registradas'},

            # Surtidores
            {'codigo': 'surtidores.ver',      'nombre': 'Ver surtidores',      'descripcion': 'Ver lista de surtidores'},
            {'codigo': 'surtidores.crear',    'nombre': 'Crear surtidores',    'descripcion': 'Crear nuevos surtidores'},
            {'codigo': 'surtidores.editar',   'nombre': 'Editar surtidores',   'descripcion': 'Editar surtidores existentes'},
            {'codigo': 'surtidores.eliminar', 'nombre': 'Eliminar surtidores', 'descripcion': 'Eliminar surtidores'},

            # Clientes
            {'codigo': 'clientes.ver',      'nombre': 'Ver clientes',      'descripcion': 'Ver lista de clientes'},
            {'codigo': 'clientes.crear',    'nombre': 'Crear clientes',    'descripcion': 'Crear nuevos clientes'},
            {'codigo': 'clientes.editar',   'nombre': 'Editar clientes',   'descripcion': 'Editar clientes existentes'},
            {'codigo': 'clientes.eliminar', 'nombre': 'Eliminar clientes', 'descripcion': 'Eliminar clientes'},

            # Sucursales
            {'codigo': 'sucursales.ver',      'nombre': 'Ver sucursales',      'descripcion': 'Ver lista de sucursales'},
            {'codigo': 'sucursales.crear',    'nombre': 'Crear sucursales',    'descripcion': 'Crear nuevas sucursales'},
            {'codigo': 'sucursales.editar',   'nombre': 'Editar sucursales',   'descripcion': 'Editar sucursales existentes'},
            {'codigo': 'sucursales.eliminar', 'nombre': 'Eliminar sucursales', 'descripcion': 'Eliminar sucursales'},

            # Reportes
            {'codigo': 'reportes.ver', 'nombre': 'Ver reportes', 'descripcion': 'Acceder a los reportes del sistema'},
        ]

        permisos_creados = {}
        for permiso_data in permisos_data:
            permiso, created = Permiso.objects.get_or_create(
                codigo=permiso_data['codigo'],
                defaults={
                    'nombre': permiso_data['nombre'],
                    'descripcion': permiso_data['descripcion']
                }
            )
            permisos_creados[permiso_data['codigo']] = permiso
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Permiso creado: {permiso.codigo}'))
            else:
                self.stdout.write(f'  Permiso ya existe: {permiso.codigo}')

        # ── Roles ─────────────────────────────────────────────────────────────
        todos_los_permisos = list(permisos_creados.values())

        permisos_gerente = [
            permisos_creados.get('usuarios.ver'),
            permisos_creados.get('usuarios.crear'),
            permisos_creados.get('usuarios.editar'),
            permisos_creados.get('usuarios.asignar_roles'),
            permisos_creados.get('roles.ver'),
            permisos_creados.get('permisos.ver'),
            permisos_creados.get('bitacora.ver'),
            permisos_creados.get('turnos.ver'),
            permisos_creados.get('turnos.abrir'),
            permisos_creados.get('turnos.cerrar'),
            permisos_creados.get('ventas.ver'),
            permisos_creados.get('ventas.registrar'),
            permisos_creados.get('ventas.anular'),
            permisos_creados.get('surtidores.ver'),
            permisos_creados.get('surtidores.crear'),
            permisos_creados.get('surtidores.editar'),
            permisos_creados.get('clientes.ver'),
            permisos_creados.get('clientes.crear'),
            permisos_creados.get('clientes.editar'),
            permisos_creados.get('sucursales.ver'),
            permisos_creados.get('sucursales.crear'),
            permisos_creados.get('sucursales.editar'),
            permisos_creados.get('reportes.ver'),
        ]

        permisos_operador = [
            permisos_creados.get('turnos.ver'),
            permisos_creados.get('turnos.abrir'),
            permisos_creados.get('turnos.cerrar'),
            permisos_creados.get('ventas.ver'),
            permisos_creados.get('ventas.registrar'),
            permisos_creados.get('ventas.anular'),
            permisos_creados.get('surtidores.ver'),
            permisos_creados.get('clientes.ver'),
        ]

        permisos_auditor = [
            permisos_creados.get('bitacora.ver'),
            permisos_creados.get('ventas.ver'),
            permisos_creados.get('usuarios.ver'),
            permisos_creados.get('turnos.ver'),
            permisos_creados.get('clientes.ver'),
            permisos_creados.get('sucursales.ver'),
            permisos_creados.get('surtidores.ver'),
            permisos_creados.get('reportes.ver'),
        ]

        permisos_cliente = [
            permisos_creados.get('ventas.ver'),
            permisos_creados.get('clientes.ver'),
        ]

        roles_data = [
            {
                'nombre': 'Administrador',
                'descripcion': 'Acceso total al sistema',
                'permisos': todos_los_permisos
            },
            {
                'nombre': 'Gerente/Dueño',
                'descripcion': 'Acceso a reportes, configuración y gestión general',
                'permisos': permisos_gerente
            },
            {
                'nombre': 'Operador',
                'descripcion': 'Registro de ventas y turnos',
                'permisos': permisos_operador
            },
            {
                'nombre': 'Auditor',
                'descripcion': 'Solo lectura de registros del sistema',
                'permisos': permisos_auditor
            },
            {
                'nombre': 'Cliente',
                'descripcion': 'Cliente de la estación de servicio',
                'permisos': permisos_cliente
            },
        ]

        roles_creados = {}
        for rol_data in roles_data:
            rol, created = Rol.objects.get_or_create(
                nombre=rol_data['nombre'],
                defaults={'descripcion': rol_data['descripcion']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Rol creado: {rol.nombre}'))
            else:
                self.stdout.write(f'  Rol ya existe: {rol.nombre}')

            permisos_validos = [p for p in rol_data['permisos'] if p is not None]
            rol.permisos.set(permisos_validos)
            roles_creados[rol_data['nombre']] = rol

        # ── Usuarios ──────────────────────────────────────────────────────────
        # 2 por cada rol (Administrador ya tiene admin@estacion.com, se agrega Enrique)
        usuarios_data = [
            # Administrador (2 usuarios)
            {
                'nombre': 'Administrador',
                'email': 'admin@estacion.com',
                'password': 'admin123',
                'is_superuser': True,
                'is_staff': True,
                'rol': 'Administrador'
            },
            {
                'nombre': 'Enrique',
                'email': 'enriquemamani2403@gmail.com',
                'password': 'enrique123',
                'is_superuser': True,
                'is_staff': True,
                'rol': 'Administrador'
            },

            # Gerente/Dueño (2 usuarios)
            {
                'nombre': 'Gerente Demo',
                'email': 'gerente@estacion.com',
                'password': 'gerente123',
                'is_superuser': False,
                'is_staff': True,
                'rol': 'Gerente/Dueño'
            },
            {
                'nombre': 'Dueño Demo',
                'email': 'dueno@estacion.com',
                'password': 'dueno123',
                'is_superuser': False,
                'is_staff': True,
                'rol': 'Gerente/Dueño'
            },

            # Operador (2 usuarios)
            {
                'nombre': 'Operador Demo',
                'email': 'operador@estacion.com',
                'password': 'operador123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Operador'
            },
            {
                'nombre': 'Operador 2',
                'email': 'operador2@estacion.com',
                'password': 'operador123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Operador'
            },

            # Auditor (2 usuarios)
            {
                'nombre': 'Auditor Demo',
                'email': 'auditor@estacion.com',
                'password': 'auditor123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Auditor'
            },
            {
                'nombre': 'Auditor 2',
                'email': 'auditor2@estacion.com',
                'password': 'auditor123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Auditor'
            },

            # Cliente (2 usuarios)
            {
                'nombre': 'Cliente Demo',
                'email': 'cliente@estacion.com',
                'password': 'cliente123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Cliente'
            },
            {
                'nombre': 'Cliente 2',
                'email': 'cliente2@estacion.com',
                'password': 'cliente123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Cliente'
            },
        ]

        for usuario_data in usuarios_data:
            email = usuario_data['email']
            rol_nombre = usuario_data['rol']
            password = usuario_data['password']

            usuario, created = Usuario.objects.get_or_create(
                email=email,
                defaults={
                    'nombre': usuario_data['nombre'],
                    'is_superuser': usuario_data['is_superuser'],
                    'is_staff': usuario_data['is_staff'],
                    'is_active': True
                }
            )

            if created:
                usuario.set_password(password)
                usuario.save()
                self.stdout.write(self.style.SUCCESS(f'  Usuario creado: {usuario.nombre} ({email})'))
            else:
                self.stdout.write(f'  Usuario ya existe: {usuario.nombre} ({email})')

            rol = roles_creados.get(rol_nombre)
            if rol:
                usuario.roles.set([rol])

        # ── Sucursales ────────────────────────────────────────────────────────
        sucursales_data = [
            {
                'nombre': 'Estación Central',
                'direccion': 'Av. Blanco Galindo Km 5, Cochabamba',
                'telefono': '74512345',
                'nit': '1234567890',
                'cantidad_islas': 2,
                'tiene_gnv': True,
                'estado': 'ACTIVA',
            },
            {
                'nombre': 'Estación Norte',
                'direccion': 'Av. Panamericana Km 2, Cochabamba',
                'telefono': '74598765',
                'nit': '9876543210',
                'cantidad_islas': 2,
                'tiene_gnv': False,
                'estado': 'ACTIVA',
            },
        ]

        sucursales_creadas = {}
        for suc_data in sucursales_data:
            suc, created = Sucursal.objects.get_or_create(
                nombre=suc_data['nombre'],
                defaults=suc_data
            )
            sucursales_creadas[suc_data['nombre']] = suc
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Sucursal creada: {suc.nombre}'))
            else:
                self.stdout.write(f'  Sucursal ya existe: {suc.nombre}')

        sucursal_principal = sucursales_creadas.get('Estación Central')

        # ── Islas y Lados ─────────────────────────────────────────────────────
        islas_data = [
            {'numero': 1, 'descripcion': 'Isla 1'},
            {'numero': 2, 'descripcion': 'Isla 2'},
        ]

        for isla_data in islas_data:
            isla, created = Isla.objects.get_or_create(
                numero=isla_data['numero'],
                defaults={
                    'descripcion': isla_data['descripcion'],
                    'estado': 'ACTIVO',
                    'sucursal': sucursal_principal,
                }
            )
            # Si la isla ya existía sin sucursal, asignarla
            if not created and isla.sucursal is None and sucursal_principal:
                isla.sucursal = sucursal_principal
                isla.save()
                self.stdout.write(self.style.SUCCESS(f'  Isla {isla.numero}: sucursal asignada'))
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Isla creada: Isla {isla.numero}'))
            else:
                self.stdout.write(f'  Isla ya existe: Isla {isla.numero}')

            for lado in ['A', 'B']:
                l, created = Lado.objects.get_or_create(
                    isla=isla,
                    lado=lado,
                    defaults={'activo': True}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'    Lado creado: Isla {isla.numero} - Lado {lado}'))
                else:
                    self.stdout.write(f'    Lado ya existe: Isla {isla.numero} - Lado {lado}')

        # ── Tipos de combustible ──────────────────────────────────────────────
        tipos_data = [
            {'tipo': 'GASOLINA_ESPECIAL', 'precio_litro': 6.96},
            {'tipo': 'GASOLINA_PREMIUM',  'precio_litro': 11.00},
            {'tipo': 'DIESEL',            'precio_litro': 9.80},
            {'tipo': 'GNV',               'precio_litro': 2.73},
        ]

        for tipo_data in tipos_data:
            tipo, created = TipoCombustible.objects.get_or_create(
                tipo=tipo_data['tipo'],
                defaults={'precio_litro': tipo_data['precio_litro'], 'activo': True}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Combustible creado: {tipo.get_tipo_display()}'))
            else:
                self.stdout.write(f'  Combustible ya existe: {tipo.get_tipo_display()}')

        # ── Clientes ──────────────────────────────────────────────────────────
        clientes_data = [
            {
                'nombre': 'Juan Pérez',
                'nit': '12345678',
                'email': 'juan.perez@gmail.com',
                'telefono': '71234567',
                'limite_credito': 500.00,
                'saldo_credito': 0.00,
                'activo': True,
            },
            {
                'nombre': 'María López',
                'nit': '87654321',
                'email': 'maria.lopez@gmail.com',
                'telefono': '76543210',
                'limite_credito': 1000.00,
                'saldo_credito': 0.00,
                'activo': True,
            },
            {
                'nombre': 'Transportes Andes S.R.L.',
                'nit': '55566677',
                'email': 'contacto@transandes.com',
                'telefono': '44556677',
                'limite_credito': 5000.00,
                'saldo_credito': 0.00,
                'activo': True,
            },
        ]

        clientes_creados = []
        for cli_data in clientes_data:
            cli, created = Cliente.objects.get_or_create(
                nit=cli_data['nit'],
                defaults=cli_data
            )
            clientes_creados.append(cli)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Cliente creado: {cli.nombre}'))
            else:
                self.stdout.write(f'  Cliente ya existe: {cli.nombre}')

        # ── Turnos ────────────────────────────────────────────────────────────
        operador = Usuario.objects.filter(email='operador@estacion.com').first()
        operador2 = Usuario.objects.filter(email='operador2@estacion.com').first()
        isla1 = Isla.objects.filter(numero=1).first()
        isla2 = Isla.objects.filter(numero=2).first()

        turnos_data = [
            {
                'operador': operador,
                'isla': isla1,
                'horario': 'MANANA',
                'estado': 'CERRADO',
                'monto_inicial': 200.00,
                'monto_final': 1850.50,
                'observaciones': 'Turno de prueba mañana',
            },
            {
                'operador': operador2,
                'isla': isla2,
                'horario': 'TARDE',
                'estado': 'ABIERTO',
                'monto_inicial': 150.00,
                'monto_final': None,
                'observaciones': 'Turno de prueba tarde',
            },
        ]

        turnos_creados = []
        for turno_data in turnos_data:
            if not turno_data['operador'] or not turno_data['isla']:
                self.stdout.write(self.style.WARNING('  Turno omitido: operador o isla no encontrados'))
                continue
            # Evitar duplicados simples por operador+isla+horario+estado
            turno = Turno.objects.filter(
                operador=turno_data['operador'],
                isla=turno_data['isla'],
                horario=turno_data['horario'],
            ).first()
            if not turno:
                turno = Turno.objects.create(
                    operador=turno_data['operador'],
                    isla=turno_data['isla'],
                    horario=turno_data['horario'],
                    estado=turno_data['estado'],
                    monto_inicial=turno_data['monto_inicial'],
                    monto_final=turno_data['monto_final'],
                    observaciones=turno_data['observaciones'],
                )
                self.stdout.write(self.style.SUCCESS(
                    f'  Turno creado: {turno.operador.nombre} - Isla {turno.isla.numero} - {turno.horario}'
                ))
            else:
                self.stdout.write(f'  Turno ya existe: {turno.operador.nombre} - Isla {turno.isla.numero}')
            turnos_creados.append(turno)

        # ── Ventas ────────────────────────────────────────────────────────────
        if turnos_creados:
            lado_1a = Lado.objects.filter(isla__numero=1, lado='A').first()
            lado_1b = Lado.objects.filter(isla__numero=1, lado='B').first()
            lado_2a = Lado.objects.filter(isla__numero=2, lado='A').first()
            lado_2b = Lado.objects.filter(isla__numero=2, lado='B').first()

            t_especial = TipoCombustible.objects.filter(tipo='GASOLINA_ESPECIAL').first()
            t_premium  = TipoCombustible.objects.filter(tipo='GASOLINA_PREMIUM').first()
            t_diesel   = TipoCombustible.objects.filter(tipo='DIESEL').first()
            t_gnv      = TipoCombustible.objects.filter(tipo='GNV').first()

            turno1 = turnos_creados[0]
            turno2 = turnos_creados[1] if len(turnos_creados) > 1 else turnos_creados[0]

            cli1 = clientes_creados[0] if clientes_creados else None
            cli2 = clientes_creados[1] if len(clientes_creados) > 1 else None
            cli3 = clientes_creados[2] if len(clientes_creados) > 2 else None

            ventas_data = [
                # comprobante, turno, lado, tipo, cliente, litros, precio, metodo, estado
                ('VTA-0001', turno1, lado_1a, t_especial, cli1,  20.000,  6.96, 'EFECTIVO',      'COMPLETADA'),
                ('VTA-0002', turno1, lado_1b, t_premium,  None,  15.500, 11.00, 'QR',            'COMPLETADA'),
                ('VTA-0003', turno1, lado_1a, t_diesel,   cli2,  30.000,  9.80, 'TARJETA',       'COMPLETADA'),
                ('VTA-0004', turno1, lado_1b, t_gnv,      None,  10.000,  2.73, 'EFECTIVO',      'COMPLETADA'),
                ('VTA-0005', turno1, lado_1a, t_especial, cli3,  25.000,  6.96, 'CREDITO_FLEET', 'COMPLETADA'),
                ('VTA-0006', turno2, lado_2a, t_premium,  cli1,  18.000, 11.00, 'EFECTIVO',      'COMPLETADA'),
                ('VTA-0007', turno2, lado_2b, t_diesel,   None,  40.000,  9.80, 'QR',            'COMPLETADA'),
                ('VTA-0008', turno2, lado_2a, t_especial, cli2,  12.000,  6.96, 'TARJETA',       'ANULADA'),
                ('VTA-0009', turno2, lado_2b, t_gnv,      cli3,   8.000,  2.73, 'EFECTIVO',      'COMPLETADA'),
                ('VTA-0010', turno2, lado_2a, t_premium,  None,  22.500, 11.00, 'QR',            'COMPLETADA'),
            ]

            admin_user = Usuario.objects.filter(email='admin@estacion.com').first()

            for comprobante, turno, lado, tipo_comb, cliente, litros, precio, metodo, estado in ventas_data:
                if not all([turno, lado, tipo_comb]):
                    self.stdout.write(self.style.WARNING(f'  Venta {comprobante} omitida: faltan datos'))
                    continue
                if Venta.objects.filter(numero_comprobante=comprobante).exists():
                    self.stdout.write(f'  Venta ya existe: {comprobante}')
                    continue
                total = round(litros * precio, 2)
                Venta.objects.create(
                    numero_comprobante=comprobante,
                    turno=turno,
                    lado=lado,
                    tipo_combustible=tipo_comb,
                    cliente=cliente,
                    litros=litros,
                    precio_unitario=precio,
                    total=total,
                    metodo_pago=metodo,
                    estado=estado,
                    created_by=admin_user,
                )
                self.stdout.write(self.style.SUCCESS(f'  Venta creada: {comprobante} - Bs. {total}'))
        else:
            self.stdout.write(self.style.WARNING('  Ventas omitidas: no hay turnos disponibles'))

        # ── Resumen ───────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS('\nSeed completado exitosamente!'))
        self.stdout.write(self.style.NOTICE('Credenciales:'))
        self.stdout.write('  Admin:          admin@estacion.com        / admin123')
        self.stdout.write('  Enrique:        enriquemamani2403@gmail.com / enrique123')
        self.stdout.write('  Gerente:        gerente@estacion.com       / gerente123')
        self.stdout.write('  Dueño:          dueno@estacion.com         / dueno123')
        self.stdout.write('  Operador:       operador@estacion.com      / operador123')
        self.stdout.write('  Operador 2:     operador2@estacion.com     / operador123')
        self.stdout.write('  Auditor:        auditor@estacion.com       / auditor123')
        self.stdout.write('  Auditor 2:      auditor2@estacion.com      / auditor123')
        self.stdout.write('  Cliente:        cliente@estacion.com       / cliente123')
        self.stdout.write('  Cliente 2:      cliente2@estacion.com      / cliente123')

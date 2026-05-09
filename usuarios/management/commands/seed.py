from django.core.management.base import BaseCommand
from usuarios.models import Permiso, Rol, Usuario
from ventas.models import Isla, Lado, TipoCombustible, Cliente


class Command(BaseCommand):
    help = 'Seeder para permisos, roles y usuarios iniciales de la gasolinera'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE('Iniciando seed...'))

        permisos_data = [
            # Usuarios
            {'codigo': 'usuarios.ver', 'nombre': 'Ver usuarios', 'descripcion': 'Ver lista de usuarios'},
            {'codigo': 'usuarios.crear', 'nombre': 'Crear usuarios', 'descripcion': 'Crear nuevos usuarios'},
            {'codigo': 'usuarios.editar', 'nombre': 'Editar usuarios', 'descripcion': 'Editar usuarios existentes'},
            {'codigo': 'usuarios.eliminar', 'nombre': 'Eliminar usuarios', 'descripcion': 'Eliminar usuarios'},
            {'codigo': 'usuarios.asignar_roles', 'nombre': 'Asignar roles', 'descripcion': 'Asignar roles a usuarios'},

            # Roles
            {'codigo': 'roles.ver', 'nombre': 'Ver roles', 'descripcion': 'Ver lista de roles'},
            {'codigo': 'roles.crear', 'nombre': 'Crear roles', 'descripcion': 'Crear nuevos roles'},
            {'codigo': 'roles.editar', 'nombre': 'Editar roles', 'descripcion': 'Editar roles existentes'},
            {'codigo': 'roles.eliminar', 'nombre': 'Eliminar roles', 'descripcion': 'Eliminar roles'},

            # Permisos
            {'codigo': 'permisos.ver', 'nombre': 'Ver permisos', 'descripcion': 'Ver lista de permisos'},
            {'codigo': 'permisos.crear', 'nombre': 'Crear permisos', 'descripcion': 'Crear nuevos permisos'},
            {'codigo': 'permisos.editar', 'nombre': 'Editar permisos', 'descripcion': 'Editar permisos existentes'},
            {'codigo': 'permisos.eliminar', 'nombre': 'Eliminar permisos', 'descripcion': 'Eliminar permisos'},

            # Bitacora
            {'codigo': 'bitacora.ver', 'nombre': 'Ver bitácora', 'descripcion': 'Ver registro de auditoría'},

            # Turnos
            {'codigo': 'turnos.ver', 'nombre': 'Ver turnos', 'descripcion': 'Ver lista de turnos'},
            {'codigo': 'turnos.abrir', 'nombre': 'Abrir turno', 'descripcion': 'Abrir un nuevo turno'},
            {'codigo': 'turnos.cerrar', 'nombre': 'Cerrar turno', 'descripcion': 'Cerrar un turno abierto'},

            # Ventas
            {'codigo': 'ventas.ver', 'nombre': 'Ver ventas', 'descripcion': 'Ver registro de ventas'},
            {'codigo': 'ventas.registrar', 'nombre': 'Registrar venta', 'descripcion': 'Registrar nuevas ventas'},
            {'codigo': 'ventas.anular', 'nombre': 'Anular venta', 'descripcion': 'Anular ventas registradas'},

            # Surtidores
            {'codigo': 'surtidores.ver', 'nombre': 'Ver surtidores', 'descripcion': 'Ver lista de surtidores'},
            {'codigo': 'surtidores.crear', 'nombre': 'Crear surtidores', 'descripcion': 'Crear nuevos surtidores'},
            {'codigo': 'surtidores.editar', 'nombre': 'Editar surtidores', 'descripcion': 'Editar surtidores existentes'},
            {'codigo': 'surtidores.eliminar', 'nombre': 'Eliminar surtidores', 'descripcion': 'Eliminar surtidores'},

            # Clientes
            {'codigo': 'clientes.ver', 'nombre': 'Ver clientes', 'descripcion': 'Ver lista de clientes'},
            {'codigo': 'clientes.crear', 'nombre': 'Crear clientes', 'descripcion': 'Crear nuevos clientes'},
            {'codigo': 'clientes.editar', 'nombre': 'Editar clientes', 'descripcion': 'Editar clientes existentes'},
            {'codigo': 'clientes.eliminar', 'nombre': 'Eliminar clientes', 'descripcion': 'Eliminar clientes'},
            {'codigo': 'limites_consumo.ver', 'nombre': 'Ver límites de consumo', 'descripcion': 'Ver límites de consumo por cliente'},
            {'codigo': 'limites_consumo.crear', 'nombre': 'Crear límites de consumo', 'descripcion': 'Crear límites de consumo por cliente'},
            {'codigo': 'limites_consumo.editar', 'nombre': 'Editar límites de consumo', 'descripcion': 'Editar límites de consumo por cliente'},
            {'codigo': 'limites_consumo.eliminar', 'nombre': 'Eliminar límites de consumo', 'descripcion': 'Eliminar límites de consumo por cliente'},
            {'codigo': 'limites_consumo.validar', 'nombre': 'Validar consumo contra límites', 'descripcion': 'Validar consumos contra los límites activos'},

            # Sucursales
            {'codigo': 'sucursales.ver', 'nombre': 'Ver sucursales', 'descripcion': 'Ver lista de sucursales'},
            {'codigo': 'sucursales.crear', 'nombre': 'Crear sucursales', 'descripcion': 'Crear nuevas sucursales'},
            {'codigo': 'sucursales.editar', 'nombre': 'Editar sucursales', 'descripcion': 'Editar sucursales existentes'},
            {'codigo': 'sucursales.eliminar', 'nombre': 'Eliminar sucursales', 'descripcion': 'Eliminar sucursales'},
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

        # Roles
        todos_los_permisos = list(permisos_creados.values())

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

        permisos_gerente = [
            permisos_creados.get('usuarios.ver'),
            permisos_creados.get('roles.ver'),
            permisos_creados.get('permisos.ver'),
            permisos_creados.get('bitacora.ver'),
            permisos_creados.get('turnos.ver'),
            permisos_creados.get('ventas.ver'),
            permisos_creados.get('surtidores.ver'),
            permisos_creados.get('clientes.ver'),
            permisos_creados.get('sucursales.ver'),
        ]

        permisos_auditor = [
            permisos_creados.get('bitacora.ver'),
            permisos_creados.get('ventas.ver'),
            permisos_creados.get('usuarios.ver'),
            permisos_creados.get('turnos.ver'),
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
                'nombre': 'Gerente',
                'descripcion': 'Acceso a reportes y configuración',
                'permisos': permisos_gerente
            },
            {
                'nombre': 'Operador',
                'descripcion': 'Registro de ventas y turnos',
                'permisos': permisos_operador
            },
            {
                'nombre': 'Auditor',
                'descripcion': 'Solo lectura y bitácora',
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

        # Usuarios base
        usuarios_data = [
            {
                'nombre': 'Administrador',
                'email': 'admin@estacion.com',
                'password': 'admin123',
                'is_superuser': True,
                'is_staff': True,
                'rol': 'Administrador'
            },
            {
                'nombre': 'Operador Demo',
                'email': 'operador@estacion.com',
                'password': 'operador123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Operador'
            },
        ]

        for usuario_data in usuarios_data:
            email = usuario_data['email']
            rol_nombre = usuario_data.pop('rol')
            password = usuario_data.pop('password')

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

        self.stdout.write(self.style.SUCCESS('\nSeed completado exitosamente!'))
        self.stdout.write(self.style.NOTICE('Credenciales:'))
        self.stdout.write('  Admin:    admin@estacion.com / admin123')
        self.stdout.write('  Operador: operador@estacion.com / operador123')

        islas_data = [
            {'numero': 1, 'descripcion': 'Isla 1'},
            {'numero': 2, 'descripcion': 'Isla 2'},
         ]

        for isla_data in islas_data:
            isla, created = Isla.objects.get_or_create(
                numero=isla_data['numero'],
                defaults={'descripcion': isla_data['descripcion'], 'estado': 'ACTIVO'}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Isla creada: Isla {isla.numero}'))
            else:
                self.stdout.write(f'  Isla ya existe: Isla {isla.numero}')

            # Crear lados A y B para cada isla
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

        # Crear tipos de combustible
        tipos_data = [
            {'tipo': 'GASOLINA_ESPECIAL', 'precio_litro': 6.96},
            {'tipo': 'GASOLINA_PREMIUM', 'precio_litro': 11.00},
            {'tipo': 'DIESEL', 'precio_litro': 9.80},
            {'tipo': 'GNV', 'precio_litro': 2.73},
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

        # Clientes base para módulo de ventas (separados de usuarios/CU11)
        clientes_data = [
            {'nombre': 'Transporte Andino SRL', 'nit': '900001', 'telefono': '70000001', 'limite_credito': 5000, 'saldo_credito': 5000},
            {'nombre': 'Logistica del Sur', 'nit': '900002', 'telefono': '70000002', 'limite_credito': 3000, 'saldo_credito': 3000},
        ]

        for cliente_data in clientes_data:
            cliente, created = Cliente.objects.get_or_create(
                nit=cliente_data['nit'],
                defaults={
                    'nombre': cliente_data['nombre'],
                    'telefono': cliente_data['telefono'],
                    'limite_credito': cliente_data['limite_credito'],
                    'saldo_credito': cliente_data['saldo_credito'],
                    'activo': True,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Cliente ventas creado: {cliente.nombre} ({cliente.nit})'))
            else:
                # Si existe, solo reactivamos para que siempre aparezca en el combo
                if not cliente.activo:
                    cliente.activo = True
                    cliente.save(update_fields=['activo'])
                self.stdout.write(f'  Cliente ventas ya existe: {cliente.nombre} ({cliente.nit})')

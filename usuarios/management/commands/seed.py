from django.core.management.base import BaseCommand
from usuarios.models import Permiso, Rol, Usuario, Empresa
from ventas.models import Isla, Lado, TipoCombustible, Sucursal, Cliente, Vehiculo, EmpresaCliente


class Command(BaseCommand):
    help = 'Seeder principal del sistema'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE('Iniciando seed...'))

        # ── Permisos ──────────────────────────────────────────────────────────
        permisos_data = [
            # Permisos de usuarios
            {'codigo': 'usuarios.ver', 'nombre': 'Ver Usuarios', 'descripcion': 'Permiso para ver usuarios'},
            {'codigo': 'usuarios.crear', 'nombre': 'Crear Usuarios', 'descripcion': 'Permiso para crear usuarios'},
            {'codigo': 'usuarios.editar', 'nombre': 'Editar Usuarios', 'descripcion': 'Permiso para editar usuarios'},
            {'codigo': 'usuarios.eliminar', 'nombre': 'Eliminar Usuarios', 'descripcion': 'Permiso para eliminar usuarios'},
            
            # Permisos de roles
            {'codigo': 'roles.ver', 'nombre': 'Ver Roles', 'descripcion': 'Permiso para ver roles'},
            {'codigo': 'roles.crear', 'nombre': 'Crear Roles', 'descripcion': 'Permiso para crear roles'},
            {'codigo': 'roles.editar', 'nombre': 'Editar Roles', 'descripcion': 'Permiso para editar roles'},
            {'codigo': 'roles.eliminar', 'nombre': 'Eliminar Roles', 'descripcion': 'Permiso para eliminar roles'},
            
            # Permisos de permisos
            {'codigo': 'permisos.ver', 'nombre': 'Ver Permisos', 'descripcion': 'Permiso para ver permisos'},
            {'codigo': 'permisos.crear', 'nombre': 'Crear Permisos', 'descripcion': 'Permiso para crear permisos'},
            {'codigo': 'permisos.editar', 'nombre': 'Editar Permisos', 'descripcion': 'Permiso para editar permisos'},
            {'codigo': 'permisos.eliminar', 'nombre': 'Eliminar Permisos', 'descripcion': 'Permiso para eliminar permisos'},
            
            # Permisos de facturas
            {'codigo': 'ver.facturas', 'nombre': 'Ver Facturas', 'descripcion': 'Permiso para poder ver sus facturas'},
            
            # Permisos de bombas (gasolinera)
            {'codigo': 'bombas.ver', 'nombre': 'Ver Bombas', 'descripcion': 'Permiso para ver bombas de combustible'},
            {'codigo': 'bombas.crear', 'nombre': 'Crear Bombas', 'descripcion': 'Permiso para crear bombas de combustible'},
            {'codigo': 'bombas.editar', 'nombre': 'Editar Bombas', 'descripcion': 'Permiso para editar bombas de combustible'},
            {'codigo': 'bombas.eliminar', 'nombre': 'Eliminar Bombas', 'descripcion': 'Permiso para eliminar bombas de combustible'},
            
            # Permisos de combustibles
            {'codigo': 'combustibles.ver', 'nombre': 'Ver Combustibles', 'descripcion': 'Permiso para ver tipos de combustible'},
            {'codigo': 'combustibles.crear', 'nombre': 'Crear Combustibles', 'descripcion': 'Permiso para crear tipos de combustible'},
            {'codigo': 'combustibles.editar', 'nombre': 'Editar Combustibles', 'descripcion': 'Permiso para editar tipos de combustible'},
            {'codigo': 'combustibles.eliminar', 'nombre': 'Eliminar Combustibles', 'descripcion': 'Permiso para eliminar tipos de combustible'},
            
            # Permisos de ventas
            {'codigo': 'ventas.ver', 'nombre': 'Ver Ventas', 'descripcion': 'Permiso para ver ventas'},
            {'codigo': 'ventas.crear', 'nombre': 'Crear Ventas', 'descripcion': 'Permiso para crear ventas'},
            {'codigo': 'ventas.editar', 'nombre': 'Editar Ventas', 'descripcion': 'Permiso para editar ventas'},
            {'codigo': 'ventas.eliminar', 'nombre': 'Eliminar Ventas', 'descripcion': 'Permiso para eliminar ventas'},
            
            # Permisos de reportes
            {'codigo': 'reportes.ver', 'nombre': 'Ver Reportes', 'descripcion': 'Permiso para ver reportes de la gasolinera'},
            
            # Permisos de bitácora
            {'codigo': 'bitacora.ver', 'nombre': 'Ver Bitácora', 'descripcion': 'Permiso para ver la bitácora del sistema'},
            
            # Permiso de admin (NUEVO - middleware de seguridad)
            {'codigo': 'admin.acceso', 'nombre': 'Acceso al Panel Admin', 'descripcion': 'Permiso para acceder al panel de administración de Django'},
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

        permisos_cliente = [permisos_creados.get(c) for c in [
            'ventas.ver', 'clientes.ver',
        ]]

        roles_data = [
            {'nombre': 'Administrador', 'descripcion': 'Acceso total al sistema', 'permisos': todos},
            {'nombre': 'Gerente', 'descripcion': 'Gestión de sucursal', 'permisos': permisos_gerente},
            {'nombre': 'Operador', 'descripcion': 'Registro de ventas y turnos', 'permisos': permisos_operador},
            {'nombre': 'Auditor', 'descripcion': 'Solo lectura', 'permisos': permisos_auditor},
            {'nombre': 'Cliente', 'descripcion': 'Cliente de la estación', 'permisos': permisos_cliente},
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

        # ── Tipos de combustible ──────────────────────────────────────────────
        tipos_data = [
            {'tipo': 'GASOLINA_ESPECIAL', 'precio_litro': 6.96},
            {'tipo': 'GASOLINA_PREMIUM',  'precio_litro': 11.00},
            {'tipo': 'DIESEL',            'precio_litro': 9.80},
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
                'nombre': 'Cliente',
                'descripcion': 'Rol para clientes de la gasolinera',
                'permisos': [
                    permisos_creados.get('ver.facturas'),
                    permisos_creados.get('ventas.ver'),
                ]
            },
            {
                'nombre': 'Empleado',
                'descripcion': 'Rol para empleados de la gasolinera',
                'permisos': [
                    permisos_creados.get('bombas.ver'),
                    permisos_creados.get('combustibles.ver'),
                    permisos_creados.get('ventas.ver'),
                    permisos_creados.get('ventas.crear'),
                    permisos_creados.get('ventas.editar'),
                    permisos_creados.get('ver.facturas'),
                    # ⚠️ Empleado NO tiene acceso a admin ni bitácora
                ]
            },
        ]

        sucursales_creadas = {}
        for s in sucursales_data:
            suc, created = Sucursal.objects.get_or_create(
                nombre=s['nombre'],
                defaults={**s, 'empresa': empresa}
            )
            if not created and not suc.empresa:
                suc.empresa = empresa
                suc.save()
            sucursales_creadas[s['nombre']] = suc
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Sucursal creada: {suc.nombre}'))
                # Crear islas y lados
                for i in range(1, s['cantidad_islas'] + 1):
                    isla = Isla.objects.create(numero=i, sucursal=suc, estado='ACTIVO')
                    Lado.objects.create(isla=isla, lado='A', activo=True)
                    Lado.objects.create(isla=isla, lado='B', activo=True)
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
                'empresa': empresa,
                'sucursal': None,
            },
            {
                'nombre': 'Gerente Norte',
                'email': 'gerente.norte@estacion.com',
                'password': 'gerente123',
                'is_superuser': False,
                'is_staff': True,
                'rol': 'Gerente',
                'empresa': empresa,
                'sucursal': suc_norte,
            },
            {
                'nombre': 'Gerente Oeste',
                'email': 'gerente.oeste@estacion.com',
                'password': 'gerente123',
                'is_superuser': False,
                'is_staff': True,
                'rol': 'Gerente',
                'empresa': empresa,
                'sucursal': suc_oeste,
            },
            {
                'nombre': 'Operador Norte',
                'email': 'operador.norte@estacion.com',
                'password': 'operador123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Operador',
                'empresa': empresa,
                'sucursal': suc_norte,
            },
            {
                'nombre': 'Operador Oeste',
                'email': 'operador.oeste@estacion.com',
                'password': 'operador123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Operador',
                'empresa': empresa,
                'sucursal': suc_oeste,
            },
            {
                'nombre': 'Auditor Demo',
                'email': 'auditor@estacion.com',
                'password': 'auditor123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Auditor',
                'empresa': empresa,
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
                    'empresa': u['empresa'],
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
        clientes_data = [
            {
                'nombre': 'Juan Pérez',
                'nit': '12345678',
                'telefono': '71234567',
                'placa': '1234-ABC',
                'marca': 'Toyota',
                'modelo': 'Corolla',
                'color': 'Blanco',
            },
            {
                'nombre': 'María López',
                'nit': '87654321',
                'telefono': '76543210',
                'placa': '5678-XYZ',
                'marca': 'Nissan',
                'modelo': 'Sentra',
                'color': 'Rojo',
            },
            {
                'nombre': 'Transportes Andes SRL',
                'nit': '55566677',
                'telefono': '44556677',
                'placa': '9999-TRP',
                'marca': 'Mercedes',
                'modelo': 'Sprinter',
                'color': 'Blanco',
            },
        ]

        for c in clientes_data:
            cliente, created = Cliente.objects.get_or_create(
                nit=c['nit'],
                defaults={
                    'nombre': c['nombre'],
                    'telefono': c['telefono'],
                    'activo': True,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Cliente creado: {cliente.nombre}'))
                Vehiculo.objects.get_or_create(
                    placa=c['placa'],
                    defaults={
                        'cliente': cliente,
                        'marca': c['marca'],
                        'modelo': c['modelo'],
                        'color': c['color'],
                        'activo': True,
                    }
                )
                self.stdout.write(self.style.SUCCESS(f'    Vehículo creado: {c["placa"]}'))
            # Asociar cliente a la empresa
            EmpresaCliente.objects.get_or_create(empresa=empresa, cliente=cliente)

        # ── Resumen ───────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS('\n✅ Seed completado exitosamente!'))
        self.stdout.write(self.style.NOTICE('\nCredenciales:'))
        self.stdout.write('  Super Admin:     superadmin@surtidor.com     / super123')
        self.stdout.write('  Admin:           admin@estacion.com           / admin123')
        self.stdout.write('  Gerente Norte:   gerente.norte@estacion.com   / gerente123')
        self.stdout.write('  Gerente Oeste:   gerente.oeste@estacion.com   / gerente123')
        self.stdout.write('  Operador Norte:  operador.norte@estacion.com  / operador123')
        self.stdout.write('  Operador Oeste:  operador.oeste@estacion.com  / operador123')
        self.stdout.write('  Auditor:         auditor@estacion.com         / auditor123')
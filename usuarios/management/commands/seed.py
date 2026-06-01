import random
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from usuarios.models import Permiso, Rol, Usuario
from ventas.models import Isla, Lado, TipoCombustible, Sucursal, Cliente, Vehiculo, Turno, Venta


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
            
          
            # Permisos de reportes
            {'codigo': 'reportes.ver', 'nombre': 'Ver Reportes', 'descripcion': 'Permiso para ver reportes de la gasolinera'},

            # Permisos de límites de consumo
            {'codigo': 'limites_consumo.ver', 'nombre': 'Ver Límites de Consumo', 'descripcion': 'Permiso para ver límites de consumo'},
            {'codigo': 'limites_consumo.crear', 'nombre': 'Crear Límites de Consumo', 'descripcion': 'Permiso para crear límites de consumo'},
            {'codigo': 'limites_consumo.editar', 'nombre': 'Editar Límites de Consumo', 'descripcion': 'Permiso para editar límites de consumo'},
            {'codigo': 'limites_consumo.eliminar', 'nombre': 'Eliminar Límites de Consumo', 'descripcion': 'Permiso para eliminar límites de consumo'},
            {'codigo': 'limites_consumo.validar', 'nombre': 'Validar Consumo', 'descripcion': 'Permiso para validar consumos contra límites'},
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
            if sucursal_principal:
                isla_qs = Isla.objects.filter(numero=isla_data['numero'], sucursal=sucursal_principal).order_by('id')
            else:
                isla_qs = Isla.objects.filter(numero=isla_data['numero']).order_by('id')

            isla = isla_qs.first()
            created = isla is None

            if created:
                isla = Isla.objects.create(
                    numero=isla_data['numero'],
                    descripcion=isla_data['descripcion'],
                    estado='ACTIVO',
                    sucursal=sucursal_principal,
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
            tipo_qs = TipoCombustible.objects.filter(tipo=tipo_data['tipo']).order_by('id')
            tipo = tipo_qs.first()
            created = tipo is None

            if created:
                tipo = TipoCombustible.objects.create(
                    tipo=tipo_data['tipo'],
                    precio_litro=tipo_data['precio_litro'],
                    activo=True,
                )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Combustible creado: {tipo.get_tipo_display()}'))
            else:
                self.stdout.write(f'  Combustible ya existe: {tipo.get_tipo_display()}')

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

        self.stdout.write(self.style.NOTICE('  Creando clientes y vehículos...'))
        clientes_creados = []

        for i, nombre in enumerate(nombres_clientes):
            cli, created = Cliente.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'nit': f'{random.randint(1000000, 9999999)}',
                    'telefono': f'7{random.randint(1000000, 9999999)}',
                    'limite_credito': random.choice([0, 500, 1000, 2000]),
                    'saldo_credito': random.choice([0, 200, 500, 1000]),
                    'activo': True,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Cliente creado: {nombre}'))
            else:
                self.stdout.write(f'  Cliente ya existe: {nombre}')

            marca, modelo = random.choice(marcas_modelos)
            v, v_created = Vehiculo.objects.get_or_create(
                placa=placas[i],
                defaults={
                    'cliente': cli,
                    'marca': marca,
                    'modelo': modelo,
                    'color': random.choice(colores),
                    'activo': True,
                }
            )
            if v_created:
                self.stdout.write(self.style.SUCCESS(f'    Vehículo creado: {placas[i]}'))
            else:
                self.stdout.write(f'    Vehículo ya existe: {placas[i]}')

            clientes_creados.append(cli)

        # ── Turnos y Ventas (últimos 30 días) ─────────────────────────────────
        self.stdout.write(self.style.NOTICE('  Creando turnos y ventas...'))

        operador = Usuario.objects.filter(email='operador@estacion.com').first()
        islas = list(Isla.objects.all())
        tipos = list(TipoCombustible.objects.filter(activo=True))
        metodos_pago = ['EFECTIVO', 'TARJETA', 'QR', 'CREDITO_FLEET']
        horarios = ['MANANA', 'TARDE', 'NOCHE']

        if not operador:
            self.stdout.write(self.style.WARNING('  Turnos omitidos: operador no encontrado'))
        elif not islas or not tipos:
            self.stdout.write(self.style.WARNING('  Turnos omitidos: no hay islas o tipos de combustible'))
        else:
            turnos_creados = 0
            ventas_creadas = 0

            for dias_atras in range(30, 0, -1):
                fecha = timezone.now() - timedelta(days=dias_atras)

                # 1 o 2 turnos por día
                for _ in range(random.randint(1, 2)):
                    isla = random.choice(islas)
                    lados = list(Lado.objects.filter(isla=isla, activo=True))
                    if not lados:
                        continue

                    horario = random.choice(horarios)
                    fecha_apertura = fecha.replace(
                        hour=random.randint(6, 20),
                        minute=0, second=0, microsecond=0
                    )
                    fecha_cierre = fecha_apertura + timedelta(hours=8)

                    # Verificar si ya existe un turno para esta isla, horario y fecha aproximada
                    turno = Turno.objects.filter(
                        isla=isla,
                        horario=horario,
                        fecha_apertura__date=fecha_apertura.date()
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

                        # Ajustar fechas manualmente hacia atrás
                        Turno.objects.filter(pk=turno.pk).update(
                            fecha_apertura=fecha_apertura,
                            fecha_cierre=fecha_cierre,
                            created_at=fecha_apertura,
                        )
                        turnos_creados += 1
                    else:
                        self.stdout.write(f'    Turno ya existe: Isla {isla.numero} - {horario} - {fecha_apertura.date()}')

                    # 3 a 8 ventas por turno
                    num_ventas = random.randint(3, 8)
                    for j in range(num_ventas):
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

                        # Comprobante determinista para evitar duplicados en re-ejecuciones
                        comprobante = f"VTA-{turno.id}-{j+1}"

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
                            # Ajustar fecha de venta hacia atrás solo si se acaba de crear
                            fecha_venta = fecha_apertura + timedelta(
                                minutes=random.randint(10, 400)
                            )
                            Venta.objects.filter(pk=venta.pk).update(
                                fecha_hora=fecha_venta
                            )
                            ventas_creadas += 1

            self.stdout.write(self.style.SUCCESS(
                f'  Turnos creados: {turnos_creados} | Ventas creadas: {ventas_creadas}'
            ))

        # ── Resumen ───────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(f'\nSeed completado exitosamente!'))
        self.stdout.write(self.style.NOTICE(f'  Clientes/Vehículos: {len(clientes_creados)}'))
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

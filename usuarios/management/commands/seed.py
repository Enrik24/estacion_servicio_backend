from django.core.management.base import BaseCommand
from usuarios.models import Permiso, Rol, Usuario


class Command(BaseCommand):
    help = 'Seeder para permisos, roles y usuarios iniciales de la gasolinera'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE('Iniciando seed...'))
        
        # Crear permisos
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
                self.stdout.write(self.style.SUCCESS(f'Permiso creado: {permiso.nombre}'))
            else:
                self.stdout.write(f'Permiso ya existe: {permiso.nombre}')
        
        # Crear roles
        roles_data = [
            {
                'nombre': 'Administrador',
                'descripcion': 'Rol con acceso total al sistema',
                'permisos': list(permisos_creados.values())  # Todos los permisos
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
        
        roles_creados = {}
        for rol_data in roles_data:
            rol, created = Rol.objects.get_or_create(
                nombre=rol_data['nombre'],
                defaults={'descripcion': rol_data['descripcion']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Rol creado: {rol.nombre}'))
            else:
                self.stdout.write(f'Rol ya existe: {rol.nombre}')
            
            # Asignar permisos al rol
            if rol_data['permisos']:
                permisos_validos = [p for p in rol_data['permisos'] if p is not None]
                rol.permisos.set(permisos_validos)
                self.stdout.write(f'  -> Permisos asignados: {len(permisos_validos)}')
            
            roles_creados[rol_data['nombre']] = rol
        
        # Crear usuarios
        usuarios_data = [
            {
                'nombre': 'admin',
                'email': 'admin@gmail.com',
                'password': 'admin123',
                'is_superuser': True,
                'is_staff': True,
                'rol': 'Administrador'
            },
            {
                'nombre': 'Juan Cliente',
                'email': 'juan.cliente@gmail.com',
                'password': 'cliente123',
                'is_superuser': False,
                'is_staff': False,
                'rol': 'Cliente'
            },
            {
                'nombre': 'Maria Empleada',
                'email': 'maria.empleada@gmail.com',
                'password': 'empleado123',
                'is_superuser': False,
                'is_staff': True,
                'rol': 'Empleado'
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
                self.stdout.write(self.style.SUCCESS(f'Usuario creado: {usuario.nombre} ({email})'))
            else:
                self.stdout.write(f'Usuario ya existe: {usuario.nombre} ({email})')
            
            # Asignar rol
            rol = roles_creados.get(rol_nombre)
            if rol:
                usuario.roles.set([rol])
                self.stdout.write(f'  -> Rol asignado: {rol_nombre}')
        
        self.stdout.write(self.style.SUCCESS('\nSeed completado exitosamente!'))

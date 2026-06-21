import random
import uuid
from datetime import timedelta, datetime, time
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from ventas.models import Sucursal, Isla, Lado, TipoCombustible, Cliente, Turno, Venta
from usuarios.models import Usuario, Empresa
from ventas.models import EmpresaCliente


class Command(BaseCommand):
    help = 'Seed de datos demo para entrenar modelo de IA'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando seed_demo...')

        empresa = Empresa.objects.get(nombre='Surtidor Octano')
        operador_norte = Usuario.objects.get(email='operador.norte@estacion.com')
        operador_oeste = Usuario.objects.get(email='operador.oeste@estacion.com')
        suc_norte = Sucursal.objects.get(nombre='Surtidor Octano - Norte')
        suc_oeste = Sucursal.objects.get(nombre='Surtidor Octano - Oeste')
        tipos = list(TipoCombustible.objects.filter(empresa=empresa))

        # Clientes demo
        clientes_data = [
            {'nombre': 'Carlos Mendoza',    'nit': '11111111'},
            {'nombre': 'Ana Gutierrez',     'nit': '22222222'},
            {'nombre': 'Roberto Flores',    'nit': '33333333'},
            {'nombre': 'Lucia Vargas',      'nit': '44444444'},
            {'nombre': 'Diego Mamani',      'nit': '55555555'},
            {'nombre': 'Sofia Condori',     'nit': '66666666'},
            {'nombre': 'Miguel Quispe',     'nit': '77777777'},
            {'nombre': 'Elena Rojas',       'nit': '88888888'},
            {'nombre': 'Transportes Sur',   'nit': '99999999'},
            {'nombre': 'Logistica Andina',  'nit': '10101010'},
        ]

        clientes = []
        for c in clientes_data:
            obj, _ = Cliente.objects.get_or_create(
                nit=c['nit'],
                defaults={'nombre': c['nombre'], 'activo': True}
            )
            EmpresaCliente.objects.get_or_create(empresa=empresa, cliente=obj)
            clientes.append(obj)
        self.stdout.write(f'  {len(clientes)} clientes listos')

        # Configuración por sucursal
        sucursales_config = [
            {'sucursal': suc_norte, 'operador': operador_norte},
            {'sucursal': suc_oeste, 'operador': operador_oeste},
        ]

        horarios = ['MANANA', 'TARDE', 'NOCHE']
        horario_horas = {
            'MANANA': 8,
            'TARDE': 15,
            'NOCHE': 22,
        }

        # Factor de ventas por día de semana (0=lunes, 6=domingo)
        factor_dia = {0: 0.8, 1: 0.9, 2: 1.0, 3: 1.0, 4: 1.2, 5: 1.3, 6: 0.7}

        hoy = timezone.localdate()
        fecha_inicio = hoy - timedelta(days=180)

        total_ventas = 0
        comprobante_counter = 1

        for config in sucursales_config:
            sucursal = config['sucursal']
            operador = config['operador']
            islas = list(sucursal.islas.all())

            if not islas:
                self.stdout.write(f'  Sin islas en {sucursal.nombre}, saltando...')
                continue

            fecha_actual = fecha_inicio
            while fecha_actual < hoy:
                dia_semana = fecha_actual.weekday()
                factor = factor_dia[dia_semana]

                for horario in horarios:
                    for isla in islas:
                        lados = list(isla.lados.all())
                        if not lados:
                            continue

                        # Crear turno
                        hora = horario_horas[horario]
                        fecha_apertura = timezone.make_aware(
                            datetime.combine(fecha_actual, time(hora, 0))
                        )
                        fecha_cierre = fecha_apertura + timedelta(hours=8)

                        turno = Turno.objects.create(
                            operador=operador,
                            isla=isla,
                            horario=horario,
                            sucursal=sucursal,
                            estado='CERRADO',
                            monto_inicial=Decimal('0.00'),
                            fecha_cierre=fecha_cierre,
                            consolidado=True,
                        )
                        # Sobrescribir fecha_apertura (auto_now_add no permite asignar)
                        Turno.objects.filter(pk=turno.pk).update(
                            fecha_apertura=fecha_apertura,
                            created_at=fecha_apertura,
                        )

                        # Ventas por turno (2-5 según factor del día)
                        num_ventas = int(random.randint(2, 5) * factor)
                        for _ in range(num_ventas):
                            lado = random.choice(lados)
                            tipo = random.choice(tipos)
                            cliente = random.choice(clientes + [None, None])  # 33% sin cliente
                            litros = Decimal(str(round(random.uniform(10, 80), 2)))
                            precio = tipo.precio_litro
                            total = (litros * precio).quantize(Decimal('0.01'))

                            comprobante = f'VTA-{fecha_actual.strftime("%Y%m%d")}-{comprobante_counter:05d}'
                            comprobante_counter += 1

                            venta = Venta.objects.create(
                                turno=turno,
                                lado=lado,
                                tipo_combustible=tipo,
                                cliente=cliente,
                                litros=litros,
                                precio_unitario=precio,
                                total=total,
                                metodo_pago=random.choice(['EFECTIVO', 'TARJETA', 'QR', 'CREDITO_FLEET']),
                                estado='COMPLETADA',
                                numero_comprobante=comprobante,
                                client_request_id=uuid.uuid4(),
                                created_by=operador,
                            )
                            # Ajustar fecha_hora al día correcto
                            minuto = random.randint(0, 479)
                            fecha_venta = fecha_apertura + timedelta(minutes=minuto)
                            Venta.objects.filter(pk=venta.pk).update(fecha_hora=fecha_venta)
                            total_ventas += 1

                fecha_actual += timedelta(days=1)

            self.stdout.write(f'  {sucursal.nombre} procesada')

        self.stdout.write(self.style.SUCCESS(f'\n✅ Seed demo completado — {total_ventas} ventas generadas'))
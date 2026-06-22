import random
import uuid
from datetime import timedelta, datetime, time
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from ventas.models import Sucursal, Isla, Lado, TipoCombustible, Cliente, Turno, Venta, EmpresaCliente
from usuarios.models import Usuario, Empresa


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

        # Clientes demo con frecuencia de carga realista
        clientes_data = [
            {'nombre': 'Carlos Mendoza',   'nit': '11111111', 'frecuencia': 7,  'litros_min': 35, 'litros_max': 50},
            {'nombre': 'Ana Gutierrez',    'nit': '22222222', 'frecuencia': 8,  'litros_min': 30, 'litros_max': 45},
            {'nombre': 'Roberto Flores',   'nit': '33333333', 'frecuencia': 6,  'litros_min': 32, 'litros_max': 48},
            {'nombre': 'Lucia Vargas',     'nit': '44444444', 'frecuencia': 10, 'litros_min': 28, 'litros_max': 42},
            {'nombre': 'Diego Mamani',     'nit': '55555555', 'frecuencia': 2,  'litros_min': 20, 'litros_max': 35},  # taxi
            {'nombre': 'Sofia Condori',    'nit': '66666666', 'frecuencia': 9,  'litros_min': 30, 'litros_max': 44},
            {'nombre': 'Miguel Quispe',    'nit': '77777777', 'frecuencia': 3,  'litros_min': 25, 'litros_max': 40},  # transporte
            {'nombre': 'Elena Rojas',      'nit': '88888888', 'frecuencia': 7,  'litros_min': 33, 'litros_max': 50},
            {'nombre': 'Transportes Sur',  'nit': '99999999', 'frecuencia': 1,  'litros_min': 60, 'litros_max': 100}, # flota
            {'nombre': 'Logistica Andina', 'nit': '10101010', 'frecuencia': 2,  'litros_min': 50, 'litros_max': 90},  # flota
        ]

        clientes = []
        for c in clientes_data:
            obj, _ = Cliente.objects.get_or_create(
                nit=c['nit'],
                defaults={'nombre': c['nombre'], 'activo': True}
            )
            EmpresaCliente.objects.get_or_create(empresa=empresa, cliente=obj)
            clientes.append({**c, 'obj': obj, 'ultimo_carga': None})
        self.stdout.write(f'  {len(clientes)} clientes listos')

        sucursales_config = [
            {'sucursal': suc_norte, 'operador': operador_norte},
            {'sucursal': suc_oeste, 'operador': operador_oeste},
        ]

        horarios = ['MANANA', 'TARDE', 'NOCHE']
        horario_horas = {'MANANA': 8, 'TARDE': 15, 'NOCHE': 22}
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

            # Resetear ultimo_carga por sucursal
            for c in clientes:
                c['ultimo_carga'] = None

            fecha_actual = fecha_inicio
            while fecha_actual < hoy:
                dia_semana = fecha_actual.weekday()
                factor = factor_dia[dia_semana]

                for horario in horarios:
                    for isla in islas:
                        lados = list(isla.lados.all())
                        if not lados:
                            continue

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
                        Turno.objects.filter(pk=turno.pk).update(
                            fecha_apertura=fecha_apertura,
                            created_at=fecha_apertura,
                        )

                        # Ventas sin cliente (clientes ocasionales)
                        num_sin_cliente = int(random.randint(2, 5) * factor)
                        for _ in range(num_sin_cliente):
                            lado = random.choice(lados)
                            tipo = random.choice(tipos)
                            litros = Decimal(str(round(random.uniform(15, 60), 2)))
                            precio = tipo.precio_litro
                            total = (litros * precio).quantize(Decimal('0.01'))
                            comprobante = f'VTA-{fecha_actual.strftime("%Y%m%d")}-{comprobante_counter:05d}'
                            comprobante_counter += 1
                            venta = Venta.objects.create(
                                turno=turno, lado=lado, tipo_combustible=tipo,
                                cliente=None, litros=litros, precio_unitario=precio,
                                total=total,
                                metodo_pago=random.choice(['EFECTIVO', 'TARJETA', 'QR']),
                                estado='COMPLETADA', numero_comprobante=comprobante,
                                client_request_id=uuid.uuid4(), created_by=operador,
                            )
                            minuto = random.randint(0, 479)
                            Venta.objects.filter(pk=venta.pk).update(
                                fecha_hora=fecha_apertura + timedelta(minutes=minuto)
                            )
                            total_ventas += 1

                        # Ventas con cliente — solo si le toca según frecuencia
                        for c in clientes:
                            ultimo = c['ultimo_carga']
                            frecuencia = c['frecuencia']
                            # Agregar variación ±1 día a la frecuencia
                            dias_desde_ultimo = (fecha_actual - ultimo).days if ultimo else frecuencia
                            variacion = random.randint(-1, 1)
                            if dias_desde_ultimo >= frecuencia + variacion:
                                lado = random.choice(lados)
                                tipo = random.choice(tipos)
                                litros = Decimal(str(round(
                                    random.uniform(c['litros_min'], c['litros_max']), 2
                                )))
                                precio = tipo.precio_litro
                                total = (litros * precio).quantize(Decimal('0.01'))
                                comprobante = f'VTA-{fecha_actual.strftime("%Y%m%d")}-{comprobante_counter:05d}'
                                comprobante_counter += 1
                                venta = Venta.objects.create(
                                    turno=turno, lado=lado, tipo_combustible=tipo,
                                    cliente=c['obj'], litros=litros, precio_unitario=precio,
                                    total=total,
                                    metodo_pago=random.choice(['EFECTIVO', 'TARJETA', 'QR', 'CREDITO_FLEET']),
                                    estado='COMPLETADA', numero_comprobante=comprobante,
                                    client_request_id=uuid.uuid4(), created_by=operador,
                                )
                                minuto = random.randint(0, 479)
                                Venta.objects.filter(pk=venta.pk).update(
                                    fecha_hora=fecha_apertura + timedelta(minutes=minuto)
                                )
                                c['ultimo_carga'] = fecha_actual
                                total_ventas += 1

                fecha_actual += timedelta(days=1)

            self.stdout.write(f'  {sucursal.nombre} procesada')

        self.stdout.write(self.style.SUCCESS(f'\n✅ Seed demo completado — {total_ventas} ventas generadas'))
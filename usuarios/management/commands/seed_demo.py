import random
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction


class Command(BaseCommand):
    help = 'Pobla la base de datos con datos de demostración realistas'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando seed_demo...')
        
        from ventas.models import Cliente, Vehiculo, Turno, Venta, Isla, Lado, TipoCombustible
        from usuarios.models import Usuario

        # ── DATOS DE EJEMPLO ──────────────────────────────────────────
        nombres = [
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
        metodos_pago = ['EFECTIVO', 'TARJETA', 'QR', 'CREDITO_FLEET']
        horarios = ['MANANA', 'TARDE', 'NOCHE']

        with transaction.atomic():

            # ── 1. CLIENTES Y VEHÍCULOS ───────────────────────────────
            self.stdout.write('  Creando clientes y vehículos...')
            clientes_creados = []

            for i, nombre in enumerate(nombres):
                cliente, creado = Cliente.objects.get_or_create(
                    nombre=nombre,
                    defaults={
                        'nit': f'{random.randint(1000000, 9999999)}',
                        'telefono': f'7{random.randint(1000000, 9999999)}',
                        'limite_credito': random.choice([0, 500, 1000, 2000]),
                        'saldo_credito': random.choice([0, 200, 500, 1000]),
                        'activo': True,
                    }
                )
                if creado:
                    self.stdout.write(f'    Cliente creado: {nombre}')

                marca, modelo = random.choice(marcas_modelos)
                Vehiculo.objects.get_or_create(
                    placa=placas[i],
                    defaults={
                        'cliente': cliente,
                        'marca': marca,
                        'modelo': modelo,
                        'color': random.choice(colores),
                        'activo': True,
                    }
                )
                clientes_creados.append(cliente)

            # ── 2. TURNOS Y VENTAS ────────────────────────────────────
            self.stdout.write('  Creando turnos y ventas...')

            operador = Usuario.objects.filter(
                roles__nombre__iexact='operador'
            ).first()

            if not operador:
                self.stdout.write(self.style.WARNING(
                    '  No se encontró operador. Ejecuta seed primero.'
                ))
                return

            islas = list(Isla.objects.all())
            tipos = list(TipoCombustible.objects.filter(activo=True))

            if not islas or not tipos:
                self.stdout.write(self.style.WARNING(
                    '  No hay islas o tipos de combustible. Ejecuta seed primero.'
                ))
                return

            # Crear turnos de los últimos 30 días
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

                    turno = Turno.objects.create(
                        operador=operador,
                        isla=isla,
                        horario=horario,
                        estado='CERRADO',
                        monto_inicial=random.randint(100, 500),
                        monto_final=random.randint(500, 3000),
                        observaciones='Turno de demostración',
                    )

                    # Ajustar fechas manualmente
                    Turno.objects.filter(pk=turno.pk).update(
                        fecha_apertura=fecha_apertura,
                        fecha_cierre=fecha_cierre,
                        created_at=fecha_apertura,
                    )

                    turnos_creados += 1

                    # 3 a 8 ventas por turno
                    for _ in range(random.randint(3, 8)):
                        tipo = random.choice(tipos)
                        lado = random.choice(lados)
                        metodo = random.choice(metodos_pago)
                        monto = random.choice([50, 100, 150, 200, 250, 300])
                        litros = round(monto / float(tipo.precio_litro), 3)
                        cliente = random.choice(
                            clientes_creados + [None, None]
                        )

                        if metodo == 'CREDITO_FLEET' and (
                            not cliente or cliente.saldo_credito < monto
                        ):
                            metodo = 'EFECTIVO'

                        comprobante = (
                            f"VTA-{fecha_apertura.strftime('%Y%m%d')}"
                            f"-{str(uuid.uuid4())[:8].upper()}"
                        )

                        venta = Venta.objects.create(
                            turno=turno,
                            lado=lado,
                            tipo_combustible=tipo,
                            cliente=cliente,
                            litros=litros,
                            precio_unitario=tipo.precio_litro,
                            total=monto,
                            metodo_pago=metodo,
                            estado='COMPLETADA',
                            numero_comprobante=comprobante,
                            created_by=operador,
                        )

                        # Ajustar fecha de venta
                        fecha_venta = fecha_apertura + timedelta(
                            minutes=random.randint(10, 400)
                        )
                        Venta.objects.filter(pk=venta.pk).update(
                            fecha_hora=fecha_venta
                        )

                        ventas_creadas += 1

            self.stdout.write(self.style.SUCCESS(
                f'\nSeed demo completado:'
                f'\n  Clientes:  {len(clientes_creados)}'
                f'\n  Vehículos: {len(clientes_creados)}'
                f'\n  Turnos:    {turnos_creados}'
                f'\n  Ventas:    {ventas_creadas}'
            ))
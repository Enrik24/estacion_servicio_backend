import os
import pickle
import json
import pandas as pd
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from ventas.models import Venta, TipoCombustible


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ARTIFACTS_DIR = os.path.join(_BASE_DIR, 'ml_artifacts')
_MODEL_PATH = os.path.join(_ARTIFACTS_DIR, 'prediccion_consumo_model.pkl')
_METADATA_PATH = os.path.join(_ARTIFACTS_DIR, 'prediccion_consumo_metadata.json')

FEATURES = ['cliente_id', 'sucursal_id', 'dia', 'mes', 'dia_semana', 'hora', 'tipo_combustible_id', 'rolling_mean_7']


def _cargar_modelo():
    if not os.path.exists(_MODEL_PATH):
        return None, None
    with open(_MODEL_PATH, 'rb') as f:
        model = pickle.load(f)
    with open(_METADATA_PATH, 'r') as f:
        metadata = json.load(f)
    return model, metadata


def _to_decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rolling_mean(ventas_qs) -> float:
    ultimas = list(ventas_qs.order_by('-fecha_hora').values_list('litros', flat=True)[:7])
    if not ultimas:
        return 30.0
    return float(sum(ultimas) / len(ultimas))


def _predecir_dia(model, fecha, cliente_id, sucursal_id, tipo_combustible_id, rolling_mean):
    df = pd.DataFrame([{
        'cliente_id': cliente_id,
        'sucursal_id': sucursal_id,
        'dia': fecha.day,
        'mes': fecha.month,
        'dia_semana': fecha.weekday(),
        'hora': 12,
        'tipo_combustible_id': tipo_combustible_id,
        'rolling_mean_7': rolling_mean,
    }])[FEATURES]
    litros = float(model.predict(df)[0])
    return max(5.0, round(litros, 2))


def generar_prediccion_consumo(*, cliente_id, tipo_periodo, unidad, dias=7):
    model, metadata = _cargar_modelo()
    hoy = timezone.localdate()

    ventas_qs = Venta.objects.filter(cliente_id=cliente_id, estado='COMPLETADA')
    rolling_mean = _rolling_mean(ventas_qs)

    tipo_mas_usado = ventas_qs.values('tipo_combustible_id').order_by('tipo_combustible_id').first()
    tipo_combustible_id = tipo_mas_usado['tipo_combustible_id'] if tipo_mas_usado else 1

    turno_reciente = ventas_qs.select_related('turno').order_by('-fecha_hora').first()
    sucursal_id = turno_reciente.turno.sucursal_id if turno_reciente and turno_reciente.turno else 0

    predicciones = []
    total = Decimal('0.00')

    for i in range(dias):
        fecha = hoy + timedelta(days=i)

        if model:
            litros_pred = _predecir_dia(model, fecha, cliente_id, sucursal_id, tipo_combustible_id, rolling_mean)
        else:
            factor = [0.8, 0.9, 1.0, 1.0, 1.2, 1.3, 0.7][fecha.weekday()]
            litros_pred = round(rolling_mean * factor, 2)

        if unidad == 'MONTO':
            tipo = TipoCombustible.objects.filter(id=tipo_combustible_id).first()
            precio = float(tipo.precio_litro) if tipo else 6.96
            valor_estimado = round(litros_pred * precio, 2)
        else:
            valor_estimado = litros_pred

        predicciones.append({
            'fecha': fecha.isoformat(),
            'valor_estimado': valor_estimado,
            'litros_estimados': litros_pred,
            'unidad': unidad,
        })
        total += _to_decimal(valor_estimado)

    promedio = total / Decimal(str(dias))

    return {
        'cliente_id': cliente_id,
        'tipo_periodo': tipo_periodo,
        'unidad': unidad,
        'horizonte_dias': dias,
        'origen_base': 'random_forest' if model else 'fallback',
        'advertencia': None if model else 'Modelo no encontrado.',
        'modelo_version': metadata.get('model_version') if metadata else None,
        'metricas': metadata.get('metricas_test') if metadata else None,
        'resumen': {
            'total_estimado': float(_to_decimal(total)),
            'promedio_diario': float(_to_decimal(promedio)),
        },
        'predicciones': predicciones,
        'modelo': 'random_forest_regressor',
    }


def generar_prediccion_sucursal(*, sucursal_id, tipo_combustible_id, dias=7):
    model, metadata = _cargar_modelo()
    hoy = timezone.localdate()

    # Obtener ventas históricas de los últimos 30 días para calcular promedio real
    from django.utils import timezone as tz
    from datetime import timedelta
    fecha_inicio = hoy - timedelta(days=30)

    ventas_qs = Venta.objects.filter(
        turno__sucursal_id=sucursal_id,
        tipo_combustible_id=tipo_combustible_id,
        estado='COMPLETADA',
        fecha_hora__date__gte=fecha_inicio,
    )

    # Agrupar por día para obtener promedio diario real
    from django.db.models import Sum
    from django.db.models.functions import TruncDate

    ventas_por_dia = (
        ventas_qs
        .annotate(dia=TruncDate('fecha_hora'))
        .values('dia')
        .annotate(total_litros=Sum('litros'))
        .order_by('dia')
    )

    # Rolling mean de los últimos 7 días con datos reales
    litros_por_dia = [float(v['total_litros']) for v in ventas_por_dia]
    rolling_mean = sum(litros_por_dia[-7:]) / len(litros_por_dia[-7:]) if litros_por_dia else 300.0

    predicciones = []
    total = Decimal('0.00')

    for i in range(dias):
        fecha = hoy + timedelta(days=i)
        factor = [0.85, 0.90, 1.0, 1.0, 1.15, 1.25, 0.75][fecha.weekday()]

        if model:
            # Predecir para múltiples clientes y sumar
            clientes_activos = (
                Venta.objects.filter(
                    turno__sucursal_id=sucursal_id,
                    tipo_combustible_id=tipo_combustible_id,
                    estado='COMPLETADA',
                )
                .values_list('cliente_id', flat=True)
                .distinct()[:20]
            )

            total_litros_dia = Decimal('0.00')
            for cid in clientes_activos:
                rm = _rolling_mean(
                    Venta.objects.filter(
                        cliente_id=cid,
                        turno__sucursal_id=sucursal_id,
                        tipo_combustible_id=tipo_combustible_id,
                        estado='COMPLETADA'
                    )
                )
                litros = _predecir_dia(model, fecha, cid or 0, sucursal_id, tipo_combustible_id, rm)
                total_litros_dia += _to_decimal(litros)

            # Ajustar por factor día de semana
            litros_pred = float(_to_decimal(total_litros_dia * Decimal(str(factor))))
        else:
            litros_pred = round(rolling_mean * factor, 2)

        tipo = TipoCombustible.objects.filter(id=tipo_combustible_id).first()
        precio = float(tipo.precio_litro) if tipo else 6.96
        monto_estimado = round(litros_pred * precio, 2)

        predicciones.append({
            'fecha': fecha.isoformat(),
            'litros_estimados': round(litros_pred, 2),
            'monto_estimado': monto_estimado,
        })
        total += _to_decimal(litros_pred)

    promedio = total / Decimal(str(dias))

    return {
        'sucursal_id': sucursal_id,
        'tipo_combustible_id': tipo_combustible_id,
        'horizonte_dias': dias,
        'origen_base': 'random_forest' if model else 'fallback',
        'modelo_version': metadata.get('model_version') if metadata else None,
        'resumen': {
            'total_litros_estimado': float(_to_decimal(total)),
            'promedio_diario_litros': float(_to_decimal(promedio)),
        },
        'predicciones': predicciones,
        'modelo': 'random_forest_regressor',
    }
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.utils import timezone


def _to_decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _obtener_historial(cliente_id=None, tipo_combustible_id=None, unidad="MONTO", dias_historial=90, sucursal_id=None):
    """
    Obtiene el consumo diario real filtrado por sucursal (tenant).
    - Si cliente_id: filtra por ese cliente
    - Si tipo_combustible_id: filtra por ese combustible
    - Si ninguno: demanda global de la sucursal
    """
    from ventas.models import Venta

    campo = "total" if unidad == "MONTO" else "litros"
    fecha_inicio = timezone.localdate() - timedelta(days=dias_historial)

    qs = Venta.objects.filter(
        estado="COMPLETADA",
        fecha_hora__date__gte=fecha_inicio,
    )

    if sucursal_id is not None:
        qs = qs.filter(turno__sucursal_id=sucursal_id)

    if cliente_id is not None:
        qs = qs.filter(cliente_id=cliente_id)

    if tipo_combustible_id is not None:
        qs = qs.filter(tipo_combustible_id=tipo_combustible_id)

    ventas = (
        qs.values("fecha_hora__date")
        .annotate(consumo=Sum(campo))
        .order_by("fecha_hora__date")
    )

    return {v["fecha_hora__date"]: float(v["consumo"]) for v in ventas}


def _obtener_desglose_turnos(cliente_id=None, tipo_combustible_id=None, unidad="MONTO", dias_historial=90, sucursal_id=None):
    """Calcula el consumo promedio por turno (MANANA/TARDE/NOCHE) filtrado por sucursal."""
    from ventas.models import Venta

    campo = "total" if unidad == "MONTO" else "litros"
    fecha_inicio = timezone.localdate() - timedelta(days=dias_historial)

    qs = Venta.objects.filter(
        estado="COMPLETADA",
        fecha_hora__date__gte=fecha_inicio,
    )

    if sucursal_id is not None:
        qs = qs.filter(turno__sucursal_id=sucursal_id)

    if cliente_id is not None:
        qs = qs.filter(cliente_id=cliente_id)

    if tipo_combustible_id is not None:
        qs = qs.filter(tipo_combustible_id=tipo_combustible_id)

    turnos_data = (
        qs.values("turno__horario")
        .annotate(total_consumo=Sum(campo))
        .order_by("turno__horario")
    )

    # Contar días únicos para promediar
    dias_unicos = (
        qs.values("fecha_hora__date").distinct().count()
    ) or 1

    desglose = {}
    for t in turnos_data:
        horario = t["turno__horario"] or "SIN_TURNO"
        desglose[horario] = {
            "total": float(_to_decimal(t["total_consumo"] or 0)),
            "promedio_diario": float(_to_decimal((t["total_consumo"] or 0) / dias_unicos)),
        }

    # Asegurar que los 3 turnos existan en la respuesta
    for h in ["MANANA", "TARDE", "NOCHE"]:
        if h not in desglose:
            desglose[h] = {"total": 0, "promedio_diario": 0}

    return desglose


def _media_movil(valores, ventana=7):
    """Calcula media móvil simple."""
    if not valores:
        return []
    resultado = []
    for i in range(len(valores)):
        inicio = max(0, i - ventana + 1)
        segmento = valores[inicio: i + 1]
        resultado.append(sum(segmento) / len(segmento))
    return resultado


def generar_prediccion_consumo(
    *,
    cliente_id=None,
    tipo_combustible_id=None,
    tipo_periodo: str = "DIARIO",
    unidad: str = "MONTO",
    dias: int = 7,
    sucursal_id=None,
):
    hoy = timezone.localdate()
    historial = _obtener_historial(cliente_id, tipo_combustible_id, unidad, dias_historial=90, sucursal_id=sucursal_id)
    desglose_turnos = _obtener_desglose_turnos(cliente_id, tipo_combustible_id, unidad, dias_historial=90, sucursal_id=sucursal_id)

    # Determinar modo
    if cliente_id:
        modo = "cliente"
    elif tipo_combustible_id:
        modo = "combustible"
    else:
        modo = "estacion"

    if not historial:
        return {
            "cliente_id": cliente_id,
            "tipo_combustible_id": tipo_combustible_id,
            "modo": modo,
            "tipo_periodo": tipo_periodo,
            "unidad": unidad,
            "horizonte_dias": dias,
            "origen_base": "sin_historial",
            "advertencia": "Sin historial de ventas. No se pueden generar predicciones.",
            "resumen": {
                "total_estimado": 0,
                "promedio_diario": 0,
                "tendencia": "estable",
                "dias_con_datos": 0,
            },
            "predicciones": [
                {"fecha": (hoy + timedelta(days=i)).isoformat(), "valor_estimado": 0, "unidad": unidad}
                for i in range(dias)
            ],
            "historial_reciente": [],
            "desglose_turnos": desglose_turnos,
            "modelo": "media_movil_ventas_v2",
        }

    # Construir serie diaria completa (rellenando días sin ventas con 0)
    fechas_ordenadas = sorted(historial.keys())
    fecha_min = fechas_ordenadas[0]
    fecha_max = fechas_ordenadas[-1]
    total_dias_hist = (fecha_max - fecha_min).days + 1

    serie_diaria = []
    fechas_serie = []
    for i in range(total_dias_hist):
        fecha = fecha_min + timedelta(days=i)
        fechas_serie.append(fecha)
        serie_diaria.append(historial.get(fecha, 0))

    # ── Agrupar según tipo_periodo ──────────────────────────────
    if tipo_periodo == "SEMANAL":
        # Agrupar por número de semana ISO
        semanas = defaultdict(float)
        semanas_fechas = {}
        for fecha, valor in zip(fechas_serie, serie_diaria):
            clave = fecha.isocalendar()[1]  # número de semana
            semanas[clave] += valor
            if clave not in semanas_fechas:
                semanas_fechas[clave] = fecha
        serie_agrupada = list(semanas.values())
        etiqueta_periodo = "semana"
    elif tipo_periodo == "MENSUAL":
        # Agrupar por mes
        meses = defaultdict(float)
        meses_fechas = {}
        for fecha, valor in zip(fechas_serie, serie_diaria):
            clave = (fecha.year, fecha.month)
            meses[clave] += valor
            if clave not in meses_fechas:
                meses_fechas[clave] = fecha
        serie_agrupada = list(meses.values())
        etiqueta_periodo = "mes"
    else:
        # DIARIO: usar serie tal cual
        serie_agrupada = serie_diaria
        etiqueta_periodo = "día"

    # Tendencia sobre la serie agrupada
    promedio_global = sum(serie_agrupada) / len(serie_agrupada) if serie_agrupada else 0
    n_reciente = min(3, len(serie_agrupada))
    ultimos = serie_agrupada[-n_reciente:] if n_reciente > 0 else serie_agrupada
    promedio_reciente = sum(ultimos) / len(ultimos) if ultimos else 0
    factor_tendencia = (promedio_reciente / promedio_global) if promedio_global > 0 else 1.0

    # ── Generar predicciones según granularidad ─────────────────
    predicciones = []

    if tipo_periodo == "DIARIO":
        # Patrón por día de semana
        consumo_por_dia_semana = defaultdict(list)
        for fecha, valor in zip(fechas_serie, serie_diaria):
            consumo_por_dia_semana[fecha.weekday()].append(valor)
        promedios_dia_semana = {
            d: (sum(v) / len(v) if v else 0) for d, v in consumo_por_dia_semana.items()
        }
        for i in range(dias):
            fecha_pred = hoy + timedelta(days=i)
            base = promedios_dia_semana.get(fecha_pred.weekday(), promedio_global)
            valor = _to_decimal(base * factor_tendencia)
            predicciones.append({
                "fecha": fecha_pred.isoformat(),
                "valor_estimado": float(valor),
                "unidad": unidad,
            })

    elif tipo_periodo == "SEMANAL":
        # Cada "día" del horizonte es una semana
        base_semanal = promedio_global * factor_tendencia
        for i in range(dias):
            fecha_inicio_sem = hoy + timedelta(weeks=i)
            valor = _to_decimal(base_semanal)
            predicciones.append({
                "fecha": fecha_inicio_sem.isoformat(),
                "valor_estimado": float(valor),
                "unidad": unidad,
            })

    elif tipo_periodo == "MENSUAL":
        # Cada "día" del horizonte es un mes
        base_mensual = promedio_global * factor_tendencia
        for i in range(dias):
            mes = hoy.month + i
            anio = hoy.year + (mes - 1) // 12
            mes = ((mes - 1) % 12) + 1
            from datetime import date
            fecha_pred = date(anio, mes, 1)
            valor = _to_decimal(base_mensual)
            predicciones.append({
                "fecha": fecha_pred.isoformat(),
                "valor_estimado": float(valor),
                "unidad": unidad,
            })

    total = sum(Decimal(str(p["valor_estimado"])) for p in predicciones)
    promedio_por_periodo = total / Decimal(str(len(predicciones))) if predicciones else Decimal("0")

    # Historial reciente (últimos 14 días en bruto para el gráfico)
    dias_recientes = 14
    historial_reciente = []
    for i in range(dias_recientes, 0, -1):
        fecha = hoy - timedelta(days=i)
        historial_reciente.append({
            "fecha": fecha.isoformat(),
            "valor": historial.get(fecha, 0),
            "unidad": unidad,
        })

    tendencia = "estable"
    if factor_tendencia > 1.05:
        tendencia = "subiendo"
    elif factor_tendencia < 0.95:
        tendencia = "bajando"

    return {
        "cliente_id": cliente_id,
        "tipo_combustible_id": tipo_combustible_id,
        "modo": modo,
        "tipo_periodo": tipo_periodo,
        "unidad": unidad,
        "horizonte_dias": dias,
        "origen_base": "historial_ventas",
        "advertencia": None,
        "resumen": {
            "total_estimado": float(_to_decimal(total)),
            "promedio_por_periodo": float(_to_decimal(promedio_por_periodo)),
            "promedio_diario": float(_to_decimal(promedio_por_periodo)) if tipo_periodo == "DIARIO" else float(_to_decimal(promedio_global * factor_tendencia)),
            "tendencia": tendencia,
            "dias_con_datos": len(historial),
            "etiqueta_periodo": etiqueta_periodo,
        },
        "predicciones": predicciones,
        "historial_reciente": historial_reciente,
        "desglose_turnos": desglose_turnos,
        "modelo": "media_movil_ventas_v2",
    }

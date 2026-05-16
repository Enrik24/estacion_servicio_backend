from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .models import LimiteConsumo


def _to_decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _estimacion_base(cliente_id: int, tipo: str, unidad: str):
    limite_principal = (
        LimiteConsumo.objects.filter(
            cliente_id=cliente_id,
            tipo=tipo,
            unidad=unidad,
            is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )
    if limite_principal:
        return {
            "base": _to_decimal(limite_principal.valor * Decimal("0.72")),
            "origen": "limite_mismo_tipo",
            "limite_referencia": limite_principal,
            "advertencia": None,
        }

    limite_alternativo = (
        LimiteConsumo.objects.filter(
            cliente_id=cliente_id,
            unidad=unidad,
            is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )
    if limite_alternativo:
        return {
            "base": _to_decimal(limite_alternativo.valor * Decimal("0.65")),
            "origen": "limite_otro_tipo_misma_unidad",
            "limite_referencia": limite_alternativo,
            "advertencia": None,
        }

    # Fallback mock cuando no hay límites configurados.
    return {
        "base": _to_decimal(Decimal("120.00")),
        "origen": "fallback_sin_limites",
        "limite_referencia": None,
        "advertencia": (
            f"No hay límites activos en {unidad} para este cliente. "
            "Se usó una predicción base por defecto."
        ),
    }


def generar_prediccion_consumo(
    *,
    cliente_id: int,
    tipo_periodo: str,
    unidad: str,
    dias: int = 7,
):
    contexto_base = _estimacion_base(cliente_id=cliente_id, tipo=tipo_periodo, unidad=unidad)
    base = contexto_base["base"]
    hoy = timezone.localdate()
    variaciones = [
        Decimal("0.90"),
        Decimal("0.96"),
        Decimal("1.01"),
        Decimal("1.05"),
        Decimal("1.08"),
        Decimal("0.98"),
        Decimal("1.03"),
    ]

    predicciones = []
    for i in range(dias):
        factor = variaciones[i % len(variaciones)]
        valor_estimado = _to_decimal(base * factor)
        predicciones.append(
            {
                "fecha": (hoy + timedelta(days=i)).isoformat(),
                "valor_estimado": float(valor_estimado),
                "unidad": unidad,
            }
        )

    total = sum(Decimal(str(item["valor_estimado"])) for item in predicciones)
    promedio = total / Decimal(str(dias))

    return {
        "cliente_id": cliente_id,
        "tipo_periodo": tipo_periodo,
        "unidad": unidad,
        "horizonte_dias": dias,
        "origen_base": contexto_base["origen"],
        "advertencia": contexto_base["advertencia"],
        "resumen": {
            "total_estimado": float(_to_decimal(total)),
            "promedio_diario": float(_to_decimal(promedio)),
        },
        "predicciones": predicciones,
        "modelo": "mock_regla_base_v1",
    }

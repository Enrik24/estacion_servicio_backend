"""Lógica del programa de fidelización por puntos.

Reglas:
- Config por empresa (puntos_por_litro, valor_punto_bs, minimo_canje).
- Se acumulan puntos por cada litro despachado en una venta COMPLETADA.
- Se pueden canjear puntos como descuento sobre el total de la venta.
- Al anular una venta se revierten sus movimientos.
"""
from decimal import Decimal

from .models import ConfiguracionPuntos, MovimientoPuntos


def obtener_config(empresa):
    if not empresa:
        return None
    try:
        cfg = empresa.config_puntos
    except ConfiguracionPuntos.DoesNotExist:
        return None
    return cfg if cfg.activo else None


def calcular_descuento_canje(cliente, puntos, empresa):
    """Valida y retorna (descuento_bs, config). Lanza ValueError si algo falla."""
    cfg = obtener_config(empresa)
    if not cfg:
        raise ValueError('El programa de puntos no está activo para esta empresa')
    if puntos < cfg.minimo_canje:
        raise ValueError(f'El mínimo de canje es {cfg.minimo_canje} puntos')
    if puntos > cliente.puntos_acumulados:
        raise ValueError(f'Puntos insuficientes. Saldo actual: {cliente.puntos_acumulados}')

    descuento = (Decimal(puntos) * cfg.valor_punto_bs).quantize(Decimal('0.01'))
    return descuento, cfg


def registrar_canje(cliente, puntos, descuento, venta, user):
    cliente.puntos_acumulados -= puntos
    cliente.save(update_fields=['puntos_acumulados'])
    MovimientoPuntos.objects.create(
        cliente=cliente,
        venta=venta,
        tipo='CANJE',
        puntos=-puntos,
        saldo_despues=cliente.puntos_acumulados,
        descripcion=(
            f'Canje de {puntos} pts (Bs. {descuento} de descuento) '
            f'en venta {venta.numero_comprobante}'
        ),
        created_by=user,
    )


def acumular_puntos(cliente, litros, empresa, venta, user):
    """Suma puntos al cliente por los litros de una venta. Retorna puntos otorgados."""
    cfg = obtener_config(empresa)
    if not cfg or not litros:
        return 0
    puntos = int(Decimal(str(litros)) * cfg.puntos_por_litro)
    if puntos <= 0:
        return 0
    cliente.puntos_acumulados += puntos
    cliente.save(update_fields=['puntos_acumulados'])
    MovimientoPuntos.objects.create(
        cliente=cliente,
        venta=venta,
        tipo='ACUMULACION',
        puntos=puntos,
        saldo_despues=cliente.puntos_acumulados,
        descripcion=f'{puntos} pts por {litros} Lt en venta {venta.numero_comprobante}',
        created_by=user,
    )
    return puntos


def reversar_puntos_venta(venta, user):
    """Revierte todos los movimientos de puntos de una venta (usar al anular)."""
    movs = list(venta.movimientos_puntos.exclude(tipo='REVERSA'))
    for mov in movs:
        cliente = mov.cliente
        cliente.puntos_acumulados -= mov.puntos
        cliente.save(update_fields=['puntos_acumulados'])
        MovimientoPuntos.objects.create(
            cliente=cliente,
            venta=venta,
            tipo='REVERSA',
            puntos=-mov.puntos,
            saldo_despues=cliente.puntos_acumulados,
            descripcion=f'Reversa por anulación de venta {venta.numero_comprobante}',
            created_by=user,
        )


def ajustar_puntos(cliente, delta, descripcion, user):
    """Ajuste manual (positivo o negativo). Retorna el movimiento creado."""
    if delta == 0:
        raise ValueError('El ajuste no puede ser cero')
    if delta < 0 and abs(delta) > cliente.puntos_acumulados:
        raise ValueError(
            f'No puedes descontar más puntos de los que tiene el cliente '
            f'(saldo actual: {cliente.puntos_acumulados})'
        )
    cliente.puntos_acumulados += delta
    cliente.save(update_fields=['puntos_acumulados'])
    return MovimientoPuntos.objects.create(
        cliente=cliente,
        venta=None,
        tipo='AJUSTE',
        puntos=delta,
        saldo_despues=cliente.puntos_acumulados,
        descripcion=descripcion or 'Ajuste manual',
        created_by=user,
    )

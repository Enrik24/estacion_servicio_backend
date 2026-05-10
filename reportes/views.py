from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from django.conf import settings
from django.utils import timezone
from functools import partial
from decimal import Decimal
from datetime import timedelta
import json
import requests

from ventas.models import Venta, Turno, Sucursal, Isla
from utils.permissions import HasPermiso
from seguridad.models import Bitacora

# Clase pre-configurada compatible con @permission_classes
ReportesPermiso = partial(HasPermiso, permiso='reportes.ver')


def _filtrar_ventas(params):
    """Aplica filtros comunes de fecha, tipo combustible, método de pago y sucursal a Venta."""
    qs = Venta.objects.filter(estado='COMPLETADA')

    fecha_inicio = params.get('fecha_inicio')
    fecha_fin    = params.get('fecha_fin')
    if fecha_inicio:
        qs = qs.filter(fecha_hora__date__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha_hora__date__lte=fecha_fin)

    tipo_combustible = params.get('tipo_combustible')
    if tipo_combustible:
        qs = qs.filter(tipo_combustible__tipo=tipo_combustible)

    metodo_pago = params.get('metodo_pago')
    if metodo_pago:
        qs = qs.filter(metodo_pago=metodo_pago)

    sucursal_id = params.get('sucursal_id')
    if sucursal_id:
        qs = qs.filter(turno__isla__sucursal_id=sucursal_id)

    return qs


def _registrar_bitacora(request, descripcion):
    """Registra una consulta de reporte en la bitácora."""
    Bitacora.objects.create(
        usuario=request.user,
        usuario_email=request.user.email,
        usuario_nombre=request.user.nombre,
        usuario_rol=request.user.nombre_rol,
        accion='CONSULTAR',
        estado='EXITO',
        modulo_afectado='Reportes',
        descripcion=descripcion,
        ip_address=getattr(request, 'ip_address', None),
        user_agent=getattr(request, 'user_agent', '')[:500],
    )


# ── Reporte de Ventas ─────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated, ReportesPermiso])
def reporte_ventas(request):

    qs = _filtrar_ventas(request.query_params)

    # Totales generales
    totales = qs.aggregate(
        total_recaudado=Coalesce(Sum('total'), Decimal('0')),
        total_litros=Coalesce(Sum('litros'), Decimal('0')),
        cantidad_ventas=Count('id'),
    )

    # Desglose por tipo de combustible
    por_combustible = list(
        qs.values('tipo_combustible__tipo')
          .annotate(
              total_recaudado=Coalesce(Sum('total'), Decimal('0')),
              total_litros=Coalesce(Sum('litros'), Decimal('0')),
              cantidad=Count('id'),
          )
          .order_by('-total_recaudado')
    )
    for item in por_combustible:
        tipo = item.pop('tipo_combustible__tipo')
        item['tipo_combustible'] = tipo

    # Desglose por método de pago
    por_metodo = list(
        qs.values('metodo_pago')
          .annotate(
              total_recaudado=Coalesce(Sum('total'), Decimal('0')),
              cantidad=Count('id'),
          )
          .order_by('-total_recaudado')
    )

    # Ventas anuladas (sin filtro de estado para incluirlas)
    qs_todas = Venta.objects.all()
    fecha_inicio = request.query_params.get('fecha_inicio')
    fecha_fin    = request.query_params.get('fecha_fin')
    sucursal_id  = request.query_params.get('sucursal_id')
    if fecha_inicio:
        qs_todas = qs_todas.filter(fecha_hora__date__gte=fecha_inicio)
    if fecha_fin:
        qs_todas = qs_todas.filter(fecha_hora__date__lte=fecha_fin)
    if sucursal_id:
        qs_todas = qs_todas.filter(turno__isla__sucursal_id=sucursal_id)

    por_estado = list(
        qs_todas.values('estado')
                .annotate(cantidad=Count('id'))
    )

    _registrar_bitacora(request, 'Consultó reporte de ventas')

    return Response({
        'resumen': {
            'total_recaudado': totales['total_recaudado'],
            'total_litros':    totales['total_litros'],
            'cantidad_ventas': totales['cantidad_ventas'],
        },
        'por_combustible': por_combustible,
        'por_metodo_pago': por_metodo,
        'por_estado':      por_estado,
    })


# ── Reporte de Turnos ─────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated, ReportesPermiso])
def reporte_turnos(request):

    qs = Turno.objects.select_related('operador', 'isla')

    fecha_inicio = request.query_params.get('fecha_inicio')
    fecha_fin    = request.query_params.get('fecha_fin')
    horario      = request.query_params.get('horario')
    estado       = request.query_params.get('estado')
    isla_id      = request.query_params.get('isla_id')

    if fecha_inicio:
        qs = qs.filter(fecha_apertura__date__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha_apertura__date__lte=fecha_fin)
    if horario:
        qs = qs.filter(horario=horario)
    if estado:
        qs = qs.filter(estado=estado)
    if isla_id:
        qs = qs.filter(isla_id=isla_id)

    turnos_data = []
    for turno in qs:
        ventas = Venta.objects.filter(turno=turno, estado='COMPLETADA')
        agg = ventas.aggregate(
            total_recaudado=Coalesce(Sum('total'), Decimal('0')),
            total_litros=Coalesce(Sum('litros'), Decimal('0')),
            cantidad_ventas=Count('id'),
        )
        turnos_data.append({
            'id':              turno.id,
            'operador':        turno.operador.nombre,
            'isla':            turno.isla.numero,
            'horario':         turno.get_horario_display(),
            'horario_codigo':  turno.horario,
            'estado':          turno.estado,
            'fecha_apertura':  turno.fecha_apertura,
            'fecha_cierre':    turno.fecha_cierre,
            'monto_inicial':   turno.monto_inicial,
            'monto_final':     turno.monto_final,
            'total_recaudado': agg['total_recaudado'],
            'total_litros':    agg['total_litros'],
            'cantidad_ventas': agg['cantidad_ventas'],
        })

    # Desglose por horario
    por_horario = []
    for codigo, label in Turno.HORARIOS:
        turnos_horario = [t for t in turnos_data if t['horario_codigo'] == codigo]
        total = sum(t['total_recaudado'] for t in turnos_horario)
        por_horario.append({
            'horario':         label,
            'horario_codigo':  codigo,
            'cantidad_turnos': len(turnos_horario),
            'total_recaudado': total,
        })

    _registrar_bitacora(request, 'Consultó reporte de turnos')

    return Response({
        'turnos':      turnos_data,
        'por_horario': por_horario,
    })


# ── Reporte de Clientes ───────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated, ReportesPermiso])
def reporte_clientes(request):

    qs = Venta.objects.filter(estado='COMPLETADA', cliente__isnull=False)

    fecha_inicio = request.query_params.get('fecha_inicio')
    fecha_fin    = request.query_params.get('fecha_fin')
    metodo_pago  = request.query_params.get('metodo_pago')
    cliente_id   = request.query_params.get('cliente_id')

    if fecha_inicio:
        qs = qs.filter(fecha_hora__date__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha_hora__date__lte=fecha_fin)
    if metodo_pago:
        qs = qs.filter(metodo_pago=metodo_pago)
    if cliente_id:
        qs = qs.filter(cliente_id=cliente_id)

    ranking = list(
        qs.values('cliente__id', 'cliente__nombre', 'cliente__nit')
          .annotate(
              total_consumido=Coalesce(Sum('total'), Decimal('0')),
              total_litros=Coalesce(Sum('litros'), Decimal('0')),
              cantidad_ventas=Count('id'),
          )
          .order_by('-total_consumido')
    )
    for item in ranking:
        item['cliente_id']     = item.pop('cliente__id')
        item['cliente_nombre'] = item.pop('cliente__nombre')
        item['cliente_nit']    = item.pop('cliente__nit')

    # Uso de crédito fleet
    credito_fleet = list(
        qs.filter(metodo_pago='CREDITO_FLEET')
          .values('cliente__id', 'cliente__nombre')
          .annotate(
              total_credito_usado=Coalesce(Sum('total'), Decimal('0')),
              cantidad=Count('id'),
          )
          .order_by('-total_credito_usado')
    )
    for item in credito_fleet:
        item['cliente_id']     = item.pop('cliente__id')
        item['cliente_nombre'] = item.pop('cliente__nombre')

    _registrar_bitacora(request, 'Consultó reporte de clientes')

    return Response({
        'ranking_clientes':  ranking,
        'uso_credito_fleet': credito_fleet,
    })


# ── Reporte de Sucursales ─────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated, ReportesPermiso])
def reporte_sucursales(request):

    sucursales_qs = Sucursal.objects.all()

    fecha_inicio = request.query_params.get('fecha_inicio')
    fecha_fin    = request.query_params.get('fecha_fin')
    sucursal_id  = request.query_params.get('sucursal_id')
    estado       = request.query_params.get('estado')

    if sucursal_id:
        sucursales_qs = sucursales_qs.filter(id=sucursal_id)
    if estado:
        sucursales_qs = sucursales_qs.filter(estado=estado)

    data = []
    for sucursal in sucursales_qs:
        ventas_qs = Venta.objects.filter(
            estado='COMPLETADA',
            turno__isla__sucursal=sucursal,
        )
        if fecha_inicio:
            ventas_qs = ventas_qs.filter(fecha_hora__date__gte=fecha_inicio)
        if fecha_fin:
            ventas_qs = ventas_qs.filter(fecha_hora__date__lte=fecha_fin)

        agg = ventas_qs.aggregate(
            total_recaudado=Coalesce(Sum('total'), Decimal('0')),
            total_litros=Coalesce(Sum('litros'), Decimal('0')),
            cantidad_ventas=Count('id'),
        )

        cantidad_turnos = Turno.objects.filter(isla__sucursal=sucursal).count()

        data.append({
            'sucursal_id':     sucursal.id,
            'nombre':          sucursal.nombre,
            'direccion':       sucursal.direccion,
            'estado':          sucursal.estado,
            'total_recaudado': agg['total_recaudado'],
            'total_litros':    agg['total_litros'],
            'cantidad_ventas': agg['cantidad_ventas'],
            'cantidad_turnos': cantidad_turnos,
        })

    _registrar_bitacora(request, 'Consultó reporte de sucursales')

    return Response({'sucursales': data})


# ── Reporte de Islas y Lados ──────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated, ReportesPermiso])
def reporte_islas(request):

    islas_qs = Isla.objects.prefetch_related('lados').select_related('sucursal')

    fecha_inicio = request.query_params.get('fecha_inicio')
    fecha_fin    = request.query_params.get('fecha_fin')
    sucursal_id  = request.query_params.get('sucursal_id')
    isla_id      = request.query_params.get('isla_id')

    if sucursal_id:
        islas_qs = islas_qs.filter(sucursal_id=sucursal_id)
    if isla_id:
        islas_qs = islas_qs.filter(id=isla_id)

    data = []
    for isla in islas_qs:
        ventas_isla = Venta.objects.filter(
            estado='COMPLETADA',
            turno__isla=isla,
        )
        if fecha_inicio:
            ventas_isla = ventas_isla.filter(fecha_hora__date__gte=fecha_inicio)
        if fecha_fin:
            ventas_isla = ventas_isla.filter(fecha_hora__date__lte=fecha_fin)

        agg_isla = ventas_isla.aggregate(
            total_recaudado=Coalesce(Sum('total'), Decimal('0')),
            total_litros=Coalesce(Sum('litros'), Decimal('0')),
            cantidad_ventas=Count('id'),
        )

        lados_data = []
        for lado in isla.lados.all():
            ventas_lado = ventas_isla.filter(lado=lado)
            agg_lado = ventas_lado.aggregate(
                total_recaudado=Coalesce(Sum('total'), Decimal('0')),
                total_litros=Coalesce(Sum('litros'), Decimal('0')),
                cantidad_ventas=Count('id'),
            )
            lados_data.append({
                'lado':            lado.lado,
                'activo':          lado.activo,
                'total_recaudado': agg_lado['total_recaudado'],
                'total_litros':    agg_lado['total_litros'],
                'cantidad_ventas': agg_lado['cantidad_ventas'],
            })

        data.append({
            'isla_id':         isla.id,
            'numero':          isla.numero,
            'estado':          isla.estado,
            'sucursal':        isla.sucursal.nombre if isla.sucursal else None,
            'total_recaudado': agg_isla['total_recaudado'],
            'total_litros':    agg_isla['total_litros'],
            'cantidad_ventas': agg_isla['cantidad_ventas'],
            'lados':           lados_data,
        })

    isla_top = max(data, key=lambda x: x['total_recaudado'], default=None)

    _registrar_bitacora(request, 'Consultó reporte de islas y lados')

    return Response({
        'islas':    data,
        'isla_top': {
            'numero':          isla_top['numero'] if isla_top else None,
            'total_recaudado': isla_top['total_recaudado'] if isla_top else 0,
        },
    })


# ── Interpretar Comando de Voz ────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated, ReportesPermiso])
def interpretar_comando(request):
    """
    Recibe texto en lenguaje natural y usa Groq para interpretarlo
    como un comando de reporte estructurado.

    Body esperado: { "texto": "dame los turnos abiertos de la semana pasada en pdf" }

    Respuesta: {
        "pestana": "turnos",
        "params": { "fecha_inicio": "2026-04-29", "fecha_fin": "2026-05-06", "estado": "ABIERTO" },
        "formato": "pdf"
    }
    """
    texto = request.data.get('texto', '').strip()
    if not texto:
        return Response({'error': 'El campo "texto" es requerido y no puede estar vacío.'}, status=400)

    api_key = settings.GROQ_API_KEY
    if not api_key:
        return Response({'error': 'La API key de Groq no está configurada en el servidor.'}, status=500)

    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())          # lunes de esta semana
    fin_semana    = inicio_semana + timedelta(days=6)             # domingo de esta semana
    inicio_semana_pasada = inicio_semana - timedelta(days=7)
    fin_semana_pasada    = fin_semana - timedelta(days=7)
    inicio_mes    = hoy.replace(day=1)
    inicio_mes_pasado = (inicio_mes - timedelta(days=1)).replace(day=1)
    fin_mes_pasado    = inicio_mes - timedelta(days=1)

    prompt = f"""Eres un asistente que interpreta comandos de voz para un sistema de reportes de una estación de servicio (gasolinera).

Fecha actual: {hoy.isoformat()}
Lunes de esta semana: {inicio_semana.isoformat()}
Domingo de esta semana: {fin_semana.isoformat()}
Lunes de la semana pasada: {inicio_semana_pasada.isoformat()}
Domingo de la semana pasada: {fin_semana_pasada.isoformat()}
Primer día del mes actual: {inicio_mes.isoformat()}
Primer día del mes pasado: {inicio_mes_pasado.isoformat()}
Último día del mes pasado: {fin_mes_pasado.isoformat()}

Tu tarea es convertir el siguiente texto en un JSON estructurado con exactamente estas claves:
- "pestana": una de ["ventas", "turnos", "clientes", "sucursales", "islas"]
- "params": objeto con los filtros aplicables según la pestaña (puede estar vacío {{}})
- "formato": uno de ["html", "pdf", "excel"] (por defecto "html" si no se menciona)

Filtros disponibles por pestaña:
- ventas: fecha_inicio, fecha_fin, tipo_combustible (GASOLINA/DIESEL/GAS_NATURAL), metodo_pago (EFECTIVO/TARJETA/CREDITO_FLEET/QR), sucursal_id
- turnos: fecha_inicio, fecha_fin, horario (MANANA/TARDE/NOCHE), estado (ABIERTO/CERRADO), isla_id
- clientes: fecha_inicio, fecha_fin, metodo_pago, cliente_id
- sucursales: fecha_inicio, fecha_fin, sucursal_id, estado (ACTIVA/INACTIVA)
- islas: fecha_inicio, fecha_fin, sucursal_id, isla_id

Reglas importantes:
1. Las fechas deben estar en formato YYYY-MM-DD.
2. Si el texto menciona "hoy", usa {hoy.isoformat()} para ambas fechas.
3. Si menciona "esta semana", usa fecha_inicio={inicio_semana.isoformat()} y fecha_fin={fin_semana.isoformat()}.
4. Si menciona "semana pasada", usa fecha_inicio={inicio_semana_pasada.isoformat()} y fecha_fin={fin_semana_pasada.isoformat()}.
5. Si menciona "este mes", usa fecha_inicio={inicio_mes.isoformat()} y fecha_fin={hoy.isoformat()}.
6. Si menciona "mes pasado", usa fecha_inicio={inicio_mes_pasado.isoformat()} y fecha_fin={fin_mes_pasado.isoformat()}.
7. Si no se menciona fecha, no incluyas fecha_inicio ni fecha_fin en params.
8. Si no puedes determinar la pestaña con certeza, usa "ventas" como valor por defecto.
9. Responde ÚNICAMENTE con el JSON, sin explicaciones, sin markdown, sin texto adicional.

Texto a interpretar: "{texto}"

JSON:"""

    groq_url = 'https://api.groq.com/openai/v1/chat/completions'

    try:
        response = requests.post(
            groq_url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.1,
                'max_tokens': 256,
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        return Response({'error': 'La solicitud a Groq tardó demasiado. Intenta de nuevo.'}, status=504)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return Response(
                {'error': 'Se superó la cuota de la API de Groq. Espera unos minutos e intenta de nuevo.'},
                status=429,
            )
        return Response({'error': f'Error al contactar la API de Groq: {str(e)}'}, status=502)
    except requests.exceptions.RequestException as e:
        return Response({'error': f'Error al contactar la API de Groq: {str(e)}'}, status=502)

    try:
        raw_text = response.json()['choices'][0]['message']['content']
        # Limpiar posibles bloques de código markdown que el modelo a veces incluye
        raw_text = raw_text.strip()
        if raw_text.startswith('```'):
            raw_text = raw_text.split('\n', 1)[-1]
            raw_text = raw_text.rsplit('```', 1)[0]
        resultado = json.loads(raw_text.strip())
    except (KeyError, IndexError, json.JSONDecodeError):
        return Response(
            {'error': 'Groq devolvió una respuesta inesperada. No se pudo interpretar el comando.'},
            status=422,
        )

    _registrar_bitacora(request, f'Interpretó comando de voz: "{texto[:100]}"')

    return Response(resultado)

"""
Motor del Asistente Conversacional con IA.

Convierte una pregunta en lenguaje natural ("¿cuánto diésel vendí esta semana?",
"¿qué cliente consume más?", "predice mi demanda del lunes") en una respuesta
redactada, consultando los modelos reales del sistema con alcance multi-tenant
(filtrado por la sucursal del usuario autenticado).

Flujo de 3 fases:
    1. PLANIFICAR  -> Groq clasifica la pregunta en {intencion, params} (JSON).
    2. CONSULTAR   -> Se ejecutan consultas reales sobre Venta/Turno/Cliente
                      (scoped a la sucursal) o el servicio de predicción.
    3. REDACTAR    -> Groq compone una respuesta en español usando los datos reales.

Si Groq no está configurado o falla, hay degradación elegante:
clasificación por palabras clave + respuesta a partir de plantillas.
"""
from datetime import timedelta
from decimal import Decimal
import json

import requests
from django.conf import settings
from django.db.models import Sum, Count
from django.db.models.functions import Coalesce
from django.utils import timezone


GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'llama-3.3-70b-versatile'

INTENCIONES = ('ventas', 'clientes', 'turnos', 'combustible', 'prediccion', 'desconocido')


# ── Utilidades ────────────────────────────────────────────────────────────────
def _f(value) -> float:
    """Convierte Decimal/None a float plano (serializable para el prompt)."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _contexto_fechas():
    """Calcula anclas de fechas relativas para resolver 'esta semana', etc."""
    hoy = timezone.localdate()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    inicio_semana_pasada = inicio_semana - timedelta(days=7)
    fin_semana_pasada = fin_semana - timedelta(days=7)
    inicio_mes = hoy.replace(day=1)
    inicio_mes_pasado = (inicio_mes - timedelta(days=1)).replace(day=1)
    fin_mes_pasado = inicio_mes - timedelta(days=1)
    return {
        'hoy': hoy,
        'inicio_semana': inicio_semana,
        'fin_semana': fin_semana,
        'inicio_semana_pasada': inicio_semana_pasada,
        'fin_semana_pasada': fin_semana_pasada,
        'inicio_mes': inicio_mes,
        'inicio_mes_pasado': inicio_mes_pasado,
        'fin_mes_pasado': fin_mes_pasado,
    }


def _llamar_groq(prompt, temperature=0.2, max_tokens=512):
    """Llama a Groq. Devuelve el texto de la respuesta o lanza excepción."""
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise RuntimeError('GROQ_API_KEY no configurada')

    response = requests.post(
        GROQ_URL,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': GROQ_MODEL,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temperature,
            'max_tokens': max_tokens,
        },
        timeout=(3, 15),
    )
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']


def _extraer_json(texto):
    """Extrae un objeto JSON de la respuesta del modelo (tolera markdown)."""
    texto = (texto or '').strip()
    if texto.startswith('```'):
        texto = texto.split('\n', 1)[-1]
        texto = texto.rsplit('```', 1)[0]
    texto = texto.strip()
    # Recortar a las llaves externas por si hay texto adicional
    inicio = texto.find('{')
    fin = texto.rfind('}')
    if inicio != -1 and fin != -1 and fin > inicio:
        texto = texto[inicio:fin + 1]
    return json.loads(texto)


def _filtro_combustible(qs, valor):
    """Aplica filtro de combustible aceptando códigos exactos o términos generales."""
    if not valor:
        return qs
    v = str(valor).strip().upper()
    if v in ('DIESEL', 'DIÉSEL', 'DISEL'):
        return qs.filter(tipo_combustible__tipo='DIESEL')
    if v in ('GNV', 'GAS', 'GAS NATURAL', 'GAS_NATURAL', 'GAS NATURAL VEHICULAR'):
        return qs.filter(tipo_combustible__tipo='GNV')
    if v.startswith('GASOLINA'):
        # 'GASOLINA' general -> ambas; específica -> exacta
        if 'PREMIUM' in v:
            return qs.filter(tipo_combustible__tipo='GASOLINA_PREMIUM')
        if 'ESPECIAL' in v:
            return qs.filter(tipo_combustible__tipo='GASOLINA_ESPECIAL')
        return qs.filter(tipo_combustible__tipo__startswith='GASOLINA')
    # Código exacto desconocido: intento directo
    return qs.filter(tipo_combustible__tipo=v)


def _aplicar_fechas(qs, params):
    fi = params.get('fecha_inicio')
    ff = params.get('fecha_fin')
    if fi:
        qs = qs.filter(fecha_hora__date__gte=fi)
    if ff:
        qs = qs.filter(fecha_hora__date__lte=ff)
    return qs


# ── Fase 2: consultas reales (multi-tenant) ───────────────────────────────────
def _base_ventas(sucursal_id):
    from ventas.models import Venta
    qs = Venta.objects.filter(estado='COMPLETADA')
    if sucursal_id is not None:
        qs = qs.filter(turno__sucursal_id=sucursal_id)
    return qs


def _datos_ventas(sucursal_id, params):
    qs = _aplicar_fechas(_base_ventas(sucursal_id), params)
    qs = _filtro_combustible(qs, params.get('tipo_combustible'))
    if params.get('metodo_pago'):
        qs = qs.filter(metodo_pago=params['metodo_pago'])

    tot = qs.aggregate(
        total=Coalesce(Sum('total'), Decimal('0')),
        litros=Coalesce(Sum('litros'), Decimal('0')),
        cantidad=Count('id'),
    )
    por_combustible = [
        {
            'tipo_combustible': r['tipo_combustible__tipo'],
            'total': _f(r['total']),
            'litros': _f(r['litros']),
            'cantidad': r['cantidad'],
        }
        for r in qs.values('tipo_combustible__tipo')
        .annotate(total=Coalesce(Sum('total'), Decimal('0')),
                  litros=Coalesce(Sum('litros'), Decimal('0')),
                  cantidad=Count('id'))
        .order_by('-total')
    ]
    por_metodo = [
        {'metodo_pago': r['metodo_pago'], 'total': _f(r['total']), 'cantidad': r['cantidad']}
        for r in qs.values('metodo_pago')
        .annotate(total=Coalesce(Sum('total'), Decimal('0')), cantidad=Count('id'))
        .order_by('-total')
    ]
    return {
        'total_recaudado_bs': _f(tot['total']),
        'total_litros': _f(tot['litros']),
        'cantidad_ventas': tot['cantidad'],
        'por_combustible': por_combustible,
        'por_metodo_pago': por_metodo,
        'periodo': {
            'fecha_inicio': params.get('fecha_inicio'),
            'fecha_fin': params.get('fecha_fin'),
        },
    }


def _datos_combustible(sucursal_id, params):
    """Igual que ventas pero enfocado al ranking por tipo de combustible."""
    base = _datos_ventas(sucursal_id, params)
    ranking = base['por_combustible']
    return {
        'ranking_combustible': ranking,
        'combustible_top': ranking[0] if ranking else None,
        'total_litros': base['total_litros'],
        'periodo': base['periodo'],
    }


def _datos_clientes(sucursal_id, params, limite=8):
    from ventas.models import Venta
    qs = Venta.objects.filter(estado='COMPLETADA', cliente__isnull=False)
    if sucursal_id is not None:
        qs = qs.filter(turno__sucursal_id=sucursal_id)
    qs = _aplicar_fechas(qs, params)
    if params.get('metodo_pago'):
        qs = qs.filter(metodo_pago=params['metodo_pago'])

    # Filtro opcional por nombre de cliente
    nombre = params.get('cliente_nombre')
    if nombre:
        qs = qs.filter(cliente__nombre__icontains=nombre)

    ranking = [
        {
            'cliente': r['cliente__nombre'],
            'nit': r['cliente__nit'],
            'total_consumido_bs': _f(r['total']),
            'total_litros': _f(r['litros']),
            'cantidad_compras': r['cantidad'],
        }
        for r in qs.values('cliente__id', 'cliente__nombre', 'cliente__nit')
        .annotate(total=Coalesce(Sum('total'), Decimal('0')),
                  litros=Coalesce(Sum('litros'), Decimal('0')),
                  cantidad=Count('id'))
        .order_by('-total')[:limite]
    ]
    return {
        'ranking_clientes': ranking,
        'cliente_top': ranking[0] if ranking else None,
        'periodo': {
            'fecha_inicio': params.get('fecha_inicio'),
            'fecha_fin': params.get('fecha_fin'),
        },
    }


def _datos_turnos(sucursal_id, params):
    from ventas.models import Turno, Venta
    qs = Turno.objects.all()
    if sucursal_id is not None:
        qs = qs.filter(sucursal_id=sucursal_id)
    fi = params.get('fecha_inicio')
    ff = params.get('fecha_fin')
    if fi:
        qs = qs.filter(fecha_apertura__date__gte=fi)
    if ff:
        qs = qs.filter(fecha_apertura__date__lte=ff)
    if params.get('horario'):
        qs = qs.filter(horario=params['horario'])
    if params.get('estado'):
        qs = qs.filter(estado=params['estado'])

    abiertos = qs.filter(estado='ABIERTO').count()
    cerrados = qs.filter(estado='CERRADO').count()

    por_horario = []
    for codigo, label in Turno.HORARIOS:
        turnos_h = qs.filter(horario=codigo)
        ventas_h = Venta.objects.filter(estado='COMPLETADA', turno__in=turnos_h)
        agg = ventas_h.aggregate(total=Coalesce(Sum('total'), Decimal('0')))
        por_horario.append({
            'horario': label,
            'cantidad_turnos': turnos_h.count(),
            'total_recaudado_bs': _f(agg['total']),
        })

    return {
        'total_turnos': qs.count(),
        'turnos_abiertos': abiertos,
        'turnos_cerrados': cerrados,
        'por_horario': por_horario,
        'periodo': {'fecha_inicio': fi, 'fecha_fin': ff},
    }


def _datos_prediccion(sucursal_id, params):
    from usuarios.prediccion_consumo_service import generar_prediccion_consumo
    from ventas.models import Cliente, TipoCombustible

    cliente_id = None
    nombre = params.get('cliente_nombre')
    if nombre:
        c = Cliente.objects.filter(nombre__icontains=nombre).first()
        if c:
            cliente_id = c.id

    tipo_combustible_id = None
    tc = params.get('tipo_combustible')
    if tc:
        v = str(tc).strip().upper()
        obj = None
        if v.startswith('GASOLINA') and 'PREMIUM' not in v and 'ESPECIAL' not in v:
            obj = TipoCombustible.objects.filter(tipo__startswith='GASOLINA').first()
        else:
            mapa = {'GAS': 'GNV', 'GAS NATURAL': 'GNV', 'GAS_NATURAL': 'GNV',
                    'DIÉSEL': 'DIESEL', 'DISEL': 'DIESEL'}
            codigo = mapa.get(v, v)
            obj = TipoCombustible.objects.filter(tipo=codigo).first()
        if obj:
            tipo_combustible_id = obj.id

    resultado = generar_prediccion_consumo(
        cliente_id=cliente_id,
        tipo_combustible_id=tipo_combustible_id,
        tipo_periodo=params.get('tipo_periodo', 'DIARIO'),
        unidad=params.get('unidad', 'MONTO'),
        dias=int(params.get('dias', 7) or 7),
        sucursal_id=sucursal_id,
    )
    # Recortar para el prompt: lo esencial
    return {
        'modo': resultado.get('modo'),
        'tipo_periodo': resultado.get('tipo_periodo'),
        'unidad': resultado.get('unidad'),
        'horizonte': resultado.get('horizonte_dias'),
        'resumen': resultado.get('resumen'),
        'predicciones': resultado.get('predicciones', [])[:10],
        'desglose_turnos': resultado.get('desglose_turnos'),
        'advertencia': resultado.get('advertencia'),
    }


def _ejecutar(intencion, sucursal_id, params):
    if intencion == 'ventas':
        return _datos_ventas(sucursal_id, params)
    if intencion == 'combustible':
        return _datos_combustible(sucursal_id, params)
    if intencion == 'clientes':
        return _datos_clientes(sucursal_id, params)
    if intencion == 'turnos':
        return _datos_turnos(sucursal_id, params)
    if intencion == 'prediccion':
        return _datos_prediccion(sucursal_id, params)
    return {}


# ── Fase 1: planificación ─────────────────────────────────────────────────────
def _prompt_planificacion(pregunta, ctx, historial):
    hist_txt = ''
    if historial:
        ultimos = historial[-6:]
        lineas = [f"{m.get('rol', 'usuario')}: {m.get('contenido', '')}" for m in ultimos]
        hist_txt = "\nContexto de la conversación previa:\n" + "\n".join(lineas) + "\n"

    return f"""Eres el planificador de un asistente de datos para una estación de servicio (gasolinera) en Bolivia.
Tu tarea es convertir la pregunta del usuario en un JSON que indique QUÉ datos consultar.

Fecha actual: {ctx['hoy'].isoformat()}
Lunes de esta semana: {ctx['inicio_semana'].isoformat()}
Domingo de esta semana: {ctx['fin_semana'].isoformat()}
Lunes de la semana pasada: {ctx['inicio_semana_pasada'].isoformat()}
Domingo de la semana pasada: {ctx['fin_semana_pasada'].isoformat()}
Primer día del mes actual: {ctx['inicio_mes'].isoformat()}
Primer día del mes pasado: {ctx['inicio_mes_pasado'].isoformat()}
Último día del mes pasado: {ctx['fin_mes_pasado'].isoformat()}
{hist_txt}
Devuelve EXACTAMENTE este JSON:
{{
  "intencion": "ventas | clientes | turnos | combustible | prediccion | desconocido",
  "params": {{
    "fecha_inicio": "YYYY-MM-DD o null",
    "fecha_fin": "YYYY-MM-DD o null",
    "tipo_combustible": "GASOLINA_ESPECIAL | GASOLINA_PREMIUM | GASOLINA | DIESEL | GNV o null",
    "metodo_pago": "EFECTIVO | TARJETA | QR | CREDITO_FLEET o null",
    "horario": "MANANA | TARDE | NOCHE o null",
    "estado": "ABIERTO | CERRADO o null",
    "cliente_nombre": "texto o null",
    "tipo_periodo": "DIARIO | SEMANAL | MENSUAL",
    "unidad": "MONTO | LITROS",
    "dias": 7
  }}
}}

Guía de intención:
- "ventas": cuánto se vendió/recaudó, ingresos, litros despachados, por método de pago.
- "combustible": qué combustible se vende más, ranking o comparación entre combustibles.
- "clientes": qué cliente consume/compra más, ranking de clientes, crédito de clientes.
- "turnos": cuántos turnos, turnos abiertos/cerrados, recaudación por horario (mañana/tarde/noche).
- "prediccion": predecir/estimar/pronosticar demanda o consumo futuro (mañana, próxima semana, lunes, etc.).
- "desconocido": si no encaja en lo anterior.

Reglas:
1. Fechas en formato YYYY-MM-DD. Si no se menciona periodo, deja fecha_inicio y fecha_fin en null.
2. "hoy" => fecha_inicio y fecha_fin = {ctx['hoy'].isoformat()}.
3. "esta semana" => {ctx['inicio_semana'].isoformat()} a {ctx['fin_semana'].isoformat()}.
4. "semana pasada" => {ctx['inicio_semana_pasada'].isoformat()} a {ctx['fin_semana_pasada'].isoformat()}.
5. "este mes" => {ctx['inicio_mes'].isoformat()} a {ctx['hoy'].isoformat()}.
6. "mes pasado" => {ctx['inicio_mes_pasado'].isoformat()} a {ctx['fin_mes_pasado'].isoformat()}.
7. Si la unidad de la pregunta es litros, usa unidad="LITROS"; si es dinero/Bs, usa "MONTO".
8. Para predicción: "mañana" o "el lunes" => dias=1 y tipo_periodo="DIARIO"; "próxima semana" => tipo_periodo="SEMANAL", dias=1; si no se especifica, dias=7.
9. tipo_periodo por defecto "DIARIO", unidad por defecto "MONTO", dias por defecto 7.
10. Responde ÚNICAMENTE con el JSON, sin explicaciones ni markdown.

Pregunta del usuario: "{pregunta}"

JSON:"""


def _planificar(pregunta, ctx, historial):
    """Devuelve (intencion, params). Usa Groq; si falla, heurística de palabras clave."""
    try:
        raw = _llamar_groq(_prompt_planificacion(pregunta, ctx, historial),
                           temperature=0.1, max_tokens=320)
        data = _extraer_json(raw)
        intencion = data.get('intencion', 'desconocido')
        if intencion not in INTENCIONES:
            intencion = 'desconocido'
        params = data.get('params') or {}
        # Limpiar 'null' textuales
        params = {k: (None if v in ('null', '', 'None') else v) for k, v in params.items()}
        return intencion, params
    except Exception:
        return _planificar_heuristico(pregunta, ctx)


def _planificar_heuristico(pregunta, ctx):
    """Clasificador de respaldo sin LLM, por palabras clave."""
    t = (pregunta or '').lower()
    params = {}

    # Periodo simple
    if 'hoy' in t:
        params['fecha_inicio'] = params['fecha_fin'] = ctx['hoy'].isoformat()
    elif 'semana pasada' in t:
        params['fecha_inicio'] = ctx['inicio_semana_pasada'].isoformat()
        params['fecha_fin'] = ctx['fin_semana_pasada'].isoformat()
    elif 'semana' in t:
        params['fecha_inicio'] = ctx['inicio_semana'].isoformat()
        params['fecha_fin'] = ctx['fin_semana'].isoformat()
    elif 'mes pasado' in t:
        params['fecha_inicio'] = ctx['inicio_mes_pasado'].isoformat()
        params['fecha_fin'] = ctx['fin_mes_pasado'].isoformat()
    elif 'mes' in t:
        params['fecha_inicio'] = ctx['inicio_mes'].isoformat()
        params['fecha_fin'] = ctx['hoy'].isoformat()

    if 'litro' in t:
        params['unidad'] = 'LITROS'
    if 'diesel' in t or 'diésel' in t:
        params['tipo_combustible'] = 'DIESEL'
    elif 'premium' in t:
        params['tipo_combustible'] = 'GASOLINA_PREMIUM'
    elif 'especial' in t:
        params['tipo_combustible'] = 'GASOLINA_ESPECIAL'
    elif 'gasolina' in t:
        params['tipo_combustible'] = 'GASOLINA'
    elif 'gnv' in t or 'gas natural' in t:
        params['tipo_combustible'] = 'GNV'

    if any(p in t for p in ('predice', 'predic', 'pronost', 'estima', 'demanda', 'futur', 'mañana', 'próxim', 'proxim')):
        intencion = 'prediccion'
    elif 'cliente' in t:
        intencion = 'clientes'
    elif 'turno' in t:
        intencion = 'turnos'
    elif any(p in t for p in ('combustible', 'qué se vende', 'que se vende', 'cuál vende', 'cual vende')):
        intencion = 'combustible'
    elif any(p in t for p in ('vend', 'venta', 'recaud', 'ingreso', 'cuánto', 'cuanto')):
        intencion = 'ventas'
    else:
        intencion = 'desconocido'

    return intencion, params


# ── Fase 3: redacción ─────────────────────────────────────────────────────────
def _prompt_redaccion(pregunta, intencion, datos, ctx):
    return f"""Eres un asistente analista de una estación de servicio en Bolivia. La moneda es el Boliviano (Bs).
Responde la pregunta del usuario de forma clara, breve y profesional EN ESPAÑOL, usando ÚNICAMENTE los datos proporcionados.

Reglas:
- Usa los números exactos de los datos. Formatea dinero como "Bs. 1.234,50" aproximadamente y litros como "1.234 L".
- No inventes datos que no estén presentes. Si los datos están vacíos o en cero, dilo con naturalidad ("No se registran ventas en ese periodo").
- Sé conciso (2 a 5 frases). Puedes usar una lista corta si ayuda a la claridad.
- Si la intención es "prediccion", aclara que es una estimación basada en el historial.
- No muestres JSON ni nombres de campos técnicos. Habla como a un dueño de negocio.
- Fecha actual: {ctx['hoy'].isoformat()}.

Pregunta: "{pregunta}"
Intención detectada: {intencion}
Datos (JSON):
{json.dumps(datos, ensure_ascii=False, default=str)}

Respuesta:"""


def _redactar(pregunta, intencion, datos, ctx):
    try:
        return _llamar_groq(_prompt_redaccion(pregunta, intencion, datos, ctx),
                           temperature=0.4, max_tokens=512).strip()
    except Exception:
        return _redactar_plantilla(intencion, datos)


def _fmt_bs(v):
    return f"Bs. {_f(v):,.2f}"


def _fmt_l(v):
    return f"{_f(v):,.0f} L"


def _redactar_plantilla(intencion, datos):
    """Respuesta de respaldo sin LLM, a partir de plantillas."""
    if intencion == 'ventas':
        if not datos.get('cantidad_ventas'):
            return 'No se registran ventas para ese periodo.'
        return (f"Se recaudaron {_fmt_bs(datos['total_recaudado_bs'])} "
                f"({_fmt_l(datos['total_litros'])}) en {datos['cantidad_ventas']} ventas.")
    if intencion == 'combustible':
        top = datos.get('combustible_top')
        if not top:
            return 'No hay ventas de combustible registradas en ese periodo.'
        return (f"El combustible más vendido es {top['tipo_combustible']} con "
                f"{_fmt_bs(top['total'])} ({_fmt_l(top['litros'])}).")
    if intencion == 'clientes':
        top = datos.get('cliente_top')
        if not top:
            return 'No hay consumo de clientes registrado en ese periodo.'
        return (f"El cliente que más consume es {top['cliente']} con "
                f"{_fmt_bs(top['total_consumido_bs'])} en {top['cantidad_compras']} compras.")
    if intencion == 'turnos':
        return (f"Hay {datos.get('total_turnos', 0)} turnos en total "
                f"({datos.get('turnos_abiertos', 0)} abiertos, "
                f"{datos.get('turnos_cerrados', 0)} cerrados).")
    if intencion == 'prediccion':
        if datos.get('advertencia'):
            return datos['advertencia']
        r = datos.get('resumen') or {}
        return (f"Estimación basada en el historial: total previsto "
                f"{_fmt_bs(r.get('total_estimado', 0))}, tendencia {r.get('tendencia', 'estable')}.")
    return ('Puedo ayudarte con ventas, clientes, turnos, combustibles y predicciones de '
            'demanda. Prueba: "¿cuánto diésel vendí esta semana?".')


# ── Sugerencias de seguimiento ────────────────────────────────────────────────
def _sugerencias(intencion):
    base = {
        'ventas': [
            '¿Cuánto vendí hoy?',
            '¿Cuántos litros de diésel despaché esta semana?',
            '¿Cuál fue mi recaudación del mes pasado?',
        ],
        'combustible': [
            '¿Qué combustible se vende más esta semana?',
            '¿Cuántos litros de GNV vendí este mes?',
            'Compara las ventas por tipo de combustible',
        ],
        'clientes': [
            '¿Qué cliente consume más?',
            'Top 5 clientes del mes',
            '¿Quién usa más crédito fleet?',
        ],
        'turnos': [
            '¿Cuántos turnos están abiertos?',
            '¿Qué horario recauda más?',
            'Turnos cerrados de esta semana',
        ],
        'prediccion': [
            'Predice mi demanda de mañana',
            'Estima el consumo de diésel de la próxima semana',
            'Pronóstico de ventas para los próximos 7 días',
        ],
    }
    return base.get(intencion, [
        '¿Cuánto vendí esta semana?',
        '¿Qué cliente consume más?',
        'Predice mi demanda de mañana',
    ])


# ── Orquestador ───────────────────────────────────────────────────────────────
def responder_asistente(pregunta, sucursal_id=None, historial=None):
    """
    Punto de entrada del asistente.

    Args:
        pregunta: texto en lenguaje natural del usuario.
        sucursal_id: id de la sucursal del usuario (None = sin filtro / global).
        historial: lista opcional de {rol, contenido} con la conversación previa.

    Returns:
        dict con: respuesta, intencion, params, datos, sugerencias, modelo.
    """
    ctx = _contexto_fechas()
    intencion, params = _planificar(pregunta, ctx, historial)

    if intencion == 'desconocido':
        return {
            'respuesta': ('Puedo responder sobre ventas, clientes, turnos, combustibles y '
                          'predicciones de demanda de tu estación. Por ejemplo: '
                          '"¿cuánto diésel vendí esta semana?", "¿qué cliente consume más?" '
                          'o "predice mi demanda de mañana".'),
            'intencion': intencion,
            'params': params,
            'datos': {},
            'sugerencias': _sugerencias('desconocido'),
            'modelo': 'asistente_conversacional_v1',
        }

    datos = _ejecutar(intencion, sucursal_id, params)
    respuesta = _redactar(pregunta, intencion, datos, ctx)

    return {
        'respuesta': respuesta,
        'intencion': intencion,
        'params': params,
        'datos': datos,
        'sugerencias': _sugerencias(intencion),
        'modelo': 'asistente_conversacional_v1',
    }

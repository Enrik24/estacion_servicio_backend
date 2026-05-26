import requests
from django.conf import settings


def enviar_notificacion(titulo, mensaje):
    url = 'https://onesignal.com/api/v1/notifications'
    headers = {
        'Authorization': f'Basic {settings.ONESIGNAL_API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'app_id': settings.ONESIGNAL_APP_ID,
        'headings': {'es': titulo, 'en': titulo},
        'contents': {'es': mensaje, 'en': mensaje},
        'included_segments': ['Total Subscriptions'],
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f'OneSignal response: {response.status_code} - {response.json()}')
        return response.json()
    except Exception as e:
        print(f'Error enviando notificación OneSignal: {e}')
        return None

def notificar_nivel_critico(tanque):
    print(f'⚠️ Intentando enviar notificación nivel crítico...')
    try:
        titulo = '⚠️ Nivel crítico de combustible'
        mensaje = (
            f'{tanque.sucursal.nombre} — {tanque.tipo_combustible.get_tipo_display()}: '
            f'{tanque.nivel_actual} Lt ({tanque.porcentaje_nivel}% de capacidad)'
        )
        print(f'⚠️ Mensaje: {mensaje}')
        resultado = enviar_notificacion(titulo, mensaje)
        print(f'⚠️ Resultado: {resultado}')
        return resultado
    except Exception as e:
        print(f'⚠️ Error en notificacion: {e}')
        return None


def notificar_falla_surtidor(lado, descripcion, reportado_por):
    print(f'🔴 Intentando enviar notificación de falla...')
    titulo = '🔴 Falla en surtidor'
    mensaje = (
        f'Isla {lado.isla.numero} - Lado {lado.lado} '
        f'({lado.isla.sucursal.nombre}): {descripcion}. '
        f'Reportado por {reportado_por.nombre}'
    )
    resultado = enviar_notificacion(titulo, mensaje)
    print(f'🔴 Resultado OneSignal: {resultado}')
    return resultado
"""
Utilidades para la bitácora del sistema.
Incluye detección de dispositivo, obtención de IP, y funciones de registro.
"""

def detectar_dispositivo(request):
    """
    Detecta el tipo de dispositivo basado en User-Agent.
    
    Retorna:
        - 'Mobile': Si es acceso desde dispositivo móvil
        - 'Web': Si es acceso desde navegador web (desktop)
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    
    palabras_mobile = [
        'mobile', 'android', 'iphone', 'ipad', 
        'windows phone', 'blackberry', 'opera mini',
        'webos', 'ipod', 'tablet'
    ]
    
    for palabra in palabras_mobile:
        if palabra in user_agent:
            return 'Mobile'
    
    return 'Web'


def obtener_ip_cliente(request):
    """
    Obtiene la dirección IP real del cliente.
    Considera proxies y load balancers.
    
    Retorna:
        str: Dirección IP del cliente o 'Desconocida' si no se puede determinar
    """
    # Intentar obtener IP de X-Forwarded-For (proxies/load balancers)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Tomar la primera IP de la cadena
        ip = x_forwarded_for.split(',')[0].strip()
        return ip
    
    # Intentar obtener IP de X-Real-IP (algunos proxies/nginx)
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()
    
    # Última opción: REMOTE_ADDR
    ip = request.META.get('REMOTE_ADDR', 'Desconocida')
    return ip


def obtener_user_agent(request, max_length=500):
    """
    Obtiene el User-Agent del cliente.
    
    Args:
        request: HttpRequest object
        max_length: Máxima longitud del User-Agent
    
    Retorna:
        str: User-Agent truncado
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    return user_agent[:max_length]


def registrar_bitacora(
    usuario,
    accion,
    modulo_afectado,
    descripcion,
    request=None,
    detalles=None
):
    """
    Crea un registro en la bitácora del sistema.
    
    Args:
        usuario (Usuario): Usuario que realiza la acción
        accion (str): CREATE, UPDATE, DELETE, LOGIN, LOGOUT
        modulo_afectado (str): Nombre del módulo/recurso afectado
        descripcion (str): Descripción legible de la acción
        request (HttpRequest, optional): Request object para obtener IP, dispositivo, etc.
        detalles (dict, optional): Detalles adicionales de la acción
    
    Retorna:
        Bitacora: Instancia del registro creado
    """
    from .models import Bitacora
    
    if detalles is None:
        detalles = {}
    
    # Extraer información del request si está disponible
    if request:
        direccion_ip = obtener_ip_cliente(request)
        dispositivo = detectar_dispositivo(request)
        user_agent = obtener_user_agent(request)
    else:
        direccion_ip = 'Desconocida'
        dispositivo = 'Web'
        user_agent = ''
    
    bitacora = Bitacora.objects.create(
        usuario=usuario,
        usuario_nombre=usuario.nombre if usuario else 'Sistema',
        accion=accion,
        modulo_afectado=modulo_afectado,
        descripcion=descripcion,
        detalles=detalles,
        direccion_ip=direccion_ip,
        dispositivo=dispositivo,
        user_agent=user_agent
    )
    
    return bitacora

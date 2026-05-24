import subprocess
import os
import tempfile
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from seguridad.models import Bitacora , registrar_bitacora


def registrar_bitacora(request, accion, descripcion, estado='EXITO'):
    try:
        usuario_rol = 'Sin rol'
        try:
            usuario_rol = request.user.nombre_rol
        except Exception:
            pass
        registrar_bitacora(
            request,
            accion=accion,
            modulo='Backup',
            descripcion=descripcion,
        )   
    except Exception:
        pass


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def descargar_backup(request):
    if not request.user.is_superuser and not request.user.tiene_permiso('backup.crear'):
        return Response({'error': 'No tienes permiso para realizar backups'}, status=403)

    db_url = settings.DATABASE_URL
    if not db_url:
        return Response({'error': 'DATABASE_URL no configurada'}, status=500)

    nombre = f"backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.sql"
    tmp_path = os.path.join(tempfile.gettempdir(), nombre)

    resultado = subprocess.run([
        'pg_dump',
        '--dbname', db_url,
        '-F', 'p',
        '--schema=public',
        '--no-owner',
        '--no-privileges',
        '-f', tmp_path,
    ], capture_output=True, text=True)

    if resultado.returncode != 0:
        registrar_bitacora(request, 'CREAR', f'Error al crear backup: {resultado.stderr}', 'ERROR')
        return Response({'error': resultado.stderr}, status=500)

    tamanio = os.path.getsize(tmp_path)
    registrar_bitacora(request, 'CREAR', f'Backup descargado: {nombre} ({tamanio} bytes)')

    response = FileResponse(
        open(tmp_path, 'rb'),
        content_type='application/octet-stream'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restaurar_backup(request):
    if not request.user.is_superuser and not request.user.tiene_permiso('backup.restaurar'):
        return Response({'error': 'No tienes permiso para restaurar backups'}, status=403)

    archivo = request.FILES.get('archivo')
    if not archivo:
        return Response({'error': 'Debes subir un archivo .sql'}, status=400)

    if not archivo.name.endswith('.sql'):
        return Response({'error': 'El archivo debe tener extensión .sql'}, status=400)

    db_url = settings.DATABASE_URL
    if not db_url:
        return Response({'error': 'DATABASE_URL no configurada'}, status=500)

    tmp_path = os.path.join(tempfile.gettempdir(), archivo.name)
    with open(tmp_path, 'wb') as f:
        for chunk in archivo.chunks():
            f.write(chunk)

    resultado = subprocess.run([
        'psql',
        '--dbname', db_url,
        '-f', tmp_path,
        '-v', 'ON_ERROR_CONTINUE=on',
    ], capture_output=True, text=True)

    os.remove(tmp_path)

    errores_fatales = [
    line for line in resultado.stderr.split('\n')
    if 'error' in line.lower() 
    and 'event trigger' not in line.lower()
    and 'already exists' not in line.lower()
    and 'duplicate key' not in line.lower()
    and 'multiple primary keys' not in line.lower()
    and line.strip() != ''
]

    if errores_fatales:
        registrar_bitacora(request, 'EDITAR', f'Error al restaurar: {errores_fatales[0]}', 'ERROR')
        return Response({'error': errores_fatales[0]}, status=500)

    registrar_bitacora(request, 'EDITAR', f'Base de datos restaurada desde: {archivo.name}')
    return Response({'mensaje': f'Base de datos restaurada correctamente desde {archivo.name}'})
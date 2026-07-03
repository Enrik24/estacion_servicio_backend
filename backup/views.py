import subprocess
import os
import tempfile
import requests
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from seguridad.models import Bitacora, registrar_bitacora


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
        registrar_bitacora(request, accion='CREAR', descripcion=f'Error al crear backup: {resultado.stderr}', estado='ERROR', modulo='Backup')
        return Response({'error': resultado.stderr}, status=500)

    # Subir a Supabase Storage automáticamente
    try:
        with open(tmp_path, 'rb') as f:
            contenido = f.read()
        url = f"{settings.SUPABASE_URL}/storage/v1/object/backups/{nombre}"
        headers = {
            'Authorization': f'Bearer {settings.SUPABASE_SERVICE_KEY}',
            'Content-Type': 'application/octet-stream',
        }
        response = requests.post(url, headers=headers, data=contenido)
        if response.status_code in [200, 201]:
            print(f'✅ Backup subido a Supabase: {nombre}')
        else:
            print(f'⚠️ No se pudo subir a Supabase: {response.text}')
    except Exception as e:
        print(f'⚠️ Error subiendo a Supabase: {e}')

    tamanio = os.path.getsize(tmp_path)
    registrar_bitacora(request, accion='CREAR', descripcion=f'Backup generado y subido a Supabase: {nombre} ({tamanio} bytes)', modulo='Backup')

    response = FileResponse(
        open(tmp_path, 'rb'),
        content_type='application/octet-stream'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_backups(request):
    """Lista los backups disponibles en Supabase Storage."""
    if not request.user.is_superuser and not request.user.tiene_permiso('backup.crear'):
        return Response({'error': 'Sin permiso'}, status=403)

    url = f"{settings.SUPABASE_URL}/storage/v1/object/list/backups"
    headers = {
        'Authorization': f'Bearer {settings.SUPABASE_SERVICE_KEY}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(url, headers=headers, json={
            'limit': 50,
            'offset': 0,
            'prefix': '',
            'sortBy': {'column': 'created_at', 'order': 'desc'}
        })
        print(f'Status: {response.status_code}')
        print(f'Response: {response.text}')
        if response.status_code != 200:
            return Response({'error': 'Error al listar backups'}, status=500)

        archivos = response.json()
        data = [{
            'nombre': a['name'],
            'tamanio': a.get('metadata', {}).get('size', 0),
            'fecha': a.get('created_at', ''),
        } for a in archivos if a.get('name')]

        return Response(data)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def descargar_backup_supabase(request, nombre):
    """Descarga un backup específico desde Supabase Storage."""
    if not request.user.is_superuser and not request.user.tiene_permiso('backup.crear'):
        return Response({'error': 'Sin permiso'}, status=403)

    url = f"{settings.SUPABASE_URL}/storage/v1/object/backups/{nombre}"
    headers = {
        'Authorization': f'Bearer {settings.SUPABASE_SERVICE_KEY}',
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return Response({'error': 'Backup no encontrado'}, status=404)

        tmp_path = os.path.join(tempfile.gettempdir(), nombre)
        with open(tmp_path, 'wb') as f:
            f.write(response.content)

        registrar_bitacora(request, accion='CONSULTAR', descripcion=f'Descargó backup: {nombre}', modulo='Backup')

        return FileResponse(
            open(tmp_path, 'rb'),
            content_type='application/octet-stream',
            as_attachment=True,
            filename=nombre
        )
    except Exception as e:
        return Response({'error': str(e)}, status=500)


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
        and 'ya existe' not in line.lower()
        and 'llave duplicada' not in line.lower()
        and 'no se permiten' not in line.lower()
        and line.strip() != ''
    ]   
    if errores_fatales:
        registrar_bitacora(request, accion='EDITAR', descripcion=f'Error al restaurar: {errores_fatales[0]}', estado='ERROR', modulo='Backup')
        return Response({'error': errores_fatales[0]}, status=500)

    registrar_bitacora(request, accion='EDITAR', descripcion=f'Base de datos restaurada desde: {archivo.name}', modulo='Backup')
    return Response({'mensaje': f'Base de datos restaurada correctamente desde {archivo.name}'})
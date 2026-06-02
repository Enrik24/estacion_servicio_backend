import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from django.conf import settings
import requests


def backup_automatico():
    """Genera backup automático y lo sube a Supabase Storage."""
    try:
        db_url = settings.DATABASE_URL
        if not db_url:
            print('ERROR: DATABASE_URL no configurada')
            return

        # Generar nombre del archivo
        nombre = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        tmp_path = os.path.join(tempfile.gettempdir(), nombre)

        # Generar backup con pg_dump
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
            print(f'ERROR generando backup: {resultado.stderr}')
            return

        # Subir a Supabase Storage
        with open(tmp_path, 'rb') as f:
            contenido = f.read()

        url = f"{settings.SUPABASE_URL}/storage/v1/object/backups/{nombre}"
        headers = {
            'Authorization': f'Bearer {settings.SUPABASE_SERVICE_KEY}',
            'Content-Type': 'application/octet-stream',
        }

        response = requests.post(url, headers=headers, data=contenido)

        if response.status_code in [200, 201]:
            print(f'✅ Backup subido correctamente: {nombre}')
        else:
            print(f'ERROR subiendo backup: {response.status_code} - {response.text}')

        # Eliminar archivo temporal
        os.remove(tmp_path)

        # Eliminar backups de más de 7 días
        eliminar_backups_antiguos()

    except Exception as e:
        print(f'ERROR en backup_automatico: {e}')


def eliminar_backups_antiguos():
    """Elimina backups de más de 7 días en Supabase Storage."""
    try:
        url = f"{settings.SUPABASE_URL}/storage/v1/object/list/backups"
        headers = {
            'Authorization': f'Bearer {settings.SUPABASE_SERVICE_KEY}',
            'Content-Type': 'application/json',
        }

        response = requests.post(url, headers=headers, json={
            'limit': 100,
            'offset': 0,
        })

        if response.status_code != 200:
            return

        archivos = response.json()
        hace_7_dias = datetime.now() - timedelta(days=7)

        for archivo in archivos:
            fecha_str = archivo.get('created_at', '')
            if fecha_str:
                fecha = datetime.fromisoformat(fecha_str.replace('Z', '+00:00')).replace(tzinfo=None)
                if fecha < hace_7_dias:
                    nombre = archivo['name']
                    delete_url = f"{settings.SUPABASE_URL}/storage/v1/object/backups/{nombre}"
                    requests.delete(delete_url, headers=headers)
                    print(f'🗑️ Backup eliminado: {nombre}')

    except Exception as e:
        print(f'ERROR eliminando backups antiguos: {e}')
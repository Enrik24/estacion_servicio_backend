# Estacion Servicio Backend

Backend del sistema de estacion de servicio construido con Django, Django REST Framework y PostgreSQL.

## Requisitos
- Python 3.13
- PostgreSQL 14 o superior
- PowerShell en Windows

## Instalacion
1. Abre una terminal en la carpeta del proyecto:

```powershell
cd "D:\si2\3er sprint\estacion_servicio_backend-CU01_DE_CU06\estacion_servicio_backend-CU01_DE_CU06"
```

2. Crea y activa el entorno virtual:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instala dependencias:

```powershell
pip install -r requirements.txt
```

## Configuracion Del Archivo .env
Este proyecto lee variables de entorno con `python-decouple`. El archivo debe llamarse `.env` y debe vivir en la raiz del backend, al mismo nivel que `manage.py`.

1. Crea el archivo `.env`.
2. Copia este ejemplo base y ajusta los valores reales:

```env
DEBUG=True
SECRET_KEY=tu-clave-secreta-aqui-cambia-por-una-segura-de-50-caracteres
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

USE_SQLITE=False
DB_NAME=db_gasolinera_v2
DB_USER=postgres
DB_PASSWORD=12345
DB_HOST=127.0.0.1
DB_PORT=5432
DATABASE_URL=postgresql://postgres:12345@127.0.0.1:5432/db_gasolinera_v2

JWT_ACCESS_TOKEN_LIFETIME_MINUTES=60
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174
CORS_ALLOW_ALL_ORIGINS=False

TIME_ZONE=America/La_Paz
LANGUAGE_CODE=es-bo

EMAIL_USER=tu-email@gmail.com
EMAIL_PASS=tu-password-de-aplicacion
FRONTEND_URL=http://localhost:5173
GROQ_API_KEY=tu-api-key-de-groq
```

## Variables De Entorno
- `DEBUG`: activa o desactiva modo desarrollo.
- `SECRET_KEY`: clave secreta de Django.
- `ALLOWED_HOSTS`: hosts permitidos por Django separados por coma.
- `USE_SQLITE`: usa SQLite si vale `True`; para PostgreSQL debe ser `False`.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: conexion principal a PostgreSQL.
- `DATABASE_URL`: cadena de conexion equivalente, util para despliegues.
- `JWT_ACCESS_TOKEN_LIFETIME_MINUTES`: duracion del token de acceso.
- `JWT_REFRESH_TOKEN_LIFETIME_DAYS`: duracion del refresh token.
- `CORS_ALLOWED_ORIGINS`: URLs del frontend autorizadas.
- `CORS_ALLOW_ALL_ORIGINS`: habilita CORS global si vale `True`.
- `TIME_ZONE`: zona horaria del proyecto.
- `LANGUAGE_CODE`: idioma por defecto.
- `EMAIL_USER`: correo remitente usado para SMTP.
- `EMAIL_PASS`: clave o password de aplicacion del correo.
- `FRONTEND_URL`: URL base del frontend para enlaces de verificacion.
- `GROQ_API_KEY`: clave usada por integraciones IA del proyecto.

## Base De Datos
1. Crea la base de datos `db_gasolinera_v2` en PostgreSQL.
2. Verifica que el usuario y password del `.env` coincidan con tu instalacion local.
3. Ejecuta migraciones:

```powershell
py -3.13 manage.py migrate
```

4. Si necesitas cargar datos iniciales:

```powershell
py -3.13 manage.py seed
```

## Ejecucion Local
Levanta el backend escuchando tambien para emulador Android:

```powershell
py -3.13 manage.py runserver 0.0.0.0:8000
```

La API queda disponible en:
- `http://127.0.0.1:8000/api`
- `http://10.0.2.2:8000/api` desde emulador Android

## Comandos Utiles
- Ejecutar pruebas:

```powershell
py -3.13 manage.py test
```

- Ejecutar pruebas de apps puntuales:

```powershell
py -3.13 manage.py test usuarios ventas
```

- Crear migraciones:

```powershell
py -3.13 manage.py makemigrations
```

## Solucion De Problemas
- Error con `.venv\Scripts\Activate.ps1`: verifica haber creado el entorno virtual y ejecutar PowerShell con permisos para scripts.
- Error de CORS: revisa `CORS_ALLOWED_ORIGINS` y que el frontend use el puerto correcto.
- El movil no conecta: confirma que el backend este corriendo con `0.0.0.0:8000`.
- Error de PostgreSQL: revisa `USE_SQLITE=False`, credenciales y que PostgreSQL este iniciado.

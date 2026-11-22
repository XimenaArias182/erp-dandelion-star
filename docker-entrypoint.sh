#!/bin/sh
set -e

echo "==> [entrypoint] Ejecutando migraciones de base de datos..."
python manage.py migrate --noinput

echo "==> [entrypoint] Iniciando Gunicorn en puerto ${PORT:-8000}..."
exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-1} \
    --threads 4 \
    --timeout 120 \
    --log-file - \
    --access-logfile -
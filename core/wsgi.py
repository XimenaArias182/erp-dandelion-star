"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()


def _auto_migrate_productos():
    try:
        from django.core.management import call_command
        call_command('migrate', 'productos', interactive=False, verbosity=0)
    except Exception:
        pass

_auto_migrate_productos()


def _auto_migrate_all():
    try:
        from django.db import connection
        from django.core.management import call_command
        connection.close()
        call_command('migrate', interactive=False, verbosity=0)
        connection.close()
    except Exception:
        pass

_auto_migrate_all()

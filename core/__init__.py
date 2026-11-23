"""Inicialización del paquete core del proyecto ERP Django — W16."""
from .celery import app as celery_app

__all__ = ('celery_app',)

# clickygo_project/__init__.py

# Esto asegura que la app de Celery se cargue cuando arranca Django,
# para que @shared_task la encuentre.
from .celery import app as celery_app

__all__ = ("celery_app",)

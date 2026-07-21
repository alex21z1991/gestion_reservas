# clickygo_project/celery.py

import os

from celery import Celery

# Le indica a Celery dónde está la configuración de Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "clickygo_project.settings")

app = Celery("clickygo_project")

# Lee toda la configuración que empieza con CELERY_ desde settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Busca automáticamente un archivo tasks.py dentro de cada app instalada
# (encontrará app_reservas/tasks.py sin que haya que registrarlo a mano)
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Tarea de prueba para verificar que el worker está vivo."""
    print(f"Request: {self.request!r}")

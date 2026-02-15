import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_playground.settings")

app = Celery("celery_playground")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_playground.settings")

app = Celery("celery_playground")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.update(
    task_acks_late=True,              # Golden Rule #2
    task_reject_on_worker_lost=True,  # Re-queue on SIGKILL
    worker_prefetch_multiplier=1,     # Golden Rule #3
)

# autodiscover finds demo/tasks.py
app.autodiscover_tasks(["demo"])

# Explicitly register per-module task files (not named tasks.py)
# (no additional task modules on this branch yet)

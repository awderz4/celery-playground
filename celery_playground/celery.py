import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_playground.settings")

app = Celery("celery_playground")

# Load configuration from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Production-critical default: prefetch_multiplier=1
# This prevents invisible task starvation (Golden Rule #3)
app.conf.update(
    task_acks_late=True,  # Golden Rule #2: ACK only after successful execution
    task_reject_on_worker_lost=True,  # Re-queue on SIGKILL
    worker_prefetch_multiplier=1,  # Golden Rule #3: No pre-fetching
)

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

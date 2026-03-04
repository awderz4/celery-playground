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

# Auto-discover tasks in all installed apps.
# autodiscover_tasks() only finds files literally named "tasks.py".
# We pass related_name patterns so every tasks_module_NN.py is also loaded.
app.autodiscover_tasks(
    packages=[
        "demo",
        "production_patterns",
    ],
    related_name="tasks",          # finds demo/tasks.py
)

# Force-import every additional task module so the worker registers them.
# These files are named tasks_module_NN.py — not picked up by autodiscover.
from demo import (  # noqa: F401, E402
    tasks_module_02,
    tasks_module_03,
    tasks_module_04,
    tasks_module_05,
    tasks_module_06,
    tasks_module_07,
    tasks_module_08,
    tasks_module_11,
)

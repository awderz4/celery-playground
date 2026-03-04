"""
demo/tasks_module_07.py
=======================
Module 7 — Scheduling & django-celery-beat

Demonstrates:
  - Periodic task registered via CELERY_BEAT_SCHEDULE
  - Dynamic schedule management (create/update/disable via ORM)
  - One-time future task (ClockedSchedule)
  - Beat duplicate execution prevention (single instance rule)
"""

import json
import socket
import time

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(acks_late=True, name="demo.heartbeat_task")
def heartbeat_task():
    """
    Scheduled every 30s via django-celery-beat.

    Beat only ENQUEUES this task — the worker executes it.
    Beat downtime = missed runs. Beat NEVER back-fills.

    Register with:
        from django_celery_beat.models import PeriodicTask, IntervalSchedule
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=30, period=IntervalSchedule.SECONDS
        )
        PeriodicTask.objects.get_or_create(
            name='heartbeat',
            defaults={
                'interval': schedule,
                'task': 'demo.heartbeat_task',
            }
        )
    """
    ts = time.time()
    worker = socket.gethostname()
    logger.info("[heartbeat] worker=%s ts=%.2f", worker, ts)
    return {"alive": True, "worker": worker, "ts": ts}


@shared_task(acks_late=True, soft_time_limit=300, time_limit=360,
             name="demo.daily_report_task")
def daily_report_task(user_id: int):
    """
    Lab 7c — scheduled via CrontabSchedule, one per user.

    Create/update programmatically:
        from demo.tasks_module_07 import schedule_user_report
        schedule_user_report(user_id=42, hour=8)
    """
    logger.info("[daily_report] user_id=%d", user_id)
    time.sleep(0.1)
    return {"user_id": user_id, "report": "generated", "ts": time.time()}


@shared_task(acks_late=True, name="demo.canary_heartbeat")
def canary_heartbeat():
    """
    Canary task — submit every 60s, alert if not completed in 120s.

    If this task stops succeeding → workers are stuck or queue is backed up.

    Prometheus alert rule:
        time() - celery_task_succeeded_timestamp{task='demo.canary_heartbeat'} > 120
    """
    return {"alive": True, "worker": socket.gethostname(), "ts": time.time()}


def schedule_user_report(user_id: int, hour: int = 8):
    """
    Programmatically create/update a per-user daily report schedule.

    Called from a Django view when a user enables daily reports.
    No Beat restart required — DatabaseScheduler polls DB every 30s.
    """
    from django_celery_beat.models import PeriodicTask, CrontabSchedule

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour=str(hour),
        day_of_week="*", day_of_month="*", month_of_year="*",
        timezone="UTC",
    )
    task, created = PeriodicTask.objects.update_or_create(
        name=f"daily-report-user-{user_id}",
        defaults={
            "crontab": schedule,
            "task": "demo.daily_report_task",
            "kwargs": json.dumps({"user_id": user_id}),
            "enabled": True,
        },
    )
    logger.info(
        "%s daily report for user %d at %02d:00 UTC",
        "Created" if created else "Updated", user_id, hour,
    )
    return task


def disable_user_report(user_id: int):
    """Disable a user's daily report schedule without deleting it."""
    from django_celery_beat.models import PeriodicTask

    updated = PeriodicTask.objects.filter(
        name=f"daily-report-user-{user_id}"
    ).update(enabled=False)
    logger.info("Disabled daily report for user %d (updated=%d)", user_id, updated)
    return updated


def pause_all_scheduled_tasks():
    """Emergency: disable ALL periodic tasks immediately."""
    from django_celery_beat.models import PeriodicTask

    count = PeriodicTask.objects.all().update(enabled=False)
    logger.warning("EMERGENCY: paused %d scheduled tasks", count)
    return count


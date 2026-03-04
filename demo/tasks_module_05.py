"""
demo/tasks_module_05.py
=======================
Module 5 — Queue Architecture & Isolation

Demonstrates:
  - Tasks explicitly routed to named queues
  - Critical queue tasks (payment, auth)
  - Notification queue tasks (email, SMS, push)
  - Media queue tasks (image resize, video transcode)
  - Import queue tasks (CSV import, bulk operations)
  - Queue starvation anti-pattern demonstration
"""

import os
import time

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 5.1 ─ CRITICAL queue tasks — SLA < 1s enqueue, dedicated workers
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    queue="critical",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=30,
    time_limit=45,
    name="demo.charge_payment",
)
def charge_payment(order_id: str, amount: float):
    """
    Critical queue — dedicated worker, never shares with slow tasks.

    Payment tasks MUST have their own queue and worker pool.
    If mixed with media tasks (5-min encode), a single encode
    blocks every payment for 5 minutes.

    Worker command:
        uv run celery -A celery_playground worker \\
            -Q critical --concurrency=4 --prefetch-multiplier=1 \\
            --hostname=worker-critical@%h -l info
    """
    logger.info("[charge_payment] order=%s amount=%.2f pid=%d", order_id, amount, os.getpid())
    time.sleep(0.1)  # simulate payment gateway call
    return {"order_id": order_id, "amount": amount, "status": "charged"}


@shared_task(
    queue="critical",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=10,
    time_limit=20,
    name="demo.revoke_auth_token",
)
def revoke_auth_token(user_id: int, token: str):
    """Critical queue — security operations must never be starved."""
    logger.info("[revoke_auth_token] user=%d pid=%d", user_id, os.getpid())
    time.sleep(0.05)
    return {"user_id": user_id, "token_revoked": True}


# ─────────────────────────────────────────────────────────────────────────────
# 5.2 ─ NOTIFICATIONS queue — gevent pool, high concurrency
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    queue="notifications",
    acks_late=True,
    rate_limit="500/m",
    soft_time_limit=30,
    time_limit=45,
    name="demo.send_email_notification",
)
def send_email_notification(to_address: str, subject: str, body: str = ""):
    """
    Notifications queue — run with gevent pool for I/O-bound efficiency.

    Worker command:
        uv run celery -A celery_playground worker \\
            -Q notifications --concurrency=100 --pool=gevent \\
            --prefetch-multiplier=1 --hostname=worker-notifications@%h -l info
    """
    logger.info("[send_email] to=%s subject=%s pid=%d", to_address, subject, os.getpid())
    time.sleep(0.05)  # simulate SMTP call
    return {"to": to_address, "status": "sent"}


@shared_task(
    queue="notifications",
    acks_late=True,
    rate_limit="200/m",
    soft_time_limit=20,
    time_limit=30,
    name="demo.send_push_notification",
)
def send_push_notification(device_token: str, title: str, body: str = ""):
    """Notifications queue — push notifications via gevent pool."""
    logger.info("[push_notification] device=%s title=%s", device_token[:8], title)
    time.sleep(0.05)
    return {"device": device_token[:8], "status": "pushed"}


# ─────────────────────────────────────────────────────────────────────────────
# 5.3 ─ MEDIA queue — CPU-heavy, low concurrency, high memory
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    queue="media",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=600,
    time_limit=660,
    name="demo.resize_image",
)
def resize_image(image_id: int, width: int, height: int):
    """
    Media queue — CPU-bound, slow. MUST NOT share with notifications queue.

    Anti-pattern (DON'T DO THIS):
        celery worker -Q default,notifications,media  ← starvation!

    This 5-minute encode will block 50 pending email tasks.

    Worker command:
        uv run celery -A celery_playground worker \\
            -Q media --concurrency=2 --pool=prefork \\
            --max-tasks-per-child=50 --max-memory-per-child=800000 \\
            --prefetch-multiplier=1 --hostname=worker-media@%h -l info
    """
    logger.info("[resize_image] id=%d size=%dx%d pid=%d", image_id, width, height, os.getpid())
    time.sleep(0.3)  # simulate image processing
    return {"image_id": image_id, "width": width, "height": height, "status": "resized"}


@shared_task(
    queue="media",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=1800,
    time_limit=1860,
    name="demo.transcode_video",
)
def transcode_video(video_id: int, format: str = "mp4"):
    """Media queue — long-running video transcode (up to 30 min)."""
    logger.info("[transcode_video] id=%d format=%s pid=%d", video_id, format, os.getpid())
    time.sleep(0.5)  # simulate transcode
    return {"video_id": video_id, "format": format, "status": "transcoded"}


# ─────────────────────────────────────────────────────────────────────────────
# 5.4 ─ IMPORTS queue — memory-heavy, single concurrency, long tasks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    queue="imports",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=1800,
    time_limit=2000,
    name="demo.import_csv",
)
def import_csv(file_id: int, user_id: int):
    """
    Imports queue — slow, memory-heavy. Concurrency=1 to avoid OOM.

    Worker command:
        uv run celery -A celery_playground worker \\
            -Q imports --concurrency=1 --pool=prefork \\
            --max-tasks-per-child=10 --max-memory-per-child=1000000 \\
            --prefetch-multiplier=1 -l info
    """
    logger.info("[import_csv] file=%d user=%d pid=%d", file_id, user_id, os.getpid())
    time.sleep(0.2)  # simulate CSV processing
    return {"file_id": file_id, "user_id": user_id, "rows_imported": 1000}


@shared_task(
    queue="imports",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=3600,
    time_limit=3660,
    name="demo.bulk_user_create",
)
def bulk_user_create(data: list):
    """Imports queue — bulk DB operations, single concurrency."""
    count = len(data)
    logger.info("[bulk_user_create] count=%d pid=%d", count, os.getpid())
    time.sleep(0.1)
    return {"created": count, "status": "done"}


# ─────────────────────────────────────────────────────────────────────────────
# 5.5 ─ Queue starvation demonstration task
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    acks_late=True,
    soft_time_limit=120,
    time_limit=150,
    name="demo.starvation_slow_task",
)
def starvation_slow_task(task_number: int, duration: int = 30):
    """
    Lab 5a — slow task used to starve fast tasks when on same worker.

    Submit 20 of these + 5 email tasks to a SINGLE mixed worker.
    Observe: emails take 20 × 30s = 10 minutes instead of 1s each.

    Then repeat with separate workers — emails finish in < 1s.
    """
    logger.info("[starvation_slow #%d] sleeping %ds pid=%d", task_number, duration, os.getpid())
    time.sleep(duration)
    return {"task_number": task_number, "duration": duration}


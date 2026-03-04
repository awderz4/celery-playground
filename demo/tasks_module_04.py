"""
demo/tasks_module_04.py
=======================
Module 4 — Backpressure, Rate Control & Dead Letters

Demonstrates:
  - Rate-limited tasks (10/m, 100/m)
  - ProductionTask base (auto dead-letter on exhausted retries)
  - Dead-letter observation task (always fails → goes to DLQ)
  - Circuit breaker usage in a producer view
  - Queue depth monitoring task
"""

import os
import time

from celery import shared_task
from celery.utils.log import get_task_logger

from production_patterns.tasks.base import ProductionTask

logger = get_task_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 4.1 ─ Rate-limited tasks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    rate_limit="10/m",
    acks_late=True,
    name="demo.send_sms",
)
def send_sms(phone_number: str, message: str):
    """
    Lab 4a — rate-limited to 10 executions per minute per worker.

    Rate limits are enforced by the worker (not the broker).
    If you submit 100 sms tasks, the worker will only process 10/min.

    Dynamic rate limit change (no restart needed):
        from celery import current_app
        current_app.control.rate_limit('demo.send_sms', '5/m')
    """
    logger.info("[send_sms] to=%s msg=%s pid=%d", phone_number, message[:20], os.getpid())
    time.sleep(0.1)  # simulate SMS API call
    return {"phone": phone_number, "status": "sent"}


@shared_task(
    rate_limit="100/m",
    acks_late=True,
    name="demo.send_bulk_email",
)
def send_bulk_email(to_address: str, subject: str, body: str = ""):
    """
    Lab 4a — higher rate limit for email (100/min vs SMS 10/min).

    Shows how different task types can have different rate limits
    matching the capacity of the downstream system.
    """
    logger.info("[send_bulk_email] to=%s subject=%s", to_address, subject[:30])
    time.sleep(0.05)
    return {"to": to_address, "status": "queued"}


# ─────────────────────────────────────────────────────────────────────────────
# 4.2 ─ ProductionTask base — auto dead-letter routing
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    base=ProductionTask,
    max_retries=2,
    name="demo.always_fails_task",
)
def always_fails_task(task_number: int = 0):
    """
    Lab 4b — task that always raises an exception.

    After max_retries=2 exhausted, ProductionTask.on_failure()
    automatically pushes the task metadata to:
      Redis key: celery:dead-letter  (LPUSH, capped at 10,000)

    Inspect the dead-letter queue:
        redis-cli -p 6380 LRANGE celery:dead-letter 0 -1

    Replay dead-letter tasks:
        uv run python scripts/replay_dead_letter.py
    """
    raise RuntimeError(
        f"Task #{task_number} always fails — intentional for dead-letter lab"
    )


@shared_task(
    base=ProductionTask,
    max_retries=3,
    soft_time_limit=60,
    time_limit=90,
    name="demo.payment_task",
)
def payment_task(order_id: str, amount: float):
    """
    Lab 4b — simulates a payment processing task using ProductionTask base.

    ProductionTask provides:
      - acks_late=True automatically
      - reject_on_worker_lost=True automatically
      - Dead-letter routing on exhausted retries
      - Structured failure logging

    This is the pattern to use for all business-critical tasks.
    """
    logger.info("[payment_task] order=%s amount=%.2f", order_id, amount)
    time.sleep(0.2)  # simulate payment gateway call
    return {"order_id": order_id, "amount": amount, "status": "charged"}


# ─────────────────────────────────────────────────────────────────────────────
# 4.3 ─ Queue depth monitoring
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    acks_late=True,
    name="demo.check_queue_depths",
)
def check_queue_depths():
    """
    Periodic task: sample queue depths and log a warning if above thresholds.

    In production: use Prometheus celery_queue_length metric + Grafana alert.
    This task is a simple alternative for environments without Prometheus.

    Schedule via django-celery-beat every 60 seconds.
    """
    from production_patterns.utils.circuit_breaker import get_all_queue_depths

    queues = ["celery", "critical", "notifications", "default", "media", "imports"]
    thresholds = {
        "celery": 100,
        "critical": 10,
        "notifications": 200,
        "default": 100,
        "media": 20,
        "imports": 10,
    }

    try:
        depths = get_all_queue_depths(queues)
        alerts = []
        for queue, depth in depths.items():
            limit = thresholds.get(queue, 100)
            if depth > limit:
                logger.warning(
                    "QUEUE ALERT: '%s' depth=%d > threshold=%d", queue, depth, limit
                )
                alerts.append({"queue": queue, "depth": depth, "threshold": limit})
            else:
                logger.info("Queue '%s': depth=%d (OK)", queue, depth)

        return {"depths": depths, "alerts": alerts}
    except Exception as exc:
        logger.error("Failed to check queue depths: %s", exc)
        return {"error": str(exc)}


"""
production_patterns/tasks/base.py
==================================
Module 4 — Backpressure & Dead Letters

ProductionTask base class:
  - acks_late=True, reject_on_worker_lost=True (Golden Rules #2)
  - Dead-letter routing after max retries exhausted
  - Structured failure logging

Usage:
    @app.task(base=ProductionTask)
    def process_payment(order_id: int):
        pass
"""

import json
import logging
from datetime import datetime, timezone

import redis
from celery import Task
from django.conf import settings

logger = logging.getLogger(__name__)

DEAD_LETTER_KEY = "celery:dead-letter"
DEAD_LETTER_MAX_SIZE = 10_000


class ProductionTask(Task):
    """
    Base task class that enforces all production reliability settings
    and routes exhausted tasks to a Redis dead-letter list.

    Inherit from this or use base=ProductionTask on individual tasks.
    All settings here can be overridden per-task.
    """
    abstract = True

    # Golden Rule #2 — reliability
    acks_late = True
    reject_on_worker_lost = True

    # Golden Rule #6 — time limits (override per task category)
    soft_time_limit = 300   # 5 min
    time_limit = 360        # 6 min

    # Retry defaults
    max_retries = 3

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Route to dead-letter after all retries are exhausted."""
        if self.request.retries >= self.max_retries:
            self._route_to_dead_letter(task_id, exc, args, kwargs, self.request.retries)
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def _route_to_dead_letter(self, task_id: str, exc: Exception, args, kwargs, retry_count: int = 0):
        """Push failed task metadata to a Redis dead-letter list."""
        try:
            r = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
            payload = {
                "task_id": task_id,
                "task_name": self.name,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "args": list(args) if args else [],
                "kwargs": kwargs or {},
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": retry_count,
            }
            r.lpush(DEAD_LETTER_KEY, json.dumps(payload))
            r.ltrim(DEAD_LETTER_KEY, 0, DEAD_LETTER_MAX_SIZE - 1)
            logger.error(
                "Task %s (%s) moved to dead-letter after %d retries: %s",
                task_id, self.name, retry_count, exc,
            )
        except Exception as redis_exc:
            logger.critical(
                "Failed to route task %s to dead-letter: %s", task_id, redis_exc
            )


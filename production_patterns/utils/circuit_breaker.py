"""
production_patterns/utils/circuit_breaker.py
=============================================
Module 4 — Backpressure & Dead Letters

Circuit breaker pattern for task producers.
Checks queue depth before enqueuing and either:
  - Drops the task (queue > hard limit)
  - Enqueues with expiry (queue > soft limit)
  - Enqueues normally (queue within bounds)
"""

import json
import logging
from datetime import datetime

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


class QueueFullError(Exception):
    """Raised when a queue has exceeded its hard limit."""
    pass


def get_redis_client():
    return redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def get_queue_depth(queue_name: str) -> int:
    """Return the number of tasks currently waiting in a named queue."""
    r = get_redis_client()
    return r.llen(queue_name)


def safe_enqueue(task_func, *args, queue: str = "celery", **kwargs):
    """
    Enqueue a task with circuit-breaker backpressure protection.

    Thresholds (tune per queue in production):
      depth > 5000 → REJECT: queue is at capacity, raise QueueFullError
      depth > 1000 → WARN:   enqueue with expires=300 (drop if not processed in 5min)
      depth <= 1000 → OK:    enqueue normally

    Usage:
        from production_patterns.utils.circuit_breaker import safe_enqueue
        safe_enqueue(send_email, user_id=42, queue='notifications')
    """
    depth = get_queue_depth(queue)

    if depth > 5000:
        logger.error(
            "Queue '%s' is at capacity (depth=%d > 5000). Dropping task %s.",
            queue, depth, task_func.name,
        )
        raise QueueFullError(
            f"Queue '{queue}' is full (depth={depth}). Task {task_func.name} dropped."
        )

    if depth > 1000:
        logger.warning(
            "Queue '%s' is under pressure (depth=%d). Enqueuing with 5min expiry.",
            queue, depth,
        )
        return task_func.apply_async(args=args, kwargs=kwargs, expires=300, queue=queue)

    return task_func.apply_async(args=args, kwargs=kwargs, queue=queue)


def get_all_queue_depths(queue_names: list) -> dict:
    """Return depth for all named queues in a single Redis round-trip."""
    r = get_redis_client()
    pipe = r.pipeline()
    for name in queue_names:
        pipe.llen(name)
    depths = pipe.execute()
    return dict(zip(queue_names, depths))


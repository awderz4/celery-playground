"""
demo/tasks.py
=============
Module 1 — Task Lifecycle & Internals

Demonstrates:
  - Basic task anatomy (Module 0 baseline preserved)
  - Serialization comparison (JSON / msgpack)
  - Result backend strategies (ignore vs store)
  - Task state transitions (PENDING → STARTED → SUCCESS/FAILURE)
  - Task metadata & request context
"""

import os
import time

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 0 ─ Baseline (kept from Module 0)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task
def slow_add(x, y):
    """Baseline task from Module 0 — intentionally slow so you can observe it."""
    logger.info("PID %s — starting slow_add(%s, %s)", os.getpid(), x, y)
    time.sleep(30)
    result = x + y
    logger.info("PID %s — slow_add result: %s", os.getpid(), result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 1.1 ─ Task State Transitions
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, track_started=True)
def task_with_states(self, duration: int = 5):
    """
    Lab 1.1 — observe state transitions in Flower.

    States you will see:
      PENDING  → task is in the queue, not yet picked up
      STARTED  → worker accepted the task (requires track_started=True)
      SUCCESS  → task returned normally
      FAILURE  → task raised an exception
    """
    logger.info(
        "Task %s — STARTED (state=%s, worker=%s)",
        self.request.id, "STARTED", self.request.hostname,
    )
    time.sleep(duration)
    logger.info("Task %s — finishing", self.request.id)
    return {
        "task_id": self.request.id,
        "worker": self.request.hostname,
        "duration": duration,
        "pid": os.getpid(),
    }


@shared_task(bind=True, track_started=True)
def task_that_fails(self):
    """
    Lab 1.1 — deliberately raises to produce FAILURE state.
    Check the traceback in Flower → Tasks → <this task id>.
    """
    logger.info("Task %s — about to fail intentionally", self.request.id)
    time.sleep(2)
    raise ValueError("Intentional failure — this is expected in Lab 1.1")


# ─────────────────────────────────────────────────────────────────────────────
# 1.2 ─ Serialization Comparison
# ─────────────────────────────────────────────────────────────────────────────

@shared_task
def json_payload_task(data: dict):
    """
    Lab 1.2 — receives a dict payload over the wire as JSON.

    The broker stores this as a UTF-8 JSON string that you can read with:
      redis-cli LRANGE celery 0 0
    You will see the full message envelope including the serialized payload.
    """
    logger.info("json_payload_task received %d keys", len(data))
    return {"received_keys": list(data.keys()), "count": len(data)}


@shared_task
def large_payload_task(size: int = 1000):
    """
    Lab 1.2 — generates a large payload to measure serialization overhead.

    Use this to compare how much Redis memory a result takes:
      redis-cli STRLEN celery-task-meta-<uuid>
    """
    payload = {f"key_{i}": f"value_{i}" * 10 for i in range(size)}
    return {"keys": size, "sample": payload["key_0"]}


# ─────────────────────────────────────────────────────────────────────────────
# 1.3 ─ Result Backend Strategies
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(ignore_result=True)
def fire_and_forget(message: str):
    """
    Lab 1.3 — result is NOT stored in Redis.

    After this runs:
      redis-cli KEYS celery-task-meta-*   → this task's key will NOT appear.

    Use when the caller never calls .get() — saves Redis memory & CPU.
    Golden Rule: CELERY_TASK_IGNORE_RESULT = True for fire-and-forget tasks.
    """
    logger.info("fire_and_forget: %s", message)
    time.sleep(1)
    # return value is discarded — Redis never stores it


@shared_task(ignore_result=False)
def store_result(value: int):
    """
    Lab 1.3 — result IS stored in Redis with a TTL.

    After this runs:
      redis-cli GET celery-task-meta-<uuid>       → JSON result
      redis-cli TTL celery-task-meta-<uuid>       → seconds until expiry

    The TTL comes from CELERY_RESULT_EXPIRES = 3600 (set in settings.py).
    Without a TTL, results accumulate forever — a common memory leak.
    """
    logger.info("store_result: computing %d", value)
    time.sleep(1)
    return {"input": value, "squared": value ** 2, "cubed": value ** 3}


# ─────────────────────────────────────────────────────────────────────────────
# 1.4 ─ Message Envelope Inspection
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True)
def inspect_request(self, echo: str = "hello"):
    """
    Lab 1.4 — exposes everything Celery puts in the task request context.

    The *request* object is what the broker message becomes once decoded.
    Every field here was transmitted over the wire inside the JSON envelope.
    """
    request = self.request
    info = {
        # Routing
        "task_id":     request.id,
        "task_name":   request.task,
        "hostname":    request.hostname,
        "queue":       request.delivery_info.get("routing_key", "unknown"),
        # Execution context
        "retries":     request.retries,
        "is_eager":    request.is_eager,
        "pid":         os.getpid(),
        # Payload echo
        "echo":        echo,
    }
    logger.info("inspect_request: %s", info)
    return info


# ─────────────────────────────────────────────────────────────────────────────
# 1.5 ─ Broker Transport Visibility (prefetch demo)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, acks_late=True)
def observable_task(self, task_number: int, duration: int = 10):
    """
    Lab 1.5 — used to visualise queue depth vs in-flight tasks in Flower.

    Submit 8 of these, then watch Flower's "Active" vs queue depth counters.
    With prefetch_multiplier=1 you will see:
      Active = 1 (or concurrency value)
      Queue  = 7 remaining tasks — all visible and monitorable

    With prefetch_multiplier=4 you would see:
      Active = 1, Pre-fetched = 3 (invisible!), Queue = 4
    """
    logger.info(
        "observable_task #%d started on worker %s (pid=%d)",
        task_number, self.request.hostname, os.getpid(),
    )
    time.sleep(duration)
    return {"task_number": task_number, "duration": duration}

"""
demo/tasks_module_02.py
=======================
Module 2 — Worker Internals & Concurrency

Demonstrates:
  - Prefetch multiplier impact (prefetch=4 vs prefetch=1)
  - Task acknowledgment modes (acks_early vs acks_late)
  - Slow task that holds a worker (used for starvation demo)
  - I/O-bound task suitable for gevent pool
  - Worker process identity (PID logging to verify recycling)
  - Autoscale-friendly tasks
"""

import os
import time
import socket

import requests
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 2.1 ─ Slow Task (prefetch starvation demo)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    name="demo.slow_task",
)
def slow_task(self, task_number: int, duration: int = 30):
    """
    Lab 2a — submit 8 of these, then SIGKILL the worker at T+15s.

    With prefetch=4 (BAD):
      Worker grabs tasks 1-4 into memory before executing task 1.
      Tasks 2-4 are INVISIBLE to Flower and other workers.
      SIGKILL at T+15 → tasks 2-4 are GONE (if acks_early).

    With prefetch=1 + acks_late=True (GOOD):
      Only task 1 is in-flight. Tasks 2-8 stay in Redis queue.
      SIGKILL → task 1 is re-queued (not ACK'd yet), tasks 2-8 untouched.

    Usage:
        uv run python scripts/submit_tasks.py slow_task 8
    """
    pid = os.getpid()
    worker = self.request.hostname
    logger.info(
        "[slow_task #%d] START — pid=%d worker=%s duration=%ds",
        task_number, pid, worker, duration,
    )
    time.sleep(duration)
    logger.info("[slow_task #%d] DONE — pid=%d", task_number, pid)
    return {
        "task_number": task_number,
        "duration": duration,
        "pid": pid,
        "worker": worker,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2.2 ─ acks_early vs acks_late comparison
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    acks_late=False,   # Default (dangerous) — ACK on receipt
    name="demo.acks_early_task",
)
def acks_early_task(self, task_number: int, duration: int = 20):
    """
    Lab 2b — demonstrates acks_early (default, dangerous) behaviour.

    The broker ACKs this task as soon as the worker RECEIVES it.
    If the worker crashes while executing → message is GONE.

    Kill the worker while this runs and the task disappears silently.
    Compare with acks_late_task to see the difference.
    """
    pid = os.getpid()
    logger.info(
        "[acks_early #%d] START — pid=%d (ACK already sent to broker!)",
        task_number, pid,
    )
    time.sleep(duration)
    logger.info("[acks_early #%d] DONE", task_number)
    return {"task_number": task_number, "acks_mode": "early", "pid": pid}


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    name="demo.acks_late_task",
)
def acks_late_task(self, task_number: int, duration: int = 20):
    """
    Lab 2b — demonstrates acks_late=True (safe) behaviour.

    The broker DOES NOT ACK until this function returns successfully.
    If the worker crashes → visibility_timeout expires → Redis re-queues.
    reject_on_worker_lost=True → immediate NACK on SIGKILL (no waiting).

    Kill the worker while this runs — task reappears in the queue.
    """
    pid = os.getpid()
    logger.info(
        "[acks_late #%d] START — pid=%d (ACK withheld until completion)",
        task_number, pid,
    )
    time.sleep(duration)
    logger.info("[acks_late #%d] DONE — sending ACK now", task_number)
    return {"task_number": task_number, "acks_mode": "late", "pid": pid}


# ─────────────────────────────────────────────────────────────────────────────
# 2.3 ─ I/O-bound task (gevent benchmark)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    acks_late=True,
    soft_time_limit=30,
    time_limit=45,
    name="demo.io_bound_task",
)
def io_bound_task(self, url: str = "http://httpbin.org/delay/1", task_number: int = 0):
    """
    Lab 2c — I/O-bound task: HTTP GET with 1s simulated server delay.

    PREFORK pool (default):
      Each concurrent task uses a separate OS process (~150MB RAM each).
      50 concurrent tasks = 50 × 150MB = 7.5GB RAM. Not viable.

    GEVENT pool:
      All tasks share ONE process using cooperative green threads.
      50 concurrent tasks = 1 × 150MB = 150MB RAM. Very viable.
      Green thread yields to event loop on every I/O call (requests.get).

    Run the benchmark to compare:
        uv run python benchmarks/concurrency_test.py

    Worker startup for gevent:
        uv run celery -A celery_playground worker -Q default \\
            --pool=gevent --concurrency=50 --prefetch-multiplier=1
    """
    pid = os.getpid()
    start = time.monotonic()
    logger.info("[io_bound #%d] START — pid=%d fetching %s", task_number, pid, url)
    try:
        resp = requests.get(url, timeout=15)
        elapsed = time.monotonic() - start
        logger.info(
            "[io_bound #%d] DONE — status=%d elapsed=%.2fs pid=%d",
            task_number, resp.status_code, elapsed, pid,
        )
        return {
            "task_number": task_number,
            "status_code": resp.status_code,
            "elapsed_s": round(elapsed, 3),
            "pid": pid,
        }
    except requests.RequestException as exc:
        elapsed = time.monotonic() - start
        logger.warning("[io_bound #%d] FAILED after %.2fs: %s", task_number, elapsed, exc)
        # Return gracefully for benchmark purposes — don't retry in bench mode
        return {
            "task_number": task_number,
            "status_code": 0,
            "elapsed_s": round(elapsed, 3),
            "pid": pid,
            "error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 2.4 ─ CPU-bound task (prefork benchmark)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    acks_late=True,
    soft_time_limit=60,
    time_limit=90,
    name="demo.cpu_bound_task",
)
def cpu_bound_task(self, iterations: int = 5_000_000, task_number: int = 0):
    """
    Lab 2c — CPU-bound task: pure Python computation.

    PREFORK pool (GOOD for CPU):
      Each worker process runs on a separate CPU core in parallel.
      4 workers × 4 cores = true parallelism.

    GEVENT pool (BAD for CPU):
      All green threads share ONE process and ONE core.
      GIL prevents true CPU parallelism — tasks queue up sequentially.
      CPU-bound code never yields to the event loop → no cooperative benefit.

    Run the benchmark to compare throughput:
        uv run python benchmarks/concurrency_test.py --mode cpu
    """
    pid = os.getpid()
    start = time.monotonic()
    logger.info("[cpu_bound #%d] START — pid=%d iterations=%d", task_number, pid, iterations)

    # Pure Python computation — stresses CPU, does NOT yield to I/O
    total = sum(i * i for i in range(iterations))

    elapsed = time.monotonic() - start
    logger.info("[cpu_bound #%d] DONE — elapsed=%.2fs pid=%d", task_number, elapsed, pid)
    return {
        "task_number": task_number,
        "iterations": iterations,
        "result": total % 1_000_000,  # mod to keep result small
        "elapsed_s": round(elapsed, 3),
        "pid": pid,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2.5 ─ Worker identity / recycling probe
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    acks_late=True,
    name="demo.worker_identity_task",
)
def worker_identity_task(self, task_number: int = 0):
    """
    Lab 2d — shows worker PID, hostname, and task count.

    Submit this task 20+ times to observe:
    - Same PIDs while max_tasks_per_child not reached
    - PID changes after max_tasks_per_child executions (worker recycled)

    Cross-reference with max_tasks_per_child setting in settings.py.
    """
    pid = os.getpid()
    hostname = socket.gethostname()
    worker = self.request.hostname
    retries = self.request.retries

    info = {
        "task_number": task_number,
        "pid": pid,
        "hostname": hostname,
        "worker": worker,
        "retries": retries,
    }
    logger.info("[worker_identity #%d] pid=%d worker=%s", task_number, pid, worker)
    return info


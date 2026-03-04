"""
demo/tasks_module_06.py
=======================
Module 6 — Memory Management & Performance

Demonstrates:
  - Memory leak via module-level list accumulation
  - max_tasks_per_child: process recycles, RSS resets
  - max_memory_per_child: hard guard against runaway memory
  - Memory profiling with tracemalloc + resource module
"""

import os
import resource
import tracemalloc

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# THE BUG: module-level list grows with every task execution.
# Without max_tasks_per_child, grows until OOMKill.
# With max_tasks_per_child=50, process recycles and RSS resets.
_LEAKY_ACCUMULATOR = []


@shared_task(bind=True, acks_late=True, name="demo.leaky_task")
def leaky_task(self, task_number: int, payload_size: int = 1000):
    """
    Lab 6a — module-level state accumulates across task executions.

    Fix: CELERYD_MAX_TASKS_PER_CHILD = 50
    Monitor: watch -n1 'ps aux | grep celery | grep -v grep'
    """
    pid = os.getpid()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    _LEAKY_ACCUMULATOR.extend(f"task_{task_number}_item_{i}" for i in range(payload_size))
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    logger.info(
        "[leaky_task #%d] pid=%d rss=%dKB accumulator_len=%d",
        task_number, pid, rss_after, len(_LEAKY_ACCUMULATOR),
    )
    return {
        "task_number": task_number, "pid": pid,
        "rss_kb": rss_after, "accumulator_len": len(_LEAKY_ACCUMULATOR),
        "delta_kb": rss_after - rss_before,
    }


@shared_task(bind=True, acks_late=True, name="demo.clean_task")
def clean_task(self, task_number: int, payload_size: int = 1000):
    """Lab 6a — local variables only; RSS stays flat."""
    pid = os.getpid()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    data = [f"task_{task_number}_item_{i}" for i in range(payload_size)]
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "task_number": task_number, "pid": pid,
        "rss_kb": rss_after, "delta_kb": rss_after - rss_before,
        "processed": len(data),
    }


@shared_task(bind=True, acks_late=True, soft_time_limit=120, time_limit=150,
             name="demo.profiled_task")
def profiled_task(self, payload_size: int = 5000):
    """Lab 6b — production memory profiling with tracemalloc."""
    tracemalloc.start()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    pid = os.getpid()
    data = {f"key_{i}": f"value_{i}" * 100 for i in range(payload_size)}
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")[:5]
    tracemalloc.stop()
    logger.info(
        "[profiled_task] pid=%d rss_delta=%dKB\nTop allocators:\n%s",
        pid, rss_after - rss_before,
        "\n".join(str(s) for s in top_stats),
    )
    return {
        "pid": pid, "rss_before_kb": rss_before, "rss_after_kb": rss_after,
        "delta_kb": rss_after - rss_before, "payload_size": payload_size,
        "top_allocator": str(top_stats[0]) if top_stats else "none",
    }


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True,
             soft_time_limit=60, time_limit=90, name="demo.memory_spike_task")
def memory_spike_task(self, spike_mb: int = 100):
    """
    Lab 6c — allocates large block to trigger max_memory_per_child.

    Set CELERYD_MAX_MEMORY_PER_CHILD below spike_mb, submit this task.
    Worker recycles AFTER task completes (task already ACK'd with acks_late).
    """
    pid = os.getpid()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    big_block = bytearray(spike_mb * 1024 * 1024)
    big_block[0] = 1  # force OS page allocation
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    logger.info("[memory_spike] pid=%d delta=%dKB", pid, rss_after - rss_before)
    return {
        "pid": pid, "spike_mb": spike_mb,
        "rss_before_kb": rss_before, "rss_after_kb": rss_after,
        "delta_kb": rss_after - rss_before,
    }


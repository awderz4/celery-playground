"""
production_patterns/utils/distributed_lock.py
===============================================
Module 11 — Advanced Patterns

Redis-based distributed lock context manager.
Prevents concurrent execution of the same operation across multiple workers.
"""

import logging
from contextlib import contextmanager

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


@contextmanager
def distributed_lock(lock_key: str, timeout: int = 300, blocking: bool = False):
    """
    Context manager for Redis-based distributed lock.

    Args:
        lock_key:  Redis key for the lock (e.g. 'lock:erp_sync')
        timeout:   Lock auto-expires after this many seconds (prevents deadlock)
        blocking:  If True, wait for lock. If False, skip if held.

    Usage (non-blocking — skip if already running):
        with distributed_lock('lock:erp_sync', timeout=600, blocking=False) as acquired:
            if not acquired:
                return {'status': 'skipped'}
            do_work()

    Usage (blocking — wait for lock):
        with distributed_lock('lock:report_gen', timeout=300, blocking=True) as acquired:
            generate_report()
    """
    r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    lock = r.lock(lock_key, timeout=timeout)
    acquired = lock.acquire(blocking=blocking)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock.release()
            except redis.exceptions.LockNotOwnedError:
                # Lock expired during long task — acceptable with acks_late
                logger.warning("Lock %s expired before release (task took too long)", lock_key)


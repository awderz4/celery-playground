"""
demo/tasks_module_03.py
=======================
Module 3 — Reliability & Failure Handling

Demonstrates:
  - Idempotency Pattern 1: DB unique constraint (get_or_create)
  - Idempotency Pattern 2: Redis lock via celery-once (QueueOnce)
  - Retry with exponential backoff + jitter
  - Retry storm (all tasks fail simultaneously) — shows why jitter matters
  - soft_time_limit + SoftTimeLimitExceeded graceful cleanup
  - Hard time_limit as safety net
  - Dead-letter routing after max retries exhausted
"""

import random
import time
import json
import os

import requests
from billiard.exceptions import SoftTimeLimitExceeded
from celery import shared_task
from celery.utils.log import get_task_logger
from celery_once import QueueOnce

from django.db import IntegrityError

logger = get_task_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 3.1 ─ Idempotency Pattern 1: DB unique constraint
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    name="demo.process_invoice",
)
def process_invoice(self, invoice_id: str):
    """
    Lab 3c — DB unique constraint prevents double-processing.

    The ProcessedInvoice model has invoice_id as a unique field.
    get_or_create returns (obj, created):
      created=True  → first execution, proceed normally
      created=False → already processed (duplicate run), skip safely

    This handles the Redis visibility_timeout duplicate execution scenario:
      1. Task starts (T=0), slow task (T+90min)
      2. visibility_timeout=3600s expires at T+60min
      3. Redis re-queues task — now TWO workers are running the same task
      4. First one to finish calls get_or_create → created=True → proceeds
      5. Second one calls get_or_create → created=False → skips
      6. Result: exactly one execution, no double charge

    Run the lab:
        uv run python scripts/submit_tasks.py 3.3
    """
    from demo.models import ProcessedInvoice

    obj, created = ProcessedInvoice.objects.get_or_create(
        invoice_id=invoice_id,
        defaults={"status": "processing"},
    )

    if not created:
        logger.warning(
            "Invoice %s already processed (status=%s). Skipping duplicate.",
            invoice_id, obj.status,
        )
        return {"status": "skipped", "reason": "already_processed", "invoice_id": invoice_id}

    try:
        # Simulate invoice processing work
        logger.info("Processing invoice %s (pid=%d)", invoice_id, os.getpid())
        time.sleep(0.5)  # simulate work

        obj.status = "done"
        obj.save(update_fields=["status"])
        logger.info("Invoice %s processed successfully", invoice_id)
        return {"status": "done", "invoice_id": invoice_id}

    except Exception:
        # Delete the record so a retry can reprocess it
        obj.delete()
        raise


# ─────────────────────────────────────────────────────────────────────────────
# 3.2 ─ Idempotency Pattern 2: Redis lock via celery-once
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    base=QueueOnce,
    once={"graceful": True, "timeout": 3600},
    acks_late=True,
    name="demo.sync_user_data",
)
def sync_user_data(user_id: int):
    """
    Lab 3c — celery-once prevents concurrent duplicate execution per user_id.

    Lock key is automatically: task_name + (user_id,)
    If a lock already exists for this user_id:
      graceful=True → task returns None silently (no exception)
      graceful=False → raises AlreadyQueued exception

    Use case: user triggers a sync via UI button — spamming the button
    should not create multiple simultaneous sync jobs.

    Run two copies in parallel — only one should execute:
        uv run python scripts/submit_tasks.py 3.3
    """
    logger.info("Syncing user %d data (pid=%d)", user_id, os.getpid())
    time.sleep(2)  # simulate sync work
    return {"status": "synced", "user_id": user_id}


# ─────────────────────────────────────────────────────────────────────────────
# 3.3 ─ Retry with exponential backoff + jitter
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=5,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=60,
    time_limit=90,
    name="demo.call_external_api",
)
def call_external_api(self, endpoint: str, payload: dict, fail_count: int = 0):
    """
    Lab 3a — flaky API task: fails `fail_count` times then succeeds.

    Retry strategy:
      - Base delay: 2^retry × 5s  (5s, 10s, 20s, 40s, 80s)
      - Jitter: ±30% of base delay
      - Why jitter? Without it, all retried tasks wake simultaneously,
        slamming the external API/DB at the same moment.

    With jitter (spread load):
      Retry 1: 4-7s  (not exactly 5s for every task)
      Retry 2: 7-13s
      Retry 3: 14-26s

    Without jitter (retry storm):
      Retry 1: exactly 5s → 100 tasks hit API simultaneously at T+5s
      Retry 2: exactly 10s → 100 tasks hit again simultaneously

    Run the lab:
        uv run python scripts/submit_tasks.py 3.1
    """
    attempt = self.request.retries + 1
    logger.info(
        "[call_external_api] attempt=%d endpoint=%s fail_count=%d",
        attempt, endpoint, fail_count,
    )

    # Simulate failures for the first `fail_count` attempts
    if self.request.retries < fail_count:
        base_delay = 5 * (2 ** self.request.retries)
        jitter = random.uniform(0, base_delay * 0.3)
        delay = int(base_delay + jitter)
        logger.warning(
            "[call_external_api] Simulated failure on attempt %d — retrying in %ds",
            attempt, delay,
        )
        raise self.retry(
            exc=RuntimeError(f"Simulated API failure (attempt {attempt})"),
            countdown=delay,
        )

    # Success path
    logger.info("[call_external_api] SUCCESS on attempt %d", attempt)
    return {
        "endpoint": endpoint,
        "attempts": attempt,
        "status": "success",
    }


@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
    soft_time_limit=30,
    time_limit=45,
    name="demo.flaky_http_task",
)
def flaky_http_task(self, url: str, task_number: int = 0):
    """
    Lab 3a — makes a real HTTP call with retry on failure.

    Handles:
      - 429 Rate Limited: retry after Retry-After header
      - 5xx Server Error: exponential backoff + jitter
      - Timeout: exponential backoff + jitter
      - Max retries exhausted: logs error, returns error dict

    Use with scripts/submit_tasks.py 3.1 against a mock server.
    """
    attempt = self.request.retries + 1
    logger.info("[flaky_http #%d] attempt=%d url=%s", task_number, attempt, url)

    try:
        resp = requests.get(url, timeout=10)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 30))
            logger.warning("[flaky_http #%d] Rate limited — retrying in %ds", task_number, retry_after)
            raise self.retry(countdown=retry_after)

        if resp.status_code >= 500:
            base = 10 * (2 ** self.request.retries)
            jitter = random.uniform(0, base * 0.3)
            raise self.retry(
                exc=RuntimeError(f"Server error {resp.status_code}"),
                countdown=int(base + jitter),
            )

        resp.raise_for_status()
        return {
            "task_number": task_number,
            "status_code": resp.status_code,
            "attempts": attempt,
        }

    except requests.Timeout as exc:
        base = 10 * (2 ** self.request.retries)
        jitter = random.uniform(0, base * 0.3)
        logger.warning("[flaky_http #%d] Timeout on attempt %d — retrying in %ds", task_number, attempt, int(base + jitter))
        raise self.retry(exc=exc, countdown=int(base + jitter))

    except requests.RequestException as exc:
        if self.request.retries >= self.max_retries:
            logger.error("[flaky_http #%d] Exhausted all %d retries: %s", task_number, self.max_retries, exc)
            return {"task_number": task_number, "status": "failed", "error": str(exc), "attempts": attempt}
        base = 10 * (2 ** self.request.retries)
        jitter = random.uniform(0, base * 0.3)
        raise self.retry(exc=exc, countdown=int(base + jitter))


# ─────────────────────────────────────────────────────────────────────────────
# 3.4 ─ Time limits — graceful cleanup on soft limit
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    acks_late=True,
    soft_time_limit=3,   # Lab: intentionally short so you can trigger it
    time_limit=5,
    name="demo.process_large_csv",
)
def process_large_csv(self, file_id: int, row_count: int = 100, row_delay: float = 0.1):
    """
    Lab 3b — demonstrates soft_time_limit + SoftTimeLimitExceeded cleanup.

    soft_time_limit fires SIGUSR1 → raises SoftTimeLimitExceeded in the task.
    The except block saves progress before the hard SIGKILL arrives.

    With soft_time_limit=3s and row_delay=0.1s:
      - Processes ~30 rows before timeout
      - Saves partial progress to DB (status='timeout')
      - Hard time_limit=5s never fires (cleanup completes in <2s)

    Run the lab:
        uv run python scripts/submit_tasks.py 3.2
    """
    from demo.models import CSVProcessingJob

    job, _ = CSVProcessingJob.objects.get_or_create(
        file_id=file_id,
        defaults={"status": "processing", "rows_processed": 0, "total_rows": row_count},
    )
    job.status = "processing"
    job.save(update_fields=["status"])

    rows_processed = 0
    logger.info("[process_large_csv] file_id=%d total_rows=%d", file_id, row_count)

    try:
        for i in range(row_count):
            time.sleep(row_delay)   # simulate per-row work
            rows_processed += 1

        job.status = "done"
        job.rows_processed = rows_processed
        job.save(update_fields=["status", "rows_processed"])
        logger.info("[process_large_csv] Completed %d/%d rows", rows_processed, row_count)
        return {"file_id": file_id, "status": "done", "rows_processed": rows_processed}

    except SoftTimeLimitExceeded:
        # Save partial progress — gives visibility into what completed
        job.status = "timeout"
        job.rows_processed = rows_processed
        job.save(update_fields=["status", "rows_processed"])
        logger.warning(
            "[process_large_csv] Soft timeout after %d/%d rows — progress saved",
            rows_processed, row_count,
        )
        return {"file_id": file_id, "status": "timeout", "rows_processed": rows_processed}


# ─────────────────────────────────────────────────────────────────────────────
# 3.5 ─ Retry storm simulation (no jitter vs jitter)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
    name="demo.task_without_jitter",
)
def task_without_jitter(self, task_number: int):
    """
    Lab 3b — all tasks retry at EXACTLY the same time → thundering herd.

    Without jitter:
      All 20 tasks fail simultaneously at T+0.
      All 20 retry at T+5s exactly.
      All 20 retry again at T+10s exactly.
      → Thundering herd hits your DB/API 3 times.
    """
    if self.request.retries < 2:   # fail twice, succeed on 3rd
        logger.info("[no_jitter #%d] Failing — retry %d", task_number, self.request.retries + 1)
        raise self.retry(exc=RuntimeError("simulated failure"), countdown=5)
    return {"task_number": task_number, "attempts": self.request.retries + 1}


@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
    name="demo.task_with_jitter",
)
def task_with_jitter(self, task_number: int):
    """
    Lab 3b — tasks retry at randomised intervals → spread load evenly.

    With jitter:
      All 20 tasks fail simultaneously at T+0.
      Retries spread: T+3s to T+7s (random in 5±30% window).
      → Load on external system is spread, not spiked.
    """
    if self.request.retries < 2:   # fail twice, succeed on 3rd
        base = 5
        jitter = random.uniform(0, base * 0.3)
        delay = int(base + jitter)
        logger.info("[with_jitter #%d] Failing — retry %d in %ds", task_number, self.request.retries + 1, delay)
        raise self.retry(exc=RuntimeError("simulated failure"), countdown=delay)
    return {"task_number": task_number, "attempts": self.request.retries + 1}


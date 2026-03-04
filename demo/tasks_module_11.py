"""
demo/tasks_module_11.py
=======================
Module 11 — Advanced Patterns & Task Versioning

Demonstrates:
  - Celery Canvas: chain, group, chord
  - Task versioning: backward-compatible signature changes
  - ETA / countdown / expires
  - Distributed lock (Redis-based)
"""

import random
import time

from celery import chain, chord, group, shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 11.1 ─ Canvas primitives
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, acks_late=True, soft_time_limit=30, time_limit=45,
             name="demo.pipeline_download")
def pipeline_download(self, url: str):
    """Chain step 1: simulate file download."""
    logger.info("[pipeline_download] url=%s", url)
    time.sleep(0.05)
    return {"url": url, "local_path": f"/tmp/file_{hash(url) % 10000}.csv", "rows": 100}


@shared_task(bind=True, acks_late=True, soft_time_limit=30, time_limit=45,
             name="demo.pipeline_parse")
def pipeline_parse(self, download_result: dict):
    """Chain step 2: parse the downloaded file."""
    logger.info("[pipeline_parse] path=%s", download_result["local_path"])
    time.sleep(0.05)
    rows = [{"id": i, "value": i * 2} for i in range(download_result["rows"])]
    return {"rows": rows, "count": len(rows)}


@shared_task(bind=True, acks_late=True, soft_time_limit=30, time_limit=45,
             name="demo.pipeline_validate")
def pipeline_validate(self, parse_result: dict):
    """Chain step 3: validate parsed rows."""
    valid = [r for r in parse_result["rows"] if r["value"] >= 0]
    return {"valid_rows": valid, "valid_count": len(valid)}


@shared_task(bind=True, acks_late=True, soft_time_limit=60, time_limit=90,
             name="demo.pipeline_save")
def pipeline_save(self, validate_result: dict, user_id: int = 0):
    """Chain step 4: save valid rows to database."""
    count = validate_result["valid_count"]
    logger.info("[pipeline_save] saving %d rows for user %d", count, user_id)
    time.sleep(0.05)
    return {"saved": count, "user_id": user_id, "status": "done"}


def build_import_pipeline(url: str, user_id: int = 0):
    """
    Lab 11a — build a 4-step chain: download → parse → validate → save.

    Usage:
        pipeline = build_import_pipeline("https://example.com/data.csv", user_id=42)
        result = pipeline.apply_async()
        final = result.get(timeout=60)
    """
    return chain(
        pipeline_download.s(url),
        pipeline_parse.s(),
        pipeline_validate.s(),
        pipeline_save.s(user_id=user_id),
    )


@shared_task(bind=True, acks_late=True, soft_time_limit=60, time_limit=90,
             name="demo.process_batch")
def process_batch(self, batch: list, batch_id: int = 0):
    """Group member: process one batch of items in parallel."""
    time.sleep(0.05)
    result = sum(item.get("value", 0) for item in batch)
    return {"batch_id": batch_id, "total": result, "count": len(batch)}


@shared_task(bind=True, acks_late=True, soft_time_limit=30, time_limit=45,
             name="demo.aggregate_results")
def aggregate_results(self, batch_results: list):
    """Chord callback: aggregate all batch results into a summary."""
    total = sum(r.get("total", 0) for r in batch_results)
    count = sum(r.get("count", 0) for r in batch_results)
    return {"grand_total": total, "total_items": count, "batch_count": len(batch_results)}


# ─────────────────────────────────────────────────────────────────────────────
# 11.2 ─ Task versioning
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(acks_late=True, name="demo.send_email_v1")
def send_email_v1(email: str, template_id: str = "default", version: int = 1):
    """
    Lab 11c — version-safe task signature.

    All new args have defaults so old messages in queue still work.
    Old message: {"email": "x@x.com"}  → template_id="default", version=1
    New message: {"email": "x@x.com", "template_id": "welcome", "version": 2}

    Both handled by same function.
    """
    logger.info("[send_email_v1] email=%s template=%s version=%d", email, template_id, version)
    return {"email": email, "template_id": template_id, "version": version, "status": "sent"}


@shared_task(acks_late=True, name="demo.send_email_v2")
def send_email_v2(email: str, template_id: str, locale: str = "en"):
    """
    Lab 11c — new task name for breaking signature change.

    Deployment process:
      1. Deploy with both v1 and v2 present
      2. Update producers to use send_email_v2
      3. Wait for send_email_v1 queue to drain
      4. Remove send_email_v1 in next release
    """
    logger.info("[send_email_v2] email=%s template=%s locale=%s", email, template_id, locale)
    return {"email": email, "template_id": template_id, "locale": locale, "status": "sent"}


# ─────────────────────────────────────────────────────────────────────────────
# 11.3 ─ Distributed lock
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, acks_late=True, soft_time_limit=600, time_limit=660,
             name="demo.sync_inventory_from_erp")
def sync_inventory_from_erp(self):
    """
    Lab 11d — only one ERP sync should run at a time.

    Uses Redis distributed lock to prevent overlap when Beat
    schedules this every 10s but the task takes 20s.

    Without lock: 2+ simultaneous syncs → duplicate DB writes, ERP rate limit.
    With lock:    second execution detects lock → skips → no overlap.
    """
    from production_patterns.utils.distributed_lock import distributed_lock

    with distributed_lock("lock:erp_sync", timeout=600, blocking=False) as acquired:
        if not acquired:
            logger.info("[sync_inventory] Lock held by another worker — skipping")
            return {"status": "skipped", "reason": "lock_held"}

        logger.info("[sync_inventory] Lock acquired — running sync")
        time.sleep(0.1)  # simulate ERP API calls
        return {"status": "done", "items_synced": 42}


# ─────────────────────────────────────────────────────────────────────────────
# 11.4 ─ ETA / countdown / expires
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(acks_late=True, name="demo.expire_discount")
def expire_discount(discount_id: int):
    """Scheduled via ETA to run at exact expiry datetime."""
    logger.info("[expire_discount] discount_id=%d", discount_id)
    return {"discount_id": discount_id, "status": "expired"}


@shared_task(acks_late=True, name="demo.send_followup_email")
def send_followup_email(user_id: int):
    """Runs after a countdown delay (e.g. 24h after signup)."""
    logger.info("[send_followup] user_id=%d", user_id)
    return {"user_id": user_id, "status": "sent"}


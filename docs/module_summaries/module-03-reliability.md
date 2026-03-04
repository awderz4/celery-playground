# Module 3 — Reliability & Failure Handling

> **Branch:** `section-3-reliability`  
> **Builds on:** Module 2 (`section-2-worker-internals`)

---

## What You'll Learn

| Concept | Golden Rule |
|---------|-------------|
| Idempotency: DB unique constraint | Rule #1 |
| Idempotency: Redis lock (celery-once) | Rule #1 |
| Exponential backoff + jitter | — |
| Why jitter prevents thundering-herd retry storms | — |
| `soft_time_limit` → graceful cleanup before hard kill | Rule #6 |
| `SoftTimeLimitExceeded` exception handling pattern | Rule #6 |
| Dead-letter routing after max retries | Rule #9 |

---

## 3.1 — Failure Taxonomy

| Failure Type | Default Behaviour | Production Fix |
|---|---|---|
| Worker crash (SIGKILL) | Task LOST (acks_early) | `acks_late` + `reject_on_worker_lost` |
| Task exception (Python error) | Task → FAILURE state | retry + `on_failure` handler |
| Task timeout (hung task) | Worker frozen forever | `soft_time_limit` + `time_limit` |
| Duplicate execution | Task runs twice | Idempotency key or celery-once |

---

## 3.2 — Idempotency Patterns

### Pattern 1: DB Unique Constraint

```python
obj, created = ProcessedInvoice.objects.get_or_create(
    invoice_id=invoice_id,
    defaults={"status": "processing"},
)
if not created:
    return {"status": "skipped", "reason": "already_processed"}
```

✅ **Simplest and most reliable** — atomic at the DB level.

### Pattern 2: Redis Lock (celery-once)

```python
@app.task(base=QueueOnce, once={"graceful": True, "timeout": 3600})
def sync_user_data(user_id: int):
    pass  # lock key = task_name + (user_id,)
```

✅ **Per-argument deduplication** — only one `sync_user_data(user_id=42)` runs at a time.

---

## 3.3 — Retry with Exponential Backoff + Jitter

### Without Jitter (thundering herd)

```
T+0:   100 tasks all fail simultaneously
T+5:   100 tasks ALL retry at exactly T+5s  ← hammer your API
T+10:  100 tasks ALL retry at exactly T+10s ← hammer again
```

### With Jitter (spread load)

```python
base_delay = 5 * (2 ** self.request.retries)
jitter = random.uniform(0, base_delay * 0.3)   # ±30%
raise self.retry(exc=exc, countdown=int(base_delay + jitter))
```

```
T+0:   100 tasks all fail simultaneously
T+4-7: retries spread randomly across 3s window ← API survives
```

---

## 3.4 — Time Limits

```python
@app.task(soft_time_limit=300, time_limit=360, acks_late=True)
def process_large_csv(self, file_id: int):
    try:
        for row in stream_csv(...):
            process_row(row)
            rows_processed += 1
    except SoftTimeLimitExceeded:
        # SIGUSR1 fired — save progress before SIGKILL arrives
        job.status = "timeout"
        job.rows_processed = rows_processed
        job.save()
```

| Limit | Signal | Effect | When to Use |
|-------|--------|--------|-------------|
| `soft_time_limit` | SIGUSR1 → exception | Allows cleanup | Always — 10-20% before hard |
| `time_limit` | SIGKILL | Immediate kill | Absolute safety net |

---

## Labs

### Lab 3a — Flaky API Retry

```bash
# Start worker
uv run celery -A celery_playground worker -Q default --prefetch-multiplier=1 -l info

# Submit a task that fails 3 times then succeeds
uv run python scripts/submit_tasks.py 3.1

# Watch logs — observe increasing backoff delays:
# attempt 1: fail, retry in ~5s
# attempt 2: fail, retry in ~10s
# attempt 3: fail, retry in ~20s
# attempt 4: SUCCESS
```

### Lab 3b — Retry Storm (jitter comparison)

```bash
# Submit 20 tasks WITHOUT jitter — watch all retry at same moment
uv run python scripts/submit_tasks.py 3.2

# Then submit 20 tasks WITH jitter — retries spread across window
# Compare Redis MONITOR output — see the difference in timing
docker exec -it celery-playground-redis redis-cli MONITOR
```

### Lab 3c — Duplicate Prevention

```bash
# Submit the same invoice twice — second run should be skipped
uv run python scripts/submit_tasks.py 3.3

# Verify in Django shell:
uv run python manage.py shell -c "
from demo.models import ProcessedInvoice
for inv in ProcessedInvoice.objects.all():
    print(inv)
"
```

---

## Run Tests

```bash
uv run pytest tests/test_module_03_reliability.py -v
```

---

## New Files

| File | Purpose |
|------|---------|
| `demo/tasks_module_03.py` | All Module 3 tasks |
| `demo/models.py` | `ProcessedInvoice`, `CSVProcessingJob` |
| `demo/migrations/0001_initial.py` | DB migration for new models |
| `tests/test_module_03_reliability.py` | 23 tests |

---

## Next Module

**Module 4 — Backpressure, Rate Control & Dead Letters**  
Branch: `section-4-backpressure`


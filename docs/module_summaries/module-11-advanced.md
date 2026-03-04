# Module 11 — Advanced Patterns & Task Versioning

> **Branch:** `section-11-advanced`

---

## Celery Canvas

### Chain — Sequential Pipeline

```python
pipeline = chain(
    download_file.s(url),
    parse_csv.s(),           # receives previous result as first arg
    validate_rows.s(),
    save_to_database.s(user_id=42),
)
pipeline.apply_async()
```

### Group — Parallel Fan-Out

```python
job = group(process_batch.s(batch) for batch in batches)
results = job.apply_async().get(timeout=60)
```

### Chord — Parallel + Callback

```python
workflow = chord(
    group(process_batch.s(b) for b in batches),
    aggregate_results.s()   # called when ALL batches complete
)
workflow()
```

⚠️ **Chord at scale:** 10,000 tasks → 10,000 result keys in Redis.  
For very large parallel jobs, use a Redis `INCR` counter instead.

---

## Task Versioning

```python
# Safe: all new args have defaults (old queue messages still work)
@app.task
def send_email(email: str, template_id: str = "default", version: int = 1):
    pass

# Breaking change: use a new task name during transition
@app.task(name="myapp.tasks.send_email_v2")
def send_email_v2(email: str, template_id: str, locale: str = "en"):
    pass
```

**Deployment process:**
1. Deploy both `v1` and `v2` tasks
2. Drain `v1` queue: `celery control cancel_consumer default`
3. Wait for queue to empty
4. Remove `v1` in next release

---

## Distributed Lock

```python
from production_patterns.utils.distributed_lock import distributed_lock

@app.task
def sync_inventory():
    with distributed_lock("lock:erp_sync", timeout=600, blocking=False) as acquired:
        if not acquired:
            return {"status": "skipped"}  # another worker is running
        return run_erp_sync()
```

---

## ETA / Countdown / Expires

```python
# Run at exact time
expire_discount.apply_async(args=[discount_id], eta=discount.expires_at)

# Run after delay
send_followup.apply_async(args=[user_id], countdown=86400)  # 24h

# Drop if not picked up in 5 minutes
send_push.apply_async(args=[user_id, msg], expires=300)
```

---

## Labs

### Lab 11a — Import Pipeline Chain

```bash
uv run python scripts/submit_tasks.py 11.1
# Chain: download → parse → validate → save
# Kill worker mid-chain — observe which step restarts
```

### Lab 11d — Distributed Lock

```bash
# Schedule sync_inventory every 10s (task takes 20s)
# Without lock: 2 simultaneous syncs
# With lock: second execution skips gracefully
uv run celery -A celery_playground beat -l info &
uv run celery -A celery_playground worker -Q default -l info
```

---

## Run Tests

```bash
uv run pytest tests/test_module_11_advanced.py -v
```


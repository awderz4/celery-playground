# Module 4 — Backpressure, Rate Control & Dead Letters

> **Branch:** `section-4-backpressure`  
> **Builds on:** Module 3 (`section-3-reliability`)

---

## What You'll Learn

| Concept | Golden Rule |
|---------|-------------|
| Queue depth stages & response thresholds | Rule #9 |
| Circuit breaker in task producers | — |
| Per-task rate limiting (`10/m`, `100/m`) | — |
| `ProductionTask` base class — auto dead-letter | Rule #9 |
| Dead-letter queue: inspect, replay, clear | — |

---

## 4.1 — Backpressure Stages

```
Stage 1: depth 0 → 100       Normal operation
Stage 2: depth 100 → 500     ALERT: scale workers
Stage 3: depth 500 → 2,000   ALERT: rate-limit producers, set expires on tasks
Stage 4: depth > 2,000       CRITICAL: pause non-critical submissions
Stage 5: Redis mem > 80%     EMERGENCY: drop with expires=0, flush old results
```

### Circuit Breaker (`production_patterns/utils/circuit_breaker.py`)

```python
from production_patterns.utils.circuit_breaker import safe_enqueue

# Instead of: send_email.delay(user_id=42)
safe_enqueue(send_email, user_id=42, queue="notifications")
# → depth > 5000: raises QueueFullError (task dropped)
# → depth > 1000: enqueued with expires=300 (drop if not processed in 5min)
# → depth <= 1000: enqueued normally
```

---

## 4.2 — Rate Limiting

```python
@app.task(rate_limit="10/m")   # 10/minute per worker process
def send_sms(phone, message): ...

@app.task(rate_limit="100/m")  # 100/minute per worker
def send_bulk_email(to, subject): ...

# Change dynamically (no restart):
current_app.control.rate_limit("demo.send_sms", "5/m")
```

---

## 4.3 — ProductionTask Base Class

```python
from production_patterns.tasks.base import ProductionTask

@app.task(base=ProductionTask, max_retries=3)
def process_payment(order_id: str): ...
```

Automatically provides:
- `acks_late=True`
- `reject_on_worker_lost=True`
- `soft_time_limit=300`, `time_limit=360`
- Dead-letter routing after `max_retries` exhausted

---

## 4.4 — Dead-Letter Queue

After `max_retries` exhausted, `ProductionTask.on_failure()` pushes to:
```
Redis key: celery:dead-letter  (LPUSH, capped at 10,000 entries)
```

### Inspect
```bash
docker exec celery-playground-redis redis-cli LRANGE celery:dead-letter 0 -1
```

### Inspect & Replay
```bash
uv run python scripts/replay_dead_letter.py --inspect
uv run python scripts/replay_dead_letter.py          # prompts before replaying
uv run python scripts/replay_dead_letter.py --limit 50
uv run python scripts/replay_dead_letter.py --clear
```

---

## Labs

### Lab 4a — Rate Limiting

```bash
uv run celery -A celery_playground worker -Q default --prefetch-multiplier=1 -l info

# Submit 50 SMS tasks — watch worker throttle at 10/min
uv run python scripts/submit_tasks.py 4.1
```

### Lab 4b — Dead Letter

```bash
# Submit tasks that always fail — watch them exhaust retries
uv run python scripts/submit_tasks.py 4.2

# Inspect dead-letter queue
uv run python scripts/replay_dead_letter.py --inspect

# "Fix" the bug (tasks are always_fails — inspect shows them)
# Replay (they'll fail again, but you see the flow)
uv run python scripts/replay_dead_letter.py
```

### Lab 4c — Circuit Breaker Load Test

```bash
# No worker running — queue will grow
# Submit 10,000 tasks rapidly
uv run python scripts/submit_tasks.py 4.3

# Watch queue depth
docker exec celery-playground-redis redis-cli LLEN default
# Circuit breaker activates at depth > 1000 (expires) and > 5000 (drop)
```

---

## Run Tests

```bash
uv run pytest tests/test_module_04_backpressure.py -v
```

---

## New Files

| File | Purpose |
|------|---------|
| `production_patterns/tasks/base.py` | `ProductionTask` base with dead-letter routing |
| `production_patterns/utils/circuit_breaker.py` | `safe_enqueue` circuit breaker |
| `demo/tasks_module_04.py` | Rate-limited, ProductionTask, queue-depth tasks |
| `scripts/replay_dead_letter.py` | Inspect/replay/clear dead-letter queue |
| `tests/test_module_04_backpressure.py` | 18 tests |

---

## Next Module

**Module 5 — Queue Architecture & Isolation**  
Branch: `section-5-queue-isolation`


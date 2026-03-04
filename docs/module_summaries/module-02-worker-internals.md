# Module 2 — Worker Internals & Concurrency

> **Branch:** `section-2-worker-internals`  
> **Builds on:** Module 1 (`section-1-task-lifecycle`)

---

## What You'll Learn

| Concept | Golden Rule |
|---------|-------------|
| Prefork vs gevent pool internals | — |
| Why `prefetch_multiplier=4` destroys production reliability | Rule #3 |
| `acks_late=True` — the most important single setting | Rule #2 |
| `reject_on_worker_lost=True` for SIGKILL safety | Rule #2 |
| `visibility_timeout` must exceed max task duration | Rule #4 |
| `max_tasks_per_child` prevents memory leak accumulation | — |
| Worker autoscaling: built-in vs Kubernetes HPA | — |

---

## 2.1 — Concurrency Architecture

### Prefork Pool (default) — for CPU-bound tasks

```
Master Process
  ├── Worker Process 1  (~150MB RAM, own memory space)
  ├── Worker Process 2  (~150MB RAM)
  ├── Worker Process 3  (~150MB RAM)
  └── Worker Process N  (~150MB RAM)
```

- **Best for:** image resize, data processing, CPU-heavy work  
- **RAM:** N × ~150MB per process  
- **Parallelism:** true OS-level parallelism across CPU cores  
- **Isolation:** one crash = one process dies, others continue  

### Gevent Pool — for I/O-bound tasks

```
Single Process
  ├── Green Thread 1 ──┐
  ├── Green Thread 2   │  Cooperative scheduling
  ├── Green Thread 3   │  (yield on I/O wait)
  └── Green Thread N ──┘
```

- **Best for:** HTTP calls, notifications, DB queries, webhooks  
- **RAM:** 1 × ~150MB (all threads share one process)  
- **Parallelism:** cooperative — yields on every I/O call  
- **Concurrency:** 50–500 green threads per process  

### Pool Comparison

| Pool | Best For | Concurrency | Memory | Risk |
|------|----------|-------------|--------|------|
| `prefork` | CPU-bound | = CPU cores (max 2x) | High — N × process size | One crash per process |
| `gevent` | I/O-bound | 50–500 | Low — single process | One bug crashes all threads |
| `eventlet` | Same as gevent | 50–500 | Low | Less maintained |
| `threads` | Mixed | 4–20 | Medium | GIL limits CPU parallelism |
| `solo` | Debugging only | 1 | Minimal | No parallelism |

---

## 2.2 — Prefetch Multiplier: The Most Dangerous Default

### The Problem (prefetch=4, default)

```
Worker A: [EXECUTING task1] [PRE-FETCHED task2] [task3] [task4]
                            ↑ invisible to Flower, can be LOST
```

With `prefetch=4` and `concurrency=1`:
1. Worker grabs **4 tasks** into memory before starting task 1
2. Tasks 2–4 are **invisible** to Flower, other workers, and monitoring
3. Deploy new code → worker restarts → tasks 2–4 are **LOST** (if `acks_early`)
4. Priority task arrives → waits behind 3 pre-fetched slow tasks

### The Fix (prefetch=1)

```
Worker A: [EXECUTING task1]
Queue:    [task2] [task3] [task4]  ← visible, monitorable, reassignable
```

```python
# settings.py
CELERYD_PREFETCH_MULTIPLIER = 1  # Always, for production
```

---

## 2.3 — Task Acknowledgment & Visibility Timeout

### Acknowledgment Modes

| Setting | Behaviour | Task Loss Risk | Production? |
|---------|-----------|----------------|-------------|
| `acks_early` (default) | ACK when task **received** from broker | HIGH — crash = lost task | 🚫 No |
| `acks_late=True` | ACK only **after** successful execution | LOW — crash = re-queue | ✅ Yes |
| `reject_on_worker_lost=True` | REJECT (not re-queue) if worker is SIGKILL'd | None — immediate re-queue | ✅ Yes with acks_late |

### Visibility Timeout Trap

```
Task takes 90 min.
visibility_timeout = 3600s (1 hour — Redis default).

At T+60min: Redis assumes worker died, re-queues the task.
Result: task runs TWICE simultaneously — duplicate data, double charges.

Fix: CELERY_BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 86400}
```

---

## 2.4 — Worker Autoscaling

```bash
# Built-in Celery autoscaler
celery -A myproject worker --autoscale=10,2
#                                    ^  ^ min workers
#                                    max workers

# WARNING: autoscaler adds 1 worker at a time — very slow
# For production: use Kubernetes HPA with queue-length metric (Module 10)
```

---

## Labs

### Lab 2a — Prefetch Starvation (the "lost tasks" experiment)

**Start a bad worker (prefetch=4):**
```bash
uv run celery -A celery_playground worker -Q default \
    --concurrency=1 --prefetch-multiplier=4 --pool=prefork -l info
```

**Submit 8 slow tasks then kill at T+15s:**
```bash
uv run python scripts/submit_tasks.py 2.1
# In another terminal, after tasks are submitted:
uv run python scripts/kill_worker.py --delay 15
```

**Count survivors in Redis:**
```bash
redis-cli -p 6380 LLEN celery
# With prefetch=4: only ~4-5 tasks visible (2-4 were pre-fetched and lost)
```

**Repeat with the safe configuration:**
```bash
uv run celery -A celery_playground worker -Q default \
    --concurrency=1 --prefetch-multiplier=1 --pool=prefork -l info

uv run python scripts/submit_tasks.py 2.1
uv run python scripts/kill_worker.py --delay 15
redis-cli -p 6380 LLEN celery
# With prefetch=1 + acks_late: all 7 tasks re-appear in queue
```

---

### Lab 2b — acks_early vs acks_late

```bash
# Start worker
uv run celery -A celery_playground worker -Q default \
    --concurrency=4 --prefetch-multiplier=1 -l info

# Submit comparison tasks
uv run python scripts/submit_tasks.py 2.2

# Kill worker while tasks are running
uv run python scripts/kill_worker.py

# Check Redis — only acks_late tasks survive
redis-cli -p 6380 LLEN celery
```

---

### Lab 2c — Gevent Benchmark (I/O-bound tasks)

**Prefork worker (baseline):**
```bash
uv run celery -A celery_playground worker -Q default \
    --pool=prefork --concurrency=4 --prefetch-multiplier=1 -l info

uv run python benchmarks/concurrency_test.py --mode io --count 20
# Expected: ~5 seconds (20 tasks / 4 concurrent = 5 batches × 1s)
```

**Gevent worker (fast):**
```bash
uv run celery -A celery_playground worker -Q default \
    --pool=gevent --concurrency=50 --prefetch-multiplier=1 -l info

uv run python benchmarks/concurrency_test.py --mode io --count 20
# Expected: ~2-3 seconds (all 20 run concurrently)
```

**CPU benchmark (gevent penalty):**
```bash
uv run python benchmarks/concurrency_test.py --mode cpu --count 8
# gevent: ~8s (sequential despite "concurrency=50")
# prefork: ~2s (4 cores working in parallel)
```

---

### Lab 2d — Worker Identity / PID Tracking

```bash
# Start worker with low max_tasks_per_child to see recycling
uv run celery -A celery_playground worker -Q default \
    --max-tasks-per-child=5 --prefetch-multiplier=1 -l info

# Submit 15 tasks and watch PIDs change every 5 tasks
uv run python scripts/submit_tasks.py 2.3
```

---

## Worker Command Reference

```bash
# Default worker — CPU-bound, general purpose
uv run celery -A celery_playground worker \
    --loglevel=info \
    --concurrency=4 \
    --pool=prefork \
    -Q default \
    --max-tasks-per-child=200 \
    --max-memory-per-child=400000 \
    --prefetch-multiplier=1 \
    --hostname=worker-default@%h

# Notifications worker — I/O-bound, high concurrency
uv run celery -A celery_playground worker \
    --loglevel=info \
    --concurrency=100 \
    --pool=gevent \
    -Q notifications \
    --prefetch-multiplier=1 \
    --hostname=worker-notifications@%h

# Media worker — CPU-heavy, low concurrency
uv run celery -A celery_playground worker \
    --loglevel=info \
    --concurrency=2 \
    --pool=prefork \
    -Q media \
    --max-tasks-per-child=50 \
    --max-memory-per-child=800000 \
    --prefetch-multiplier=1 \
    --hostname=worker-media@%h
```

---

## Run Tests

```bash
uv run pytest tests/test_module_02_worker_internals.py -v
```

---

## Key Settings Added

```python
# settings.py — all already configured
CELERYD_PREFETCH_MULTIPLIER = 1       # Rule #3 — no pre-fetching
CELERY_TASK_ACKS_LATE = True          # Rule #2 — ACK after success
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # Immediate NACK on SIGKILL
CELERYD_MAX_TASKS_PER_CHILD = 200     # Recycle to prevent memory drift
CELERYD_MAX_MEMORY_PER_CHILD = 400000 # 400MB hard limit
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 86400,       # Rule #4 — 24h > any task duration
}
```

---

## New Files in This Module

| File | Purpose |
|------|---------|
| `demo/tasks_module_02.py` | All Module 2 tasks (slow, acks, I/O, CPU, identity) |
| `benchmarks/concurrency_test.py` | prefork vs gevent throughput benchmark |
| `scripts/kill_worker.py` | SIGKILL a running worker for labs 2a/2b |
| `tests/test_module_02_worker_internals.py` | 20 tests covering all concepts |

---

## Next Module

**Module 3 — Reliability & Failure Handling**  
Branch: `section-3-reliability`  
Topics: idempotency, exponential backoff + jitter, time limits, dead-letter queue


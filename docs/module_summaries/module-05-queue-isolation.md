# Module 5 — Queue Architecture & Isolation

> **Branch:** `section-5-queue-isolation`  
> **Builds on:** Module 4 (`section-4-backpressure`)

---

## What You'll Learn

| Concept | Golden Rule |
|---------|-------------|
| Multi-queue architecture: 5 queues by workload type | Rule #5 |
| Task routing via `CELERY_TASK_ROUTES` | Rule #5 |
| Queue starvation: mixing slow and fast tasks | Rule #5 |
| Dedicated workers per queue (gevent vs prefork) | — |
| Worker SLA configuration per queue type | — |

---

## 5.1 — Reference Queue Architecture

| Queue | Priority | Workers | Pool | SLA |
|-------|----------|---------|------|-----|
| `critical` | 10 | dedicated (2) | prefork | < 1s enqueue |
| `notifications` | 8 | gevent (2–20) | gevent | concurrency=100 |
| `default` | 5 | prefork (2–10) | prefork | general purpose |
| `media` | 3 | prefork (1–5) | prefork | concurrency=2 |
| `imports` | 2 | prefork (1–3) | prefork | concurrency=1 |

---

## 5.2 — Starvation Anti-Pattern

```bash
# BAD: single worker on all queues
celery worker -Q default,notifications,media,imports
# → 1 slow media encode (5 min) blocks 50 email notifications
# → Users get emails 25 minutes late

# GOOD: dedicated worker per queue type
celery worker -Q critical   --hostname=worker-critical@%h
celery worker -Q notifications --pool=gevent --concurrency=100
celery worker -Q media      --concurrency=2
```

---

## Labs

### Lab 5a — Starvation Demo

```bash
# Single mixed worker
uv run celery -A celery_playground worker -Q default,notifications,media \
    --concurrency=4 --prefetch-multiplier=1 -l info

# Submit 20 slow media tasks + 5 email notifications
uv run python scripts/submit_tasks.py 5.1
# Observe: emails wait behind media tasks
```

### Lab 5b — Separate Workers

```bash
# Start dedicated workers
uv run celery -A celery_playground worker -Q notifications \
    --pool=gevent --concurrency=100 --hostname=worker-notif@%h -l info &
uv run celery -A celery_playground worker -Q media \
    --concurrency=2 --hostname=worker-media@%h -l info &

uv run python scripts/submit_tasks.py 5.1
# Emails finish in < 1s regardless of media queue depth
```

---

## Run Tests

```bash
uv run pytest tests/test_module_05_queue_isolation.py -v
```

---

## New Files

| File | Purpose |
|------|---------|
| `demo/tasks_module_05.py` | Tasks for all 5 queues |
| `tests/test_module_05_queue_isolation.py` | 15 tests |
| `docs/module_summaries/module-05-queue-isolation.md` | This file |

---

## Next Module

**Module 6 — Memory Management & Performance**  
Branch: `section-6-memory-management`


# Celery Production Mastery

> Django · Redis · Kubernetes · 12 Modules · 24+ Labs · 40+ Production Patterns

---

## Course Structure

Each module lives on its own branch. Check out the branch to get **only the code for that module** — no spoilers from later modules.

```bash
git checkout module-00-baseline       # start here
git checkout module-01-task-lifecycle
git checkout module-02-worker-internals
# ... continue through module-11-advanced
```

| Branch | Module | Topic | Tests |
|--------|--------|-------|-------|
| [module-00-baseline](../../tree/module-00-baseline) | 0 | Architecture & Golden Rules | — |
| [module-01-task-lifecycle](../../tree/module-01-task-lifecycle) | 1 | Core Architecture & Lifecycle | 23 |
| [module-02-worker-internals](../../tree/module-02-worker-internals) | 2 | Worker Internals & Concurrency | 24 |
| [module-03-reliability](../../tree/module-03-reliability) | 3 | Reliability & Failure Handling | 23 |
| [module-04-backpressure](../../tree/module-04-backpressure) | 4 | Backpressure, Rate Control & Dead Letters | 20 |
| [module-05-queue-isolation](../../tree/module-05-queue-isolation) | 5 | Queue Architecture & Isolation | 15 |
| [module-06-memory-management](../../tree/module-06-memory-management) | 6 | Memory Management & Performance | 10 |
| [module-07-beat-scheduling](../../tree/module-07-beat-scheduling) | 7 | Scheduling & django-celery-beat | 9 |
| [module-08-monitoring](../../tree/module-08-monitoring) | 8 | Monitoring, Logging & Tracing | 9 |
| [module-09-redis-ha](../../tree/module-09-redis-ha) | 9 | Redis Production Architecture | 13 |
| [module-10-kubernetes](../../tree/module-10-kubernetes) | 10 | Kubernetes Production Deployment | 14 |
| [module-11-advanced](../../tree/module-11-advanced) | 11 | Advanced Patterns & Task Versioning | 17 |

**Total: 192 tests**

---

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd celery-playground
uv sync

# 2. Start Redis + Flower
docker compose up redis flower -d

# 3. Check out Module 0
git checkout module-00-baseline

# 4. Follow the MODULE_README.md on each branch
```

---

## Redis Commands Reference

```bash
# Connect to Redis (redis-cli is inside the container)
docker exec -it celery-playground-redis redis-cli

# Check queue depth (queue key is 'default', not 'celery')
docker exec celery-playground-redis redis-cli LLEN default

# Watch all commands in real-time
docker exec -it celery-playground-redis redis-cli MONITOR

# Use the trace script (wrapper for all Redis inspection)
bash scripts/trace_redis.sh queue
bash scripts/trace_redis.sh dbsize
bash scripts/trace_redis.sh monitor
```

---

## The 10 Production Golden Rules

| # | Rule |
|---|------|
| 1 | Tasks MUST be idempotent |
| 2 | Always `acks_late=True` |
| 3 | `prefetch_multiplier=1` |
| 4 | `visibility_timeout` > max task duration |
| 5 | Separate queues by workload type |
| 6 | Set time limits on every task |
| 7 | JSON serializer only, never pickle |
| 8 | Run exactly one Beat instance |
| 9 | Monitor queue depth and failure rate |
| 10 | `terminationGracePeriod` > max task duration |

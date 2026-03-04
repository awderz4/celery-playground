# Celery Production Mastery — Complete Engineering Handbook

> Django · Redis · Kubernetes  
> 12 Modules · 24+ Labs · 40+ Production Patterns · 10+ K8s Configs

---

## Quick Start

```bash
# 1. Clone and install
git clone <repo>
cd celery-playground
uv sync

# 2. Start Redis
docker compose up redis -d

# 3. Apply migrations
uv run python manage.py migrate

# 4. Start a worker
uv run celery -A celery_playground worker -Q default \
    --prefetch-multiplier=1 --loglevel=info

# 5. Run the full test suite
uv run pytest tests/ -q
# → 192 passed
```

---

## Course Structure

| Module | Branch | Topic | Tests |
|--------|--------|-------|-------|
| 0 | `section-0-baseline-environment` | Architecture Decisions & Production Mindset | 5 |
| 1 | `section-1-task-lifecycle` | Celery Core Architecture | 18 |
| 2 | `section-2-worker-internals` | Worker Internals & Concurrency | 24 |
| 3 | `section-3-reliability` | Reliability & Failure Handling | 23 |
| 4 | `section-4-backpressure` | Backpressure, Rate Control & Dead Letters | 20 |
| 5 | `section-5-queue-isolation` | Queue Architecture & Isolation | 15 |
| 6 | `section-6-memory-management` | Memory Management & Performance | 10 |
| 7 | `section-7-beat-scheduling` | Scheduling & django-celery-beat | 9 |
| 8 | `section-8-monitoring` | Monitoring, Logging & Distributed Tracing | 9 |
| 9 | `section-9-redis-ha` | Redis Production Architecture | 13 |
| 10 | `section-10-kubernetes` | Kubernetes Production Deployment | 14 |
| 11 | `section-11-advanced` | Advanced Patterns & Task Versioning | 17 |
| **Total** | | | **192** |

---

## The 10 Production Golden Rules

| # | Rule | Why It Matters |
|---|------|----------------|
| 1 | Tasks MUST be idempotent | They will run more than once. Design for it. |
| 2 | Always enable `acks_late=True` | Crashed worker = lost task without it. |
| 3 | `prefetch_multiplier=1` for long tasks | Default=4 causes invisible task starvation. |
| 4 | `visibility_timeout` > max task duration | Redis re-queues running tasks if too short. |
| 5 | Separate queues by workload type | One slow task must never starve fast tasks. |
| 6 | Set time limits on every task | Hung tasks freeze a worker forever. |
| 7 | Use JSON serializer only, never pickle | pickle = RCE vulnerability. |
| 8 | Run exactly one Beat instance | Two Beats = every scheduled task runs twice. |
| 9 | Monitor queue depth and failure rate | Silent failures are the most dangerous. |
| 10 | `terminationGracePeriod` > max task duration | K8s rolling updates kill tasks mid-flight. |

---

## Module Summaries

| Module | Read the full guide |
|--------|---------------------|
| 0 — Baseline | `docs/module_summaries/module-00-baseline.md` |
| 2 — Worker Internals | `docs/module_summaries/module-02-worker-internals.md` |
| 3 — Reliability | `docs/module_summaries/module-03-reliability.md` |
| 4 — Backpressure | `docs/module_summaries/module-04-backpressure.md` |
| 5 — Queue Isolation | `docs/module_summaries/module-05-queue-isolation.md` |
| 6 — Memory | `docs/module_summaries/module-06-memory-management.md` |
| 7 — Beat | `docs/module_summaries/module-07-beat-scheduling.md` |
| 8 — Monitoring | `docs/module_summaries/module-08-monitoring.md` |
| 9 — Redis HA | `docs/module_summaries/module-09-redis-ha.md` |
| 10 — Kubernetes | `docs/module_summaries/module-10-kubernetes.md` |
| 11 — Advanced | `docs/module_summaries/module-11-advanced.md` |

---

## Key Files

| File | Purpose |
|------|---------|
| `celery_playground/settings.py` | All production Celery settings |
| `production_patterns/tasks/base.py` | `ProductionTask` base with auto dead-letter |
| `production_patterns/utils/circuit_breaker.py` | `safe_enqueue` backpressure guard |
| `production_patterns/utils/distributed_lock.py` | Redis distributed lock context manager |
| `scripts/replay_dead_letter.py` | DLQ inspect / replay / clear |
| `scripts/submit_tasks.py` | Lab task submission script |
| `scripts/validate_golden_rules.py` | Validate all 10 Golden Rules |
| `k8s/workers/` | K8s Deployment manifests (default/notifications/media/beat) |
| `k8s/keda/` | KEDA ScaledObjects (queue-depth autoscaling) |
| `k8s/hpa/` | HPA configurations |
| `docs/module_summaries/` | Per-module reference docs |

---

## Production Readiness Checklist

### Reliability
- [ ] All tasks idempotent (DB constraint or celery-once)
- [ ] `acks_late=True` on all workers
- [ ] `reject_on_worker_lost=True`
- [ ] `visibility_timeout` > max task duration (24h)
- [ ] `soft_time_limit` + `time_limit` on every task
- [ ] Dead-letter queue configured and monitored
- [ ] Retry with exponential backoff + jitter

### Performance
- [ ] `prefetch_multiplier=1` on all workers
- [ ] `max_tasks_per_child` configured (50–500)
- [ ] `max_memory_per_child` = 60% of pod memory limit
- [ ] Separate workers per queue type
- [ ] `gevent` pool for I/O-bound queues (notifications)

### Observability & Safety
- [ ] JSON serializer only (no pickle — ever)
- [ ] Flower deployed + basic auth secured
- [ ] Prometheus + Grafana alerts active
- [ ] Structured JSON logs + correlation IDs
- [ ] Redis AOF + RDB persistence enabled
- [ ] `volatile-lru` eviction on results DB
- [ ] Beat: `replicas: 1`, `strategy: Recreate`
- [ ] `terminationGracePeriodSeconds` > max task duration

---

## Run All Tests

```bash
uv run pytest tests/ -q
# 192 passed in ~72s
```

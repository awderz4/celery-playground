# ✅ Production Readiness Checklist

Before deploying Celery to production, verify all 24 items in this checklist. **Every item represents a real production incident if missed.**

---

## 🔐 Reliability (7 items)

| ☐ | Item | Verification | Why It Matters |
|---|------|--------------|----------------|
| ☐ | **All tasks are idempotent** | DB unique constraints or celery-once locks in place | Tasks will run more than once—duplicate execution must be safe |
| ☐ | **`acks_late=True` on all workers** | Check `app.conf.task_acks_late` or worker startup logs | Prevents task loss on worker crash |
| ☐ | **`reject_on_worker_lost=True`** | Check `app.conf.task_reject_on_worker_lost` | SIGKILL events re-queue task rather than drop it |
| ☐ | **`visibility_timeout` > max task duration** | Check `CELERY_BROKER_TRANSPORT_OPTIONS` | Prevents duplicate execution from Redis timeout |
| ☐ | **`soft_time_limit` + `time_limit` set on all long tasks** | Review task decorators | No worker can be frozen by a hung task |
| ☐ | **Dead-letter queue configured** | Submit failing task, verify it lands in DLQ | Failed tasks are inspectable, not silently discarded |
| ☐ | **Retry with exponential backoff + jitter** | Check retry logic in tasks | Prevents retry storms against external APIs |

---

## ⚡ Performance & Scalability (7 items)

| ☐ | Item | Verification | Why It Matters |
|---|------|--------------|----------------|
| ☐ | **`prefetch_multiplier=1` on all workers** | Check worker logs or `app.conf.worker_prefetch_multiplier` | Prevents invisible task starvation |
| ☐ | **`max_tasks_per_child` configured** | Check `CELERYD_MAX_TASKS_PER_CHILD` | Worker processes recycle—memory leaks can't compound |
| ☐ | **`max_memory_per_child` configured** | Check `CELERYD_MAX_MEMORY_PER_CHILD` | Hard memory guard before K8s OOMKills |
| ☐ | **Separate workers per queue type** | Run `celery inspect active` - verify dedicated workers | Slow workloads never starve fast workloads |
| ☐ | **Concurrency model matches workload** | Prefork for CPU, gevent for I/O | Right tool for the job—prevents wasted resources |
| ☐ | **Resource limits with 2x headroom** | Check K8s manifests: `limits.memory = 2x peak` | Pod memory limit should be 2x peak worker memory |
| ☐ | **HPA or KEDA configured** | Submit 1000 tasks, watch pods scale | Workers scale automatically with queue depth |

---

## 👁️ Observability & Safety (10 items)

| ☐ | Item | Verification | Why It Matters |
|---|------|--------------|----------------|
| ☐ | **JSON serializer only (no pickle)** | Check `CELERY_ACCEPT_CONTENT = ['json']` | pickle = RCE vulnerability |
| ☐ | **Flower deployed + secured** | Access http://flower-url with auth | Real-time visibility into workers and queues |
| ☐ | **Prometheus + Grafana alerts active** | Trigger alert (e.g., fill queue) | Silent failures surface as alerts |
| ☐ | **Distributed tracing configured** | Trace one request end-to-end | Debug across Django → Celery → DB |
| ☐ | **Structured JSON logs + correlation IDs** | Grep one correlation ID across logs | Trace user request through all systems |
| ☐ | **Redis persistence enabled (AOF + RDB)** | Check redis.conf: `appendonly yes` | Queued tasks survive Redis restart |
| ☐ | **Redis eviction policy = `volatile-lru`** | Check redis.conf: `maxmemory-policy` | Queue messages never evicted by memory pressure |
| ☐ | **Beat: `replicas=1`, Recreate strategy** | Check K8s manifest | Scheduled tasks never run twice |
| ☐ | **`terminationGracePeriod` > max task** | Check K8s manifest (should be 600s+) | Rolling updates don't kill in-flight tasks |
| ☐ | **Dead-letter alerts configured** | Trigger DLQ, verify alert fires | Engineers notified when tasks fail permanently |

---

## 🎯 You're Production Ready When...

✅ **All 24 checklist items are verified**

✅ **Grafana dashboard shows:**
- 0 failed tasks over 1 hour
- Queue depths are stable
- All workers are alive and healthy

✅ **Failure simulation passes:**
```bash
# Worker SIGKILL test
./scripts/kill_worker.py
# Result: Task re-queued, zero task loss

# Redis restart test
docker restart celery-playground-redis
# Result: Workers reconnect, tasks resume

# Beat restart test
kubectl delete pod -l app=celery-beat
# Result: New Beat starts, no duplicate schedules

# Rolling update test (K8s)
./scripts/rolling_update_test.sh
# Result: New code deployed, zero task loss measured
```

✅ **Team knowledge check:**
- Every engineer can explain the 10 Golden Rules
- On-call runbook is documented
- Rollback procedure is tested

---

## 📊 Scoring Your Readiness

- **0-10 items:** ❌ Not ready - significant production risk
- **11-18 items:** ⚠️ Partially ready - address gaps before go-live
- **19-23 items:** ✅ Nearly ready - finish remaining items
- **24 items:** 🎉 **PRODUCTION READY** - deploy with confidence!

---

## 🚨 Non-Negotiable Items (Critical Priority)

If you skip these, you **will** have incidents:

1. ⚠️ **`acks_late=True`** - Most common cause of task loss
2. ⚠️ **`prefetch_multiplier=1`** - Causes mysterious "queue not draining" issues
3. ⚠️ **JSON serializer only** - Security vulnerability
4. ⚠️ **Beat replicas=1** - Duplicate execution chaos
5. ⚠️ **Task idempotency** - Duplicate charges, duplicate emails

---

## 📅 Pre-Deployment Timeline

**1 week before:**
- [ ] Complete full checklist
- [ ] Run all failure simulations
- [ ] Load test with production-scale traffic
- [ ] Document rollback procedure

**1 day before:**
- [ ] Final checklist review
- [ ] Alert rules tested and firing correctly
- [ ] On-call engineer briefed
- [ ] Rollback tested

**Go-live day:**
- [ ] Deploy during low-traffic window
- [ ] Monitor for 2 hours minimum
- [ ] Verify key metrics are green
- [ ] Document any issues for postmortem

---

## 🔗 Related Documentation

- [Production Settings Template](./production_settings_template.py)
- [Worker Commands Reference](./worker_commands_reference.md)
- [Troubleshooting Guide](./troubleshooting_guide.md)
- [Failure Scenarios](./failure_scenarios.md)

---

**Remember:** Production readiness isn't a checkbox—it's a culture. Keep this checklist up to date as you learn from incidents.


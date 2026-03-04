# Module 8 — Monitoring, Logging & Distributed Tracing

> **Branch:** `section-8-monitoring`

---

## Observability Stack

| Layer | Tool | What It Answers |
|-------|------|-----------------|
| Metrics | Prometheus + Grafana | Queue depth, failure rate, worker count |
| Logs | Structured JSON + correlation ID | What happened and why |
| Traces | OpenTelemetry + Jaeger | How long each step took |
| Real-time | Flower | Right now — active tasks, worker status |

---

## Correlation IDs

Tie a single user request to all tasks it spawns:

```
HTTP request → X-Correlation-ID: abc-123
    → Django view enqueues task (header forwarded)
        → Worker executes task (header restored in thread-local)
            → Subtask inherits same correlation_id
                → All log lines share "correlation_id": "abc-123"
```

Grep one ID across all services:
```bash
grep "abc-123" /var/log/django/*.log /var/log/celery/*.log
```

---

## Prometheus Alert Rules

```yaml
# Queue depth alert
- alert: CeleryQueueDepthHigh
  expr: celery_queue_length{queue="critical"} > 10
  for: 2m
  labels: {severity: critical}

# Workers stuck (canary task)
- alert: CeleryWorkersStuck
  expr: time() - celery_task_succeeded_timestamp{task="demo.monitoring_canary"} > 120
  for: 2m
  labels: {severity: critical}

# High failure rate
- alert: CeleryHighFailureRate
  expr: rate(celery_task_failed_total[5m]) > 0.05
  for: 5m
  labels: {severity: warning}
```

---

## Labs

### Lab 8a — Deploy Observability Stack

```bash
docker compose up redis flower prometheus grafana -d
# Flower:     http://localhost:5555
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000 (admin/admin)
```

### Lab 8b — End-to-End Trace

```bash
# With Jaeger running (add to docker-compose):
uv run python scripts/submit_tasks.py 8.1
# View trace in Jaeger: HTTP request → task → DB query spans
```

### Lab 8d — Correlation ID

```bash
uv run python scripts/submit_tasks.py 8.4
# Submit task chain with shared correlation_id
# Grep logs: grep "corr-id" worker.log
```

---

## Run Tests

```bash
uv run pytest tests/test_module_08_monitoring.py -v
```


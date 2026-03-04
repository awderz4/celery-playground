# Module 10 — Kubernetes Production Deployment

> **Branch:** `section-10-kubernetes`  
> **Golden Rule #10:** `terminationGracePeriodSeconds` > max task duration

---

## Pod Termination Sequence

```
T=0:    Kubernetes sends SIGTERM to worker
T=0:    Worker stops accepting new tasks (warm shutdown)
T=0:    Worker finishes currently executing tasks
T=?:    Worker exits cleanly → ACK sent
T=600:  terminationGracePeriodSeconds expires → SIGKILL
```

With `acks_late=True`: SIGKILL → task NOT ACK'd → re-queued by broker.

---

## Worker Manifest Key Settings

```yaml
spec:
  terminationGracePeriodSeconds: 600   # > max task duration
  containers:
    - command:
        - celery -A celery_playground worker
        - --prefetch-multiplier=1
        - --max-tasks-per-child=200
        - --max-memory-per-child=400000
      resources:
        requests: {memory: "512Mi", cpu: "500m"}
        limits:   {memory: "1Gi",  cpu: "2000m"}
```

---

## Beat: Recreate Strategy (Non-Negotiable)

```yaml
spec:
  replicas: 1
  strategy:
    type: Recreate    # NEVER RollingUpdate for Beat
```

---

## KEDA Autoscaling

```yaml
# Scale notifications workers based on Redis queue depth
triggers:
  - type: redis
    metadata:
      listName: notifications
      listLength: "10"    # 1 replica per 10 queued tasks
```

---

## Labs

### Lab 10a — Zero-Loss Rolling Update

```bash
# Deploy with 20 slow tasks running
kubectl set image deployment/celery-worker-default worker=myapp:v2
# With acks_late=True: 0 tasks lost after rollout
```

### Lab 10b — KEDA Autoscaling

```bash
# Flood the notifications queue
uv run python scripts/submit_tasks.py 5.2  # 500 notifications
kubectl get pods -l queue=notifications -w
# Watch: 2 → 20 pods as queue grows, back to 2 as it drains
```

---

## Run Tests

```bash
uv run pytest tests/test_module_10_kubernetes.py -v
```

---

## New Files

| File | Purpose |
|------|---------|
| `k8s/workers/worker-default.yaml` | Default worker deployment |
| `k8s/workers/worker-notifications.yaml` | Gevent notifications worker |
| `k8s/workers/worker-media.yaml` | CPU-heavy media worker |
| `k8s/workers/beat-deployment.yaml` | Beat with Recreate strategy |
| `k8s/keda/scaledobject-notifications.yaml` | KEDA queue-depth autoscaler |
| `k8s/hpa/hpa-default.yaml` | Standard HPA for default queue |


# Module 6 — Memory Management & Performance

> **Branch:** `section-6-memory-management`

---

## What You'll Learn

| Concept | Setting |
|---------|---------|
| Why workers grow in RSS over time | module-level state |
| `max_tasks_per_child` — recycle and reset | `CELERYD_MAX_TASKS_PER_CHILD` |
| `max_memory_per_child` — hard RSS guard | `CELERYD_MAX_MEMORY_PER_CHILD` |
| Memory profiling with `tracemalloc` | in-task profiling |
| Kubernetes OOMKill prevention formula | pod limit = 2× peak |

---

## 6.1 — Memory Leak Pattern

```python
# THE BUG: module-level list accumulates across executions
_cache = []

@app.task
def leaky_task(data):
    _cache.extend(data)   # never cleared → grows forever
```

**Without `max_tasks_per_child`:**
```
Task 1:   RSS = 150MB
Task 100: RSS = 350MB
Task 500: RSS = 600MB  ← OOMKill at pod limit 512Mi
```

**With `max_tasks_per_child=200`:**
```
Task 200: RSS = 350MB → recycle → fresh process at 80MB
Task 400: RSS = 350MB → recycle → fresh process at 80MB
```

---

## 6.2 — K8s OOMKill Prevention Formula

```yaml
# Step 1: Profile actual peak RSS
# watch -n5 'kubectl top pods -l app=celery-worker'
# → Peak: 380MB

# Step 2: Set pod limits at 2× peak
resources:
  limits:
    memory: "1Gi"   # 2× 380MB = safe

# Step 3: Set max_memory_per_child = 60% of pod limit
# 1024MB × 0.60 = 614MB → CELERYD_MAX_MEMORY_PER_CHILD = 614000
```

---

## Labs

### Lab 6a — Memory Leak Observation

```bash
uv run celery -A celery_playground worker -Q default \
    --concurrency=1 --prefetch-multiplier=1 -l info

# Submit 50 leaky tasks — watch RSS grow
uv run python scripts/submit_tasks.py 6.1

# Check RSS
watch -n1 'ps aux | grep "[c]elery worker" | awk "{print \$6, \"KB\"}"'
```

### Lab 6b — max_tasks_per_child Fix

```bash
uv run celery -A celery_playground worker -Q default \
    --max-tasks-per-child=10 --concurrency=1 -l info

uv run python scripts/submit_tasks.py 6.1
# RSS resets every 10 tasks
```

---

## Run Tests

```bash
uv run pytest tests/test_module_06_memory.py -v
```


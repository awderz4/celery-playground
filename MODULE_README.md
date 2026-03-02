# Module 1: Celery Core Architecture — Task Lifecycle & Internals

[← Module 0](../../tree/section-0-baseline-environment) | **Current: Module 1** | [Module 2 →](../../tree/section-2-worker-internals)

---

## 📚 Learning Objectives

By completing this module, you will:

- ✅ Trace a task's complete journey through the **5-layer Celery architecture**
- ✅ Read and understand the raw **JSON message envelope** in Redis
- ✅ Observe all four **task state transitions** live in Flower
- ✅ Choose the right **result backend strategy** (store vs ignore)
- ✅ Understand the **visibility timeout trap** and how to avoid it
- ✅ Compare **Redis vs RabbitMQ** as brokers and know which to pick
- ✅ Know exactly why **pickle is forbidden** in production

---

## 🎯 Key Concepts

### 1.1 — The 5-Layer Architecture

Every Celery deployment has five layers. Know each one's failure mode:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: PRODUCER                                      │
│  Django view / management command / another task        │
│  Calls: my_task.delay(...)  or  my_task.apply_async()  │
└────────────────────────┬────────────────────────────────┘
                         │  serialises args to JSON
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: MESSAGE BROKER  (Redis DB 0)                  │
│  Stores the message in a Redis LIST key named           │
│  after the queue  (default: "celery")                   │
│  Command: LPUSH celery <json-envelope>                  │
└────────────────────────┬────────────────────────────────┘
                         │  worker polls with BRPOP
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 3: WORKER  (celery worker process)               │
│  Deserialises JSON, imports the task function,          │
│  executes it.  One process per concurrency slot.        │
└────────────────────────┬────────────────────────────────┘
                         │  SET result key with TTL
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 4: RESULT BACKEND  (Redis DB 1)                  │
│  Key: celery-task-meta-<uuid>                           │
│  Value: {"status": "SUCCESS", "result": ..., ...}       │
│  TTL: CELERY_RESULT_EXPIRES seconds (default 3600)      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 5: MONITORING  (Flower / Prometheus)             │
│  Flower polls the result backend and worker events      │
│  to show task history, state, runtime, arguments        │
└─────────────────────────────────────────────────────────┘
```

### 1.2 — Task State Machine

A task moves through exactly these states:

```
.delay() called
      │
      ▼
  PENDING   ← task is in the queue; no worker has touched it yet
      │
      │  worker picks up the task  (BRPOP)
      ▼
  STARTED   ← only visible if track_started=True  (we set this)
      │
      ├──── task returns normally ──────→  SUCCESS
      │
      ├──── task raises an exception ──→  FAILURE
      │
      └──── task calls self.retry() ──→  RETRY → PENDING (re-queued)
```

**Check live in Flower:** Workers → [hostname] → Tasks tab.

### 1.3 — The JSON Message Envelope

Every task becomes a Redis LIST entry that looks like this:

```json
{
  "body": "W1sxMCwgMjBdLCB7fSwgeyJjYWxsYmFja3MiOiBudWxsLCAuLi59XQ==",
  "content-encoding": "utf-8",
  "content-type": "application/json",
  "headers": {
    "lang": "py",
    "task": "demo.tasks.slow_add",
    "id": "3b5d2c1a-...",
    "retries": 0,
    "argsrepr": "(10, 20)",
    "kwargsrepr": "{}"
  },
  "properties": {
    "correlation_id": "3b5d2c1a-...",
    "delivery_info": {"exchange": "", "routing_key": "celery"}
  }
}
```

The `body` is **base64-encoded JSON**: `[[10, 20], {}, {"callbacks": null, ...}]`

**Key insight:** Everything is plain JSON — you can read any queued task with  
`redis-cli LRANGE celery 0 0` and decode the body with standard tools.

### 1.4 — Broker Comparison: Redis vs RabbitMQ

| Factor | Redis | RabbitMQ |
|--------|-------|----------|
| **Message Durability** | AOF + RDB | Durable queues + disk by default |
| **Task Acknowledgment** | Visibility timeout (re-queue on expiry) | Explicit ACK/NACK per message |
| **Priority Queues** | Basic — limited native support | Native priority (0–255) |
| **High Availability** | Sentinel or Cluster | Mirrored / Quorum queues |
| **Operational Complexity** | Low — most teams already run Redis | Higher — dedicated ops knowledge |
| **Production Recommendation** | ✓ **Use for 95% of Django deployments** | Use when guaranteed delivery is critical |

### 1.5 — Serialisation Security (Golden Rule #7)

**Why pickle is banned:**  
A malicious actor with broker access can craft a pickle payload that executes  
arbitrary code when deserialized by the worker — a critical RCE vulnerability.

| Serialiser | Speed | Human Readable | Security | Use? |
|-----------|-------|---------------|---------|------|
| `json` | Fast | ✅ Yes | ✅ Safe | ✅ **Always** |
| `msgpack` | Fastest | ❌ Binary | ✅ Safe | Optional (high throughput) |
| `yaml` | Slow | ✅ Yes | ✅ Safe | ❌ Too slow |
| `pickle` | Fast | ❌ No | 🚨 **RCE** | 🚫 **Never** |

### 1.6 — Result Backend Memory Leak Pattern

```
10,000 tasks/day × 1KB result × 30 days (no TTL) = 300MB Redis bloat

Fix already in settings.py:  CELERY_RESULT_EXPIRES = 3600
```

**Decision tree:**
```
Do you call .get() or check task.state?
  YES → Enable result backend, CELERY_RESULT_EXPIRES = 3600
  NO  → ignore_result=True on the task  (saves Redis memory + CPU)
```

### 1.7 — The Visibility Timeout Trap (Golden Rule #4)

```
Task takes 90 min. visibility_timeout = 3600s (1 hour).

T+0:   Worker A picks up task, starts executing
T+60m: Redis assumes worker died → re-queues the task
T+60m: Worker B also picks it up — TWO WORKERS RUN SIMULTANEOUSLY
Result: duplicate data, double charges, chaos

Fix (already in settings.py):
  CELERY_BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 86400}  # 24 hours
```

---

## 🔧 Changes in This Module

### Modified: `demo/tasks.py`

| Task | `ignore_result` | Purpose |
|------|----------------|---------|
| `slow_add` | default | Baseline from Module 0 (preserved) |
| `task_with_states` | default | Observe PENDING→STARTED→SUCCESS |
| `task_that_fails` | default | Observe FAILURE state + traceback |
| `json_payload_task` | default | Read raw message envelope in Redis |
| `large_payload_task` | default | Measure result key size |
| `fire_and_forget` | **True** | Nothing stored in Redis |
| `store_result` | **False** | Result stored with TTL |
| `inspect_request` | default | Access task request context |
| `observable_task` | default | Visualise queue depth |

### New: `scripts/trace_redis.sh`

```bash
bash scripts/trace_redis.sh monitor       # Stream all Redis commands
bash scripts/trace_redis.sh queue         # Show queue depth + first message
bash scripts/trace_redis.sh results       # List result keys with TTLs
bash scripts/trace_redis.sh dbsize        # Compare broker vs results DB
bash scripts/trace_redis.sh ttl <uuid>    # TTL + size for one task result
```

### New: `scripts/submit_tasks.py`

```bash
uv run python scripts/submit_tasks.py 1.1   # State transitions
uv run python scripts/submit_tasks.py 1.2   # Serialization payloads
uv run python scripts/submit_tasks.py 1.3   # Result backend comparison
uv run python scripts/submit_tasks.py 1.4   # Request context
uv run python scripts/submit_tasks.py 1.5   # Queue depth (8 tasks)
uv run python scripts/submit_tasks.py all   # All labs
```

### New: `tests/test_module_01_architecture.py` — 24 tests

```
TestTaskExecution          (9 tests)  — all task types execute correctly
TestSerializationSecurity  (4 tests)  — JSON only, pickle forbidden
TestResultBackend          (4 tests)  — TTL configured, ignore flags correct
TestBrokerTransportOptions (3 tests)  — visibility_timeout, retry_on_timeout
TestWorkerReliabilitySettings (4 tests) — Golden Rules still hold
```

---

## 🔬 Lab Exercises

### Lab 1.1 — Observe State Transitions Live

**🎯 Goal:** Watch PENDING → STARTED → SUCCESS and FAILURE in Flower.

**🔧 Setup:**
```bash
docker-compose up -d
uv run celery -A celery_playground worker --loglevel=info   # Terminal 1
```

**💪 Challenge:** Submit tasks that produce both SUCCESS and FAILURE, then find them in Flower.

<details>
<summary>💡 Hints</summary>

- `task_with_states` runs for 8 seconds — plenty of time to catch STARTED state
- `task_that_fails` raises `ValueError` after 2 seconds
- In Flower: navigate to **Tasks** tab, filter by state
- `track_started=True` is required for STARTED to appear (it's already set)
</details>

<details>
<summary>✅ Solution</summary>

```bash
uv run python scripts/submit_tasks.py 1.1
```

In Flower (http://localhost:5555):
1. Click **Tasks** → watch `task_with_states` move PENDING → STARTED → SUCCESS
2. Find `task_that_fails` → click task ID → see full Python traceback

In worker logs you'll see:
```
Task demo.tasks.task_with_states received
Task <id> — STARTED (state=STARTED, worker=celery@hostname)
Task demo.tasks.task_with_states succeeded in 8.0s
Task demo.tasks.task_that_fails raised unexpected: ValueError(...)
```
</details>

**✓ Verification:**
- [ ] `task_with_states` shows STARTED state before SUCCESS
- [ ] `task_that_fails` shows FAILURE with `ValueError` traceback in Flower
- [ ] Worker logs show matching task IDs

---

### Lab 1.2 — Read the Raw Message Envelope

**🎯 Goal:** Decode the exact bytes Celery puts in Redis.

**🔧 Setup:**
```bash
# Stop the worker so the message stays in the queue
# Then in another terminal:
docker-compose exec redis redis-cli
```

**💪 Challenge:** Submit `json_payload_task`, read the raw JSON from `LRANGE celery 0 0`, and decode the base64 body to reveal `[args, kwargs, options]`.

<details>
<summary>💡 Hints</summary>

- Use `bash scripts/trace_redis.sh monitor` while submitting to see LPUSH in real time
- The `body` field value is base64 — decode with `base64 -d` or Python
- `bash scripts/trace_redis.sh queue` shows the first message neatly
</details>

<details>
<summary>✅ Solution</summary>

```bash
# Terminal 1: watch Redis commands
bash scripts/trace_redis.sh monitor

# Terminal 2: submit task (worker stopped)
uv run python scripts/submit_tasks.py 1.2
```

Decode the body:
```python
import base64, json
body_b64 = "<paste body value here>"
decoded = base64.b64decode(body_b64).decode()
print(json.dumps(json.loads(decoded), indent=2))
# Output: [[{"user_id": 42, ...}], {}, {"callbacks": null, ...}]
```

Check result key size after worker processes it:
```bash
bash scripts/trace_redis.sh ttl <task-uuid>
# SIZE=NNNb — this is the per-result Redis memory cost
```
</details>

**✓ Verification:**
- [ ] MONITOR shows `LPUSH celery` when task is submitted
- [ ] Body decodes to `[args, kwargs, options]` structure
- [ ] MONITOR shows `BRPOP` when worker picks up the task
- [ ] MONITOR shows `SET celery-task-meta-<uuid>` when result stored

---

### Lab 1.3 — Result Backend: Store vs Ignore

**🎯 Goal:** Prove `ignore_result=True` saves memory; TTL prevents leaks.

**💪 Challenge:** Submit both task types, wait for completion, then compare DB 1 key counts and inspect the TTL countdown.

<details>
<summary>✅ Solution</summary>

```bash
# Run the guided lab
uv run python scripts/submit_tasks.py 1.3

# Check result keys with TTLs
bash scripts/trace_redis.sh results

# Watch TTL count down for store_result
bash scripts/trace_redis.sh ttl <store_result-uuid>
sleep 10
bash scripts/trace_redis.sh ttl <store_result-uuid>
# TTL should decrease by ~10 between runs
```
</details>

**✓ Verification:**
- [ ] After both tasks complete: DB 1 grew by exactly **1** key
- [ ] `fire_and_forget` task ID appears **nowhere** in DB 1
- [ ] `store_result` task has TTL ~3600 and counting down
- [ ] `fire_and_forget.ignore_result is True` in Django shell

---

### Lab 1.4 — Inspect the Task Request Context

**🎯 Goal:** Understand every field in the task request object.

<details>
<summary>✅ Solution</summary>

```bash
uv run python scripts/submit_tasks.py 1.4
```

Or interactively:
```python
from demo.tasks import inspect_request
r = inspect_request.delay(echo="my-trace-id")
print(r.get(timeout=10))
```

Key learning: `hostname`, `queue`, and `retries` come from the message  
envelope. In Module 8, you'll add `correlation_id` to `headers` the same way.
</details>

**✓ Verification:**
- [ ] Result contains `task_id`, `hostname`, `queue`, `retries`, `pid`
- [ ] `retries` equals 0 (first attempt)
- [ ] `echo` value round-trips correctly through JSON serialisation

---

### Lab 1.5 — Queue Depth Visibility (prefetch=1 proof)

**🎯 Goal:** Confirm `prefetch_multiplier=1` keeps all queued tasks visible and monitorable.

**🔧 Setup:**
```bash
# Single-concurrency worker — makes the effect obvious
uv run celery -A celery_playground worker --loglevel=info --concurrency=1 --prefetch-multiplier=1
```

**💪 Challenge:** Submit 8 tasks (15s each). Immediately check Flower and Redis — you should see Active=1 and 7 tasks still visible in the queue.

<details>
<summary>✅ Solution</summary>

```bash
uv run python scripts/submit_tasks.py 1.5

# Watch queue drain in real time (separate terminal)
watch -n3 "docker-compose exec -T redis redis-cli LLEN celery"
```

**Flower should show:**
- Active: 1
- Queue `celery` depth: 7 → 6 → 5 … → 0 (every 15 seconds)
</details>

**✓ Verification:**
- [ ] Active=1 in Flower immediately after submission
- [ ] Queue depth shows 7 remaining tasks (not hidden by prefetch)
- [ ] Depth decreases by 1 every ~15 seconds

---

## 📊 Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `r.get()` hangs | Worker not running | `uv run celery -A celery_playground worker --loglevel=info` |
| TTL shows `-1` | `CELERY_RESULT_EXPIRES` not set | Verify `= 3600` in settings.py |
| STARTED state never appears | `track_started` not set | Check `CELERY_TASK_TRACK_STARTED = True` in settings.py |
| `LRANGE celery 0 0` empty | Worker too fast | Stop worker before submitting |
| Flower shows no tasks | Wrong result backend URL | Check `CELERY_RESULT_BACKEND` matches docker-compose |

---

## 📖 Reference

- [Celery Message Protocol v2](https://docs.celeryq.dev/en/stable/internals/protocol.html)
- [Task States](https://docs.celeryq.dev/en/stable/userguide/tasks.html#task-states)
- [Result Backends](https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-result-backend-settings)
- [Serialization](https://docs.celeryq.dev/en/stable/userguide/calling.html#serializers)

---

## ✅ Module Completion Checklist

- [ ] **Lab 1.1** — observed all 4 states in Flower (PENDING, STARTED, SUCCESS, FAILURE)
- [ ] **Lab 1.2** — decoded a raw JSON message envelope from Redis
- [ ] **Lab 1.3** — proved fire-and-forget uses zero Redis memory; TTL countdown confirmed
- [ ] **Lab 1.4** — inspected every field in the task request context
- [ ] **Lab 1.5** — confirmed `prefetch_multiplier=1` makes all 7 queued tasks visible
- [ ] **29 tests passing** — `uv run pytest tests/test_module_01_architecture.py tests/test_module_00_baseline.py -v`
- [ ] **Can draw the 5-layer architecture** from memory with failure modes
- [ ] **Can explain the visibility timeout trap** (what breaks, what fixes it)

**Self-assessment:** A task takes 2 hours. `visibility_timeout=3600`. What happens at T+60 min and how do you fix it?

---

## 🎯 Key Takeaways

1. **Every `.delay()` becomes a Redis `LPUSH`** — readable with redis-cli
2. **Task body is `base64(JSON([args, kwargs, options]))`** — plain text, no magic
3. **`ignore_result=True` eliminates the result key entirely** — use for fire-and-forget
4. **`visibility_timeout` must exceed your longest task** — prevents duplicate execution
5. **`track_started=True` makes STARTED state visible** — essential for debugging
6. **The 5 layers each have distinct failure modes** — know which layer failed
7. **Pickle is banned** — JSON only, always, forever

---

[← Module 0](../../tree/section-0-baseline-environment) | [Course Index](../../tree/master) | [Module 2 →](../../tree/section-2-worker-internals)


---

## 📚 Learning Objectives

By completing this module, you will:

- ✅ Understand when to use Celery (and when not to)
- ✅ Master the **10 Production Golden Rules**
- ✅ Set up a baseline Celery environment with Django, Redis, and Flower
- ✅ Verify complete message flow: Django → Redis → Worker → Result
- ✅ Understand the production mindset for distributed task processing

---

## 🎯 Key Concepts

### When to Use Celery - Decision Framework

**Core Rule:** Celery is for work that **must not block the HTTP response cycle**. If a user is waiting on the result, you don't need Celery—you need a faster synchronous operation.

#### ✅ Use Celery For

- **Email / SMS / Push notifications** - Fire and forget
- **File processing** - CSV imports, image resize, video transcoding
- **External API calls** - Webhooks, third-party sync
- **Data imports and exports** - Bulk operations
- **Scheduled background jobs** - Cleanup, reports, analytics
- **Report generation** - PDF creation, data aggregation

#### ❌ Do NOT Use Celery When

- **Execution must complete < 100ms** - Latency-sensitive operations
- **Real-time streaming required** - Use Kafka or Server-Sent Events instead
- **Simple scheduling only** - Use cron or APScheduler (less overhead)
- **Task output needed immediately** - Keep it synchronous
- **Strong ordering guarantees required** - Use a database queue
- **Fan-out to thousands of microtasks** - Consider a stream processor

---

### The 10 Production Golden Rules

These aren't suggestions—they're the difference between a stable system and 3am pages.

| # | Rule | Why It Matters |
|---|------|----------------|
| **1** | Tasks MUST be idempotent | They will run more than once. Design for it. |
| **2** | Always enable `acks_late=True` | Otherwise a crashed worker = a lost task. |
| **3** | `prefetch_multiplier=1` for long tasks | Default=4 causes invisible task starvation. |
| **4** | `visibility_timeout` > max task duration | Redis will re-queue running tasks if timeout too short. |
| **5** | Separate queues by workload type | One slow task type must never starve fast tasks. |
| **6** | Set time limits on every task | Tasks that hang will freeze a worker forever. |
| **7** | Use JSON serializer only, never pickle | pickle = arbitrary code execution vulnerability. |
| **8** | Run exactly one Beat instance | Two Beats = every scheduled task runs twice. |
| **9** | Monitor queue depth and failure rate | Silent failures are the most dangerous failures. |
| **10** | `terminationGracePeriod` > max task duration | K8s rolling updates will kill tasks mid-flight. |

**Memorize these.** Every module reinforces them.

---

## 🔧 Changes in This Module

### New Files Created

- `.gitignore` - Python/Django/Celery ignores
- `README.md` - Course overview and module index
- `COURSE_GUIDE.md` - How to use this course
- `docs/production_checklist.md` - 24-item production readiness checklist
- `production_patterns/` - New Django app for advanced patterns (empty for now)
- `tests/` - Test suite structure

### Modified Files

#### `pyproject.toml`
Added comprehensive dependencies:
```toml
dependencies = [
    "celery>=5.6.2",
    "django-celery-beat>=2.7.0",  # For scheduling (Module 7)
    "celery-once>=3.0.1",  # For idempotency (Module 3)
    "flower>=2.0.1",  # For monitoring (all modules)
    # ... and more
]
```

#### `docker-compose.yml`
Added Flower for monitoring:
```yaml
flower:
  image: mher/flower:2.0
  environment:
    - CELERY_BROKER_URL=redis://redis:6379/0
  ports:
    - "5555:5555"
```

#### `celery_playground/celery.py`
Production-critical defaults:
```python
app.conf.update(
    task_acks_late=True,  # Golden Rule #2
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # Golden Rule #3
)
```

#### `celery_playground/settings.py`
Complete Celery configuration following Golden Rules:
```python
# Serialization Security (Golden Rule #7)
CELERY_TASK_SERIALIZER = "json"  # NEVER pickle
CELERY_ACCEPT_CONTENT = ["json"]

# Task Reliability (Golden Rule #2)
CELERY_TASK_ACKS_LATE = True

# Worker Performance (Golden Rule #3)
CELERYD_PREFETCH_MULTIPLIER = 1

# Result TTL - prevent memory leak
CELERY_RESULT_EXPIRES = 3600  # 1 hour

# Redis Transport (Golden Rule #4)
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 86400,  # 24 hours
}
```

---

## 🔬 Lab Exercises

### Lab 0.1: Environment Setup & Verification

**🎯 Goal:** Set up a complete Celery environment and verify message flow.

**🔧 Setup:**

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Start Redis + Flower
docker-compose up -d

# 3. Verify services are running
docker-compose ps
# Expected: redis (healthy), flower (running)

# 4. Check Flower UI
open http://localhost:5555
# Credentials: admin / admin123
```

**💪 Challenge:**

1. Start a Celery worker in one terminal
2. Submit a task from Django shell in another terminal
3. Observe the task execution in:
   - Worker logs
   - Flower UI (http://localhost:5555)
   - Redis (using redis-cli)

**💡 Hints:**

<details>
<summary>Hint 1: How to start the worker</summary>

```bash
celery -A celery_playground worker --loglevel=info
```

Look for: "celery@hostname ready" message
</details>

<details>
<summary>Hint 2: How to submit a task</summary>

```bash
python manage.py shell
```

In the shell:
```python
from demo.tasks import slow_add
result = slow_add.delay(10, 20)
print(f"Task ID: {result.id}")
print(f"Result: {result.get(timeout=35)}")
```
</details>

<details>
<summary>Hint 3: How to check Redis</summary>

```bash
docker-compose exec redis redis-cli

# In Redis CLI:
KEYS celery*
LLEN celery  # Check queue length
GET celery-task-meta-<task-id>  # Check result (use your task ID)
```
</details>

**✅ Solution:**

<details>
<summary>Complete Solution</summary>

**Terminal 1 - Start Worker:**
```bash
celery -A celery_playground worker --loglevel=info
```

**Terminal 2 - Submit Task:**
```bash
python manage.py shell
```
```python
from demo.tasks import slow_add

# Submit task
result = slow_add.delay(10, 20)
print(f"Task ID: {result.id}")
print(f"Status: {result.status}")

# Wait for result (task takes 30 seconds)
final_result = result.get(timeout=35)
print(f"Result: {final_result}")  # Should print 30
```

**Terminal 3 - Monitor Redis:**
```bash
docker-compose exec redis redis-cli

# Watch commands in real-time
MONITOR

# You should see:
# - LPUSH (task added to queue)
# - BRPOP (worker pulling task)
# - SET (result stored)
```

**Browser - Flower UI:**
- Navigate to: http://localhost:5555
- Login: admin / admin123
- Click "Tasks" → See your task
- Check status, runtime, result
</details>

**✓ Verification Checklist:**

- [ ] Worker starts without errors
- [ ] Task appears in Flower UI
- [ ] Worker logs show task execution with PID
- [ ] Task completes successfully (returns 30 after ~30 seconds)
- [ ] Redis shows task metadata

---

### Lab 0.2: Golden Rules Validation

**🎯 Goal:** Verify that your environment follows the Golden Rules.

**💪 Challenge:**

Write a Python script that validates all Golden Rule configurations:

1. Check that task serializer is JSON (not pickle)
2. Verify `acks_late=True`
3. Verify `prefetch_multiplier=1`
4. Verify `visibility_timeout` is set appropriately
5. Check that accept_content only includes 'json'

**💡 Hints:**

<details>
<summary>Hint: How to access Celery app config</summary>

```python
from celery_playground.celery import app

# Access configuration
print(app.conf.task_serializer)
print(app.conf.task_acks_late)
print(app.conf.worker_prefetch_multiplier)
```
</details>

**✅ Solution:**

<details>
<summary>Complete Solution</summary>

Create `scripts/validate_golden_rules.py`:

```python
#!/usr/bin/env python
"""
Validate that Celery configuration follows the 10 Golden Rules.
"""
from celery_playground.celery import app
from django.conf import settings


def validate_golden_rules():
    """Validate Golden Rules configuration."""
    rules_passed = 0
    rules_failed = 0
    
    print("=" * 70)
    print("CELERY PRODUCTION GOLDEN RULES VALIDATION")
    print("=" * 70)
    
    # Rule #2: acks_late
    if app.conf.task_acks_late:
        print("✅ Rule #2: task_acks_late = True")
        rules_passed += 1
    else:
        print("❌ Rule #2: task_acks_late should be True")
        rules_failed += 1
    
    # Rule #3: prefetch_multiplier
    if app.conf.worker_prefetch_multiplier == 1:
        print("✅ Rule #3: worker_prefetch_multiplier = 1")
        rules_passed += 1
    else:
        print(f"❌ Rule #3: worker_prefetch_multiplier = {app.conf.worker_prefetch_multiplier} (should be 1)")
        rules_failed += 1
    
    # Rule #4: visibility_timeout
    broker_opts = getattr(settings, 'CELERY_BROKER_TRANSPORT_OPTIONS', {})
    vis_timeout = broker_opts.get('visibility_timeout', 3600)
    if vis_timeout >= 3600:
        print(f"✅ Rule #4: visibility_timeout = {vis_timeout}s (>= 1 hour)")
        rules_passed += 1
    else:
        print(f"⚠️  Rule #4: visibility_timeout = {vis_timeout}s (consider increasing)")
    
    # Rule #7: JSON serializer (no pickle)
    if app.conf.task_serializer == 'json':
        print("✅ Rule #7: task_serializer = 'json'")
        rules_passed += 1
    else:
        print(f"❌ Rule #7: task_serializer = '{app.conf.task_serializer}' (should be 'json')")
        rules_failed += 1
    
    if app.conf.result_serializer == 'json':
        print("✅ Rule #7: result_serializer = 'json'")
        rules_passed += 1
    else:
        print(f"❌ Rule #7: result_serializer = '{app.conf.result_serializer}' (should be 'json')")
        rules_failed += 1
    
    if 'pickle' not in app.conf.accept_content:
        print("✅ Rule #7: 'pickle' not in accept_content")
        rules_passed += 1
    else:
        print("❌ Rule #7: 'pickle' in accept_content (SECURITY RISK!)")
        rules_failed += 1
    
    # Additional checks
    if app.conf.task_reject_on_worker_lost:
        print("✅ Extra: task_reject_on_worker_lost = True")
        rules_passed += 1
    
    if app.conf.task_track_started:
        print("✅ Extra: task_track_started = True")
        rules_passed += 1
    
    print("=" * 70)
    print(f"PASSED: {rules_passed} | FAILED: {rules_failed}")
    print("=" * 70)
    
    if rules_failed == 0:
        print("🎉 All critical rules validated! You're on the right track.")
        return True
    else:
        print("⚠️  Some rules failed. Review your configuration.")
        return False


if __name__ == '__main__':
    import django
    django.setup()
    validate_golden_rules()
```

Run it:
```bash
python scripts/validate_golden_rules.py
```

Expected output:
```
======================================================================
CELERY PRODUCTION GOLDEN RULES VALIDATION
======================================================================
✅ Rule #2: task_acks_late = True
✅ Rule #3: worker_prefetch_multiplier = 1
✅ Rule #4: visibility_timeout = 86400s (>= 1 hour)
✅ Rule #7: task_serializer = 'json'
✅ Rule #7: result_serializer = 'json'
✅ Rule #7: 'pickle' not in accept_content
✅ Extra: task_reject_on_worker_lost = True
✅ Extra: task_track_started = True
======================================================================
PASSED: 8 | FAILED: 0
======================================================================
🎉 All critical rules validated! You're on the right track.
```
</details>

**✓ Verification:**

- [ ] Script runs without errors
- [ ] All rules show ✅ (green checkmarks)
- [ ] No ❌ (red X) marks for critical rules

---

### Lab 0.3: Run the Test Suite

**🎯 Goal:** Validate your setup using automated tests.

**🔧 Setup:**

```bash
# Install test dependencies
pip install -e ".[dev]"
```

**💪 Challenge:**

Run the Module 0 test suite and ensure all tests pass.

**✅ Solution:**

```bash
# Run Module 0 tests
pytest tests/test_module_00_baseline.py -v

# Expected output:
# test_task_execution PASSED
# test_task_serialization PASSED
# test_acks_late_enabled PASSED
# test_prefetch_multiplier PASSED
# test_reject_on_worker_lost PASSED
```

**✓ Verification:**

- [ ] All 5 tests pass
- [ ] No failures or errors
- [ ] pytest returns exit code 0

---

## 📊 Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| **"Connection refused" error** | Redis not running | `docker-compose up -d redis` |
| **Worker doesn't start** | Import errors | Check that Django app is in PYTHONPATH: `export PYTHONPATH=.` |
| **Tasks not appearing in Flower** | Flower not connected to correct broker | Check `CELERY_BROKER_URL` matches in all places |
| **"Task not found" error** | Worker not discovering tasks | Ensure `app.autodiscover_tasks()` in celery.py |
| **Flower login fails** | Wrong credentials | Use `admin` / `admin123` (see docker-compose.yml) |

---

## 📖 Reference

- [Celery Documentation - First Steps](https://docs.celeryq.dev/en/stable/getting-started/first-steps-with-celery.html)
- [Django-Celery Integration](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Production Checklist](../docs/production_checklist.md)

---

## ✅ Module Completion Checklist

Before moving to Module 1, ensure:

- [ ] **All labs completed** - Labs 0.1, 0.2, 0.3
- [ ] **All tests passing** - `pytest tests/test_module_00_baseline.py`
- [ ] **Environment verified** - Worker, Redis, Flower all running
- [ ] **Golden Rules understood** - Can explain each of the 10 rules
- [ ] **Can submit and monitor tasks** - Comfortable with workflow
- [ ] **Ready for next module** - Understand message flow basics

**Self-assessment question:** Can you explain to someone else why `acks_late=True` prevents task loss?

---

## 🎯 Key Takeaways

1. **Celery is for async work that shouldn't block HTTP responses** - Not for everything
2. **The 10 Golden Rules prevent 90% of production incidents** - Memorize them
3. **Golden Rule #2, #3, #7 are non-negotiable** - acks_late, prefetch=1, JSON only
4. **Flower gives real-time visibility** - Essential for debugging
5. **Message flow: Django → Redis → Worker → Result** - Understand each step

---

**🎉 Congratulations!** You've completed Module 0 and set up a production-ready baseline.

[**Course Index**](../README.md) | [**Next: Module 1 - Task Lifecycle →**](../../tree/section-1-task-lifecycle)


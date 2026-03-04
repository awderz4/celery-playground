# Module 7 — Scheduling & django-celery-beat

> **Branch:** `section-7-beat-scheduling`  
> **Golden Rule #8:** Run exactly ONE Beat instance

---

## Key Concepts

- Beat only **enqueues** tasks — workers execute them
- Beat **never** backfills missed runs after downtime
- Two Beat instances = **every task runs twice**
- `DatabaseScheduler` allows dynamic schedule changes without restart
- Kubernetes: `strategy: Recreate` + `replicas: 1` (non-negotiable)

---

## Beat Kubernetes Anti-Pattern

```yaml
# BAD — default RollingUpdate:
# New Beat starts BEFORE old one stops → 30-60s overlap → double execution
strategy:
  type: RollingUpdate  # ← NEVER for Beat

# GOOD:
strategy:
  type: Recreate       # old pod killed first, then new one starts
replicas: 1            # always exactly 1
```

---

## Dynamic Schedules

```python
from demo.tasks_module_07 import schedule_user_report, disable_user_report

# Create per-user schedule (no Beat restart required)
schedule_user_report(user_id=42, hour=8)   # daily at 08:00 UTC

# Disable it
disable_user_report(user_id=42)

# Emergency: pause ALL scheduled tasks
from demo.tasks_module_07 import pause_all_scheduled_tasks
pause_all_scheduled_tasks()
```

---

## Labs

### Lab 7a — Beat Execution

```bash
uv run celery -A celery_playground worker -Q default -l info &
uv run celery -A celery_playground beat \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --max-interval 30 -l info
# Observe: heartbeat_task runs every 30s
```

### Lab 7b — Duplicate Execution (Anti-Pattern Demo)

```bash
# Start TWO Beat instances simultaneously
uv run celery -A celery_playground beat -l info &
uv run celery -A celery_playground beat -l info &
# Count task executions — they double
```

### Lab 7c — Dynamic Schedule

```bash
uv run python manage.py shell -c "
from demo.tasks_module_07 import schedule_user_report
schedule_user_report(user_id=1, hour=0)  # every midnight
print('Schedule created — no Beat restart needed')
"
```

---

## Run Tests

```bash
uv run pytest tests/test_module_07_beat.py -v
```


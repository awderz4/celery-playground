# 🚀 Quick Start Guide - Module 0

## Prerequisites Checklist

- [ ] Python 3.13+ installed
- [ ] Docker & Docker Compose installed
- [ ] Git installed
- [ ] This repository cloned

## 5-Minute Setup

### Step 1: Checkout Module 0

```bash
git checkout section-0-baseline-environment
```

### Step 2: Install Dependencies

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install all dependencies (creates/updates .venv automatically)
uv sync --all-extras

# Verify install
uv pip list | grep celery
```

### Step 3: Start Infrastructure

```bash
# Start Redis and Flower
docker-compose up -d

# Verify services are running
docker-compose ps
```

Expected output:
```
NAME                           STATUS
celery-playground-flower       running
celery-playground-redis        running (healthy)
```

### Step 4: Validate Configuration

```bash
# Run the Golden Rules validation script
uv run python scripts/validate_golden_rules.py
```

Expected output: All ✅ (green checkmarks)

### Step 5: Run Tests

```bash
# Run Module 0 test suite
uv run pytest tests/test_module_00_baseline.py -v
```

Expected: 5 tests PASSED

### Step 6: Start a Worker

```bash
# In a new terminal
uv run celery -A celery_playground worker --loglevel=info
```

Look for: `celery@hostname ready.`

### Step 7: Submit Your First Task

```bash
# In another terminal
uv run python manage.py shell
```

In the Python shell:
```python
from demo.tasks import slow_add

# Submit a task
result = slow_add.delay(10, 20)
print(f"Task ID: {result.id}")

# Wait for result (task takes 30 seconds)
final = result.get(timeout=35)
print(f"Result: {final}")  # Should print 30
```

### Step 8: Check Flower UI

Open in browser: http://localhost:5555

Login: `admin` / `admin123`

Navigate to "Tasks" to see your task execution!

---

## Common Issues

### "Connection refused" Error

**Cause:** Redis not running

**Fix:**
```bash
docker-compose up -d redis
docker-compose ps  # Verify it's healthy
```

### Worker Doesn't Start

**Cause:** Import errors or missing dependencies

**Fix:**
```bash
# Reinstall dependencies
uv sync --all-extras

# Try again
uv run celery -A celery_playground worker --loglevel=info
```

### Tests Fail

**Cause:** Dependencies not installed

**Fix:**
```bash
uv sync --all-extras
uv run pytest tests/test_module_00_baseline.py -v
```

---

## What's Next?

After completing Module 0:

1. ✅ Complete all 3 labs in MODULE_README.md
2. ✅ Ensure all tests pass
3. ✅ Review the 10 Golden Rules
4. ✅ Read the production checklist

Then move to Module 1 (when created):
```bash
git checkout section-1-task-lifecycle
```

---

## Key Files

- `README.md` - Course overview (12 modules)
- `COURSE_GUIDE.md` - How to use this course
- `MODULE_README.md` - Module 0 instructions & labs
- `docs/production_checklist.md` - Production readiness (24 items)
- `docs/worker_commands_reference.md` - Worker CLI reference
- `scripts/validate_golden_rules.py` - Configuration validator

---

## The 10 Golden Rules (Memorize These!)

1. Tasks MUST be idempotent
2. Always enable `acks_late=True`
3. `prefetch_multiplier=1` for long tasks
4. `visibility_timeout` > max task duration
5. Separate queues by workload type
6. Set time limits on every task
7. Use JSON serializer only, never pickle
8. Run exactly one Beat instance
9. Monitor queue depth and failure rate
10. `terminationGracePeriod` > max task duration

---

## Help & Support

- Read `COURSE_GUIDE.md` for detailed navigation instructions
- Check `docs/troubleshooting_guide.md` (when created) for common issues
- Review the module README for lab instructions
- Run validation script to check configuration

---

**Ready to master production Celery?** Start with Module 0! 🎓


# Celery Task Detection - Fixed Issues

## Problems That Were Fixed

### 1. ❌ Demo app not in INSTALLED_APPS
**Issue**: The `demo` app was not registered in Django's `INSTALLED_APPS`.
**Why it matters**: Celery's `autodiscover_tasks()` only searches for tasks in installed Django apps.
**Fix**: Added `'demo'` to `INSTALLED_APPS` in `settings.py`

### 2. ❌ Wrong module name in celery.py
**Issue**: The celery.py file referenced `"project.settings"` instead of `"celery_playground.settings"`
**Why it matters**: Django couldn't find the settings module, causing import errors.
**Fix**: Updated to use the correct module name `"celery_playground.settings"`

### 3. ❌ Problematic wildcard import in apps.py
**Issue**: `from demo import *` in the `DemoConfig.ready()` method
**Why it matters**: This can cause circular imports and other issues.
**Fix**: Removed the wildcard import

## Verification

Your tasks are now detected! Running the worker shows:

```
[tasks]
  . demo.tasks.slow_add
```

## How to Run Celery

### 1. Start Redis (if not running)
```bash
docker-compose up -d
```

### 2. Start Celery Worker
```bash
celery -A celery_playground worker --loglevel=info
```

### 3. Test Your Task

In Django shell or a view:
```python
from demo.tasks import slow_add

# Call asynchronously
result = slow_add.delay(4, 5)

# Check result
print(result.get())  # Will wait and return 9
```

Or check status:
```python
result = slow_add.delay(4, 5)
print(result.ready())  # False while running, True when done
print(result.status)   # 'PENDING', 'SUCCESS', etc.
```

## Quick Commands

### List registered tasks
```bash
celery -A celery_playground inspect registered
```

### Check active tasks
```bash
celery -A celery_playground inspect active
```

### Purge all tasks
```bash
celery -A celery_playground purge
```

### Monitor tasks (events)
```bash
celery -A celery_playground events
```

## File Structure

```
celery_playground/
├── celery_playground/
│   ├── __init__.py          # Imports celery app
│   ├── celery.py            # Celery configuration
│   └── settings.py          # Django settings with CELERY_* configs
└── demo/
    ├── apps.py              # App configuration
    └── tasks.py             # Your Celery tasks (@shared_task)
```

## Key Points

1. **Always use `@shared_task`** decorator for tasks in Django apps
2. **Apps must be in `INSTALLED_APPS`** for autodiscovery to work
3. **Import the celery app** in `__init__.py` to ensure it loads on Django startup
4. **Use consistent naming** - module names must match throughout the project


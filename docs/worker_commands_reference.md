# 📘 Worker Commands Reference

Complete reference for Celery worker command-line options and configurations.

---

## 🚀 Basic Worker Commands

### Start a Worker

```bash
# Basic worker
uv run celery -A celery_playground worker --loglevel=info

# With custom hostname
uv run celery -A celery_playground worker --hostname=worker1@%h --loglevel=info

# Background mode (daemon)
uv run celery -A celery_playground worker --detach --pidfile=/var/run/celery/worker.pid
```

### Worker Options

| Option | Description | Example |
|--------|-------------|---------|
| `-A, --app` | Celery app instance | `-A celery_playground` |
| `-l, --loglevel` | Logging level | `--loglevel=info` (debug, info, warning, error, critical) |
| `-n, --hostname` | Worker hostname | `-n worker1@%h` (%h = hostname) |
| `-Q, --queues` | Queues to consume | `-Q critical,default` |
| `-c, --concurrency` | Number of worker processes/threads | `-c 4` |
| `-P, --pool` | Pool implementation | `-P prefork` (prefork, gevent, eventlet, solo, threads) |

---

## ⚙️ Production Worker Configurations

### Default Worker (CPU-bound, general purpose)

```bash
uv run celery -A celery_playground worker \
  --loglevel=info \
  --concurrency=4 \
  --pool=prefork \
  -Q default \
  --max-tasks-per-child=200 \
  --max-memory-per-child=400000 \
  --prefetch-multiplier=1 \
  --hostname=worker-default@%h
```

**Use for:** General background jobs, data processing, reports

**Golden Rules Applied:**
- `--prefetch-multiplier=1` - Rule #3
- `--max-tasks-per-child=200` - Prevents memory leaks
- `--pool=prefork` - CPU parallelism

---

### Notifications Worker (I/O-bound, high concurrency)

```bash
uv run celery -A celery_playground worker \
  --loglevel=info \
  --concurrency=100 \
  --pool=gevent \
  -Q notifications \
  --prefetch-multiplier=1 \
  --hostname=worker-notifications@%h
```

**Use for:** Email sending, SMS, push notifications, webhooks

**Why gevent:**
- 100+ concurrent connections
- Lightweight (single process)
- Perfect for I/O waiting (network calls)

**Requirements:**
```bash
pip install gevent
```

---

### Media Worker (CPU-heavy, low concurrency)

```bash
uv run celery -A celery_playground worker \
  --loglevel=info \
  --concurrency=2 \
  --pool=prefork \
  -Q media \
  --max-tasks-per-child=50 \
  --max-memory-per-child=800000 \
  --prefetch-multiplier=1 \
  --hostname=worker-media@%h
```

**Use for:** Image resize, video transcoding, PDF generation

**Why low concurrency:**
- CPU-intensive work
- High memory per task
- Prevents system overload

---

### Imports Worker (memory-heavy, single process)

```bash
uv run celery -A celery_playground worker \
  --loglevel=info \
  --concurrency=1 \
  --pool=prefork \
  -Q imports \
  --max-tasks-per-child=10 \
  --max-memory-per-child=1000000 \
  --prefetch-multiplier=1 \
  --hostname=worker-imports@%h
```

**Use for:** CSV imports, Excel processing, bulk data operations

**Why concurrency=1:**
- One large file at a time
- Prevents memory exhaustion
- max-tasks-per-child=10 for aggressive recycling

---

### Critical Worker (dedicated, monitored)

```bash
uv run celery -A celery_playground worker \
  --loglevel=info \
  --concurrency=4 \
  -Q critical \
  --prefetch-multiplier=1 \
  --time-limit=300 \
  --soft-time-limit=270 \
  --hostname=worker-critical@%h
```

**Use for:** Payment processing, auth operations, critical business logic

**Special characteristics:**
- Dedicated queue (Rule #5)
- Strict time limits (Rule #6)
- High priority monitoring

---

## 🔄 Beat (Scheduler) Commands

### Start Beat

```bash
# With Django-Celery-Beat (database scheduler)
uv run celery -A celery_playground beat \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler \
  --max-interval 30 \
  --loglevel=info \
  --pidfile=/tmp/celerybeat.pid
```

### Beat Options

| Option | Description | Default |
|--------|-------------|---------|
| `--scheduler` | Scheduler class | `celery.beat:PersistentScheduler` |
| `--max-interval` | Max seconds to sleep between re-checking schedule | 300s (5 min) |
| `--pidfile` | Path to PID file | None |

**⚠️ Golden Rule #8:** Run exactly ONE Beat instance. Use `replicas: 1` in Kubernetes.

---

## 🌸 Flower (Monitoring) Commands

```bash
# Start Flower
uv run celery -A celery_playground flower \
  --port=5555 \
  --basic-auth=admin:${FLOWER_PASSWORD} \
  --max-tasks=50000 \
  --persistent=True \
  --db=/var/lib/flower/flower.db

# With authentication file
uv run celery -A celery_playground flower \
  --port=5555 \
  --basic-auth=/etc/flower/users.txt
```

### Flower Options

| Option | Description |
|--------|-------------|
| `--port` | HTTP port (default: 5555) |
| `--basic-auth` | username:password or file path |
| `--max-tasks` | Max tasks to keep in memory |
| `--persistent` | Enable persistent mode |
| `--db` | Path to database file |

---

## 🔍 Inspection Commands

### Active Tasks

```bash
# List active tasks on all workers
uv run celery -A celery_playground inspect active

# Specific worker
uv run celery -A celery_playground inspect active -d celery@worker1
```

### Reserved Tasks

```bash
# Tasks pre-fetched but not yet started
uv run celery -A celery_playground inspect reserved
```

### Worker Statistics

```bash
# Get worker stats (pool size, tasks completed, etc.)
uv run celery -A celery_playground inspect stats
```

### Registered Tasks

```bash
# List all registered tasks
uv run celery -A celery_playground inspect registered
```

### Queue Lengths

```bash
# Check how many tasks are in each queue
uv run celery -A celery_playground inspect active_queues
```

---

## 🎛️ Control Commands

### Shutdown Worker

```bash
# Graceful shutdown
uv run celery -A celery_playground control shutdown

# Specific worker
uv run celery -A celery_playground control shutdown -d celery@worker1
```

### Change Rate Limit

```bash
# Set rate limit on specific task (no restart needed!)
uv run celery -A celery_playground control rate_limit \
  myapp.tasks.send_email \
  '10/m'
```

### Cancel Consumer

```bash
# Stop consuming from a queue
uv run celery -A celery_playground control cancel_consumer default

# Resume
uv run celery -A celery_playground control add_consumer default
```

### Purge Queue

```bash
# ⚠️ DANGER: Delete all tasks in all queues
uv run celery -A celery_playground purge

# Specific queue
uv run celery -A celery_playground purge -Q imports

# With confirmation
uv run celery -A celery_playground purge -f
```

---

## 🧪 Advanced Worker Options

### Memory Management

```bash
uv run celery -A celery_playground worker \
  --max-tasks-per-child=200 \
  --max-memory-per-child=400000 \
  --prefetch-multiplier=1
```

### Time Limits

```bash
uv run celery -A celery_playground worker \
  --time-limit=300 \
  --soft-time-limit=270
```

### Autoscaling

```bash
# Auto-scale between 2 and 10 workers
uv run celery -A celery_playground worker --autoscale=10,2

# Format: --autoscale=MAX,MIN
```

**Note:** For Kubernetes, use HPA/KEDA instead of built-in autoscaler.

---

## 📊 Performance Tuning Options

### Prefetch Multiplier (Golden Rule #3)

```bash
# Production (long-running tasks)
uv run celery -A celery_playground worker --prefetch-multiplier=1

# High-throughput short tasks (advanced use only)
uv run celery -A celery_playground worker --prefetch-multiplier=4
```

**⚠️ Default is 4 - causes invisible task starvation!**

### Pool Options

```bash
# Prefork (CPU-bound)
uv run celery -A celery_playground worker -P prefork -c 4

# Gevent (I/O-bound)
uv run celery -A celery_playground worker -P gevent -c 100

# Eventlet (I/O-bound, alternative to gevent)
uv run celery -A celery_playground worker -P eventlet -c 100

# Threads (mixed workload)
uv run celery -A celery_playground worker -P threads -c 10

# Solo (debugging only - single thread)
uv run celery -A celery_playground worker -P solo
```

---

## 🐛 Debugging Commands

### High Verbosity Logging

```bash
# Debug level logging
uv run celery -A celery_playground worker --loglevel=debug

# With task arguments in logs
uv run celery -A celery_playground worker --loglevel=info -O fair
```

### Single Task for Testing

```bash
# Process only one task then exit
uv run celery -A celery_playground worker --pool=solo --loglevel=debug -c 1
```

### Trace All Events

```bash
# Send task events for monitoring
uv run celery -A celery_playground worker -E

# In another terminal, watch events
uv run celery -A celery_playground events
```

---

## 📦 Multi-Worker Setup

### Running Multiple Worker Types

```bash
# Terminal 1: Critical queue worker
uv run celery -A celery_playground worker -Q critical -n critical@%h -c 2

# Terminal 2: Default queue worker
uv run celery -A celery_playground worker -Q default -n default@%h -c 4

# Terminal 3: Notifications (gevent)
uv run celery -A celery_playground worker -Q notifications -n notifications@%h -P gevent -c 100

# Terminal 4: Beat scheduler
uv run celery -A celery_playground beat -l info
```

### Systemd Service Example

```ini
# /etc/systemd/system/celery-worker@.service
[Unit]
Description=Celery Worker %i
After=network.target redis.target

[Service]
Type=forking
User=celery
Group=celery
WorkingDirectory=/app
ExecStart=/app/.venv/bin/celery -A celery_playground worker \
  -Q %i \
  -n worker-%i@%%h \
  --pidfile=/var/run/celery/worker-%i.pid \
  --logfile=/var/log/celery/worker-%i.log \
  --loglevel=info \
  --detach

[Install]
WantedBy=multi-user.target
```

Usage:
```bash
systemctl start celery-worker@default
systemctl start celery-worker@critical
systemctl start celery-worker@notifications
```

---

## 🔒 Security Best Practices

### Run as Non-Root User

```bash
# Create celery user
sudo useradd -r -s /bin/false celery

# Run worker as celery user
sudo -u celery celery -A celery_playground worker
```

### Limit Worker Permissions

```bash
# Run in restricted directory
cd /app && celery -A celery_playground worker

# With environment restrictions
env -i HOME=/app USER=celery celery -A celery_playground worker
```

---

## ✅ Production Checklist

Before starting workers in production:

- [ ] `--prefetch-multiplier=1` set (Rule #3)
- [ ] `--max-tasks-per-child` configured (prevent memory leaks)
- [ ] `--max-memory-per-child` configured (prevent OOMKill)
- [ ] Correct pool type for workload (prefork vs gevent)
- [ ] Dedicated queues for different workload types (Rule #5)
- [ ] Time limits set for long-running tasks (Rule #6)
- [ ] Monitoring enabled (Flower or events)
- [ ] Only one Beat instance (Rule #8)
- [ ] Workers run as non-root user
- [ ] Logging configured properly

---

## 📖 Quick Reference Table

| Workload Type | Pool | Concurrency | Prefetch | Max Tasks/Child |
|---------------|------|-------------|----------|-----------------|
| CPU-bound     | prefork | = CPU cores | 1 | 200 |
| I/O-bound     | gevent | 50-500 | 1 | ∞ (gevent manages) |
| Mixed         | threads | 4-20 | 1 | 200 |
| Memory-heavy  | prefork | 1-2 | 1 | 10-50 |
| Testing       | solo | 1 | 1 | N/A |

---

## 🔗 Related Documentation

- [Production Settings Template](./production_settings_template.py)
- [Production Checklist](./production_checklist.md)
- [Troubleshooting Guide](./troubleshooting_guide.md)
- [Official Celery Workers Guide](https://docs.celeryq.dev/en/stable/userguide/workers.html)

---

**Pro Tip:** Save commonly-used worker commands as shell aliases or scripts for consistency across your team!

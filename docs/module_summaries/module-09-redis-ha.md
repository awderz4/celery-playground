# Module 9 — Redis Production Architecture

> **Branch:** `section-9-redis-ha`

---

## Key Principle: Separate Broker and Result DBs

```python
# Separate Redis instances (recommended for high load)
CELERY_BROKER_URL    = "redis://redis-broker:6379/0"
CELERY_RESULT_BACKEND = "redis://redis-results:6379/0"

# Separate DBs on same instance (acceptable for medium load)
CELERY_BROKER_URL    = "redis://redis:6379/0"
CELERY_RESULT_BACKEND = "redis://redis:6379/1"
```

| DB | Eviction Policy | Why |
|----|----------------|-----|
| DB 0 (broker) | `noeviction` | Queued tasks must NEVER be evicted |
| DB 1 (results) | `volatile-lru` | Results CAN be evicted after TTL |

---

## Redis Production Config (`redis.conf`)

```
maxmemory 4gb
maxmemory-policy volatile-lru
appendonly yes
appendfsync everysec
rename-command FLUSHALL ''
rename-command DEBUG ''
```

---

## Sentinel HA

```python
CELERY_BROKER_URL = "sentinel://s0:26379;s1:26379;s2:26379/0"
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "master_name": "mymaster",
    "visibility_timeout": 86400,
}
```

Minimum 3 Sentinel nodes for quorum (tolerates 1 failure).

---

## Failure Scenarios

| Scenario | Recovery Time | Data Loss? |
|----------|--------------|------------|
| Redis restart (clean) | 5–30s auto-reconnect | None (AOF) |
| Redis OOM crash | Until restart | Possible |
| Sentinel failover | 5–30s | Minimal |
| Full Redis failure (no HA) | Manual | All queued tasks |

---

## Labs

### Lab 9a — Redis Restart

```bash
docker compose up -d redis
uv run celery -A celery_playground worker -Q default -l info &
uv run python scripts/submit_tasks.py all
docker compose restart redis
# Watch worker logs — automatic reconnect within ~10s
```

### Lab 9b — Eviction Policy

```bash
# Fill Redis to maxmemory with noeviction → tasks fail with OOM error
# Switch to volatile-lru → only result keys evicted, queue intact
```

---

## Run Tests

```bash
uv run pytest tests/test_module_09_redis_ha.py -v
```


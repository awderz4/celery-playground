"""
scripts/submit_tasks.py
=======================
Lab helper: submit tasks for every module and print IDs so you
can track them in Flower / trace_redis.sh.

Usage:
  uv run python scripts/submit_tasks.py [lab]

Module 1 Labs:
  1.1   state transitions (states + failure)
  1.2   serialization payloads
  1.3   result backend (fire-and-forget vs stored)
  1.4   request context inspection
  1.5   queue depth visibility (8 observable tasks)

Module 2 Labs:
  2.1   prefetch starvation demo (8 slow tasks)
  2.2   acks_early vs acks_late comparison
  2.3   worker identity / PID tracking

Module 3 Labs:
  3.1   idempotency — process same invoice twice (DB constraint)
  3.2   retry with exponential backoff + jitter (flaky API)
  3.3   soft_time_limit — CSV job progress saved on timeout

Module 4 Labs:
  4.1   rate-limited SMS tasks (10/min)
  4.2   always-failing task → exhausts retries → dead-letter queue
  4.3   circuit breaker — rapid task submission, watch depth alerts

Module 5 Labs:
  5.1   queue starvation — 10 slow media tasks + 5 emails (same worker)
  5.2   500 notification tasks for KEDA autoscaling demo

Module 6 Labs:
  6.1   leaky_task — watch RSS grow without max_tasks_per_child
  6.2   clean_task — comparison, RSS stays flat
  6.3   memory_spike_task — trigger max_memory_per_child

Module 7 Labs:
  7.1   canary heartbeat task
  7.2   daily report for user_id=42 (dynamic schedule demo)

Module 8 Labs:
  8.1   traced CSV task (OpenTelemetry spans)
  8.2   correlation ID chain: traceable → child

Module 11 Labs:
  11.1  CSV import pipeline (chain: download→parse→validate→save)
  11.2  process_batch group (10 parallel batches)
  11.3  task versioning: old format + new format side by side

  all       run all Module 1 labs
  all2      run all Module 2 labs
  all3      run all Module 3 labs
  all4      run all Module 4 labs
  all5      run all Module 5 labs
  all6      run all Module 6 labs
  all7      run all Module 7 labs
  all8      run all Module 8 labs
  all11     run all Module 11 labs
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_playground.settings")

import django
django.setup()

from demo.tasks import (
    task_with_states, task_that_fails, json_payload_task,
    large_payload_task, fire_and_forget, store_result,
    inspect_request, observable_task,
)
from demo.tasks_module_02 import (
    slow_task, acks_early_task, acks_late_task, worker_identity_task,
)
from demo.tasks_module_03 import (
    process_invoice, call_external_api, process_large_csv,
)
from demo.tasks_module_04 import (
    send_sms, send_bulk_email, always_fails_task as always_fails,
)
from demo.tasks_module_05 import (
    charge_payment, send_email_notification, send_push_notification,
    resize_image, import_csv, starvation_slow_task,
)
from demo.tasks_module_06 import (
    leaky_task, clean_task, memory_spike_task,
)
from demo.tasks_module_07 import (
    canary_heartbeat, daily_report_task,
)
from demo.tasks_module_08 import (
    traced_csv_task, traceable_task, child_task, set_correlation_id,
)
from demo.tasks_module_11 import (
    build_import_pipeline, process_batch, aggregate_results,
    send_email_v1, send_email_v2,
)


def separator(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1
# ─────────────────────────────────────────────────────────────────────────────

def lab_1_1():
    separator("Lab 1.1 — State Transitions")
    print("Submitting task_with_states (duration=8s)…")
    r1 = task_with_states.delay(duration=8)
    print(f"  Task ID : {r1.id}")
    print(f"  State   : {r1.state}  ← should be PENDING")
    print("  → Open Flower, watch it move PENDING→STARTED→SUCCESS")

    print("\nSubmitting task_that_fails…")
    r2 = task_that_fails.delay()
    print(f"  Task ID : {r2.id}")
    print("  → After ~2s it will be FAILURE in Flower with full traceback")


def lab_1_2():
    separator("Lab 1.2 — Serialization & Message Envelope")
    payload = {"user_id": 42, "action": "signup", "timestamp": "2026-03-04T09:00:00Z"}
    r1 = json_payload_task.delay(payload)
    print(f"  json_payload_task  id={r1.id}")
    print("  → Run: bash scripts/trace_redis.sh queue  (see raw JSON envelope)")

    r2 = large_payload_task.delay(size=500)
    print(f"  large_payload_task id={r2.id}")
    print(f"  → After completion: bash scripts/trace_redis.sh ttl {r2.id}")


def lab_1_3():
    separator("Lab 1.3 — Result Backend: fire-and-forget vs stored")
    print("Run before:  bash scripts/trace_redis.sh dbsize")
    r1 = fire_and_forget.delay("hello lab 1.3")
    print(f"  fire_and_forget  id={r1.id}  (no result key created)")
    r2 = store_result.delay(7)
    print(f"  store_result     id={r2.id}  (result key with TTL created)")
    print("\nWaiting 4s…")
    time.sleep(4)
    print("Run after:   bash scripts/trace_redis.sh dbsize")
    print(f"             bash scripts/trace_redis.sh ttl {r2.id}")


def lab_1_4():
    separator("Lab 1.4 — Request Context Inspection")
    r1 = inspect_request.delay(echo="module-1-lab-1.4")
    print(f"  Task ID : {r1.id}")
    try:
        result = r1.get(timeout=10)
        print("\n  ✅ Request context:")
        for k, v in result.items():
            print(f"     {k:<14} = {v}")
    except Exception as e:
        print(f"  ❌ {e}  — is the worker running?")


def lab_1_5():
    separator("Lab 1.5 — Queue Depth Visibility (8 observable tasks)")
    for i in range(1, 9):
        r = observable_task.delay(task_number=i, duration=15)
        print(f"  observable_task #{i}  id={r.id}")
    print("\n  → Flower: Active=1, rest visible in queue")
    print("  → bash scripts/trace_redis.sh queue  (watch depth drop)")


LABS = {"1.1": lab_1_1, "1.2": lab_1_2, "1.3": lab_1_3,
        "1.4": lab_1_4, "1.5": lab_1_5}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2
# ─────────────────────────────────────────────────────────────────────────────

def lab_2_1():
    separator("Lab 2.1 — Prefetch Starvation Demo (8 slow tasks, 20s each)")
    print("STEP 1 — start worker with BAD prefetch=4:")
    print("  uv run celery -A celery_playground worker -Q default \\")
    print("      --concurrency=1 --prefetch-multiplier=4 -l info")
    print()
    for i in range(1, 9):
        r = slow_task.delay(task_number=i, duration=20)
        print(f"  slow_task #{i}  id={r.id}")
    print("\n  → With prefetch=4: tasks 2–4 are invisible to queue")
    print("  → Kill worker:  uv run python scripts/kill_worker.py --delay 15")
    print("  → redis-cli -p 6380 LLEN celery  (count surviving tasks)")
    print()
    print("STEP 2 — repeat with prefetch=1:")
    print("  uv run celery -A celery_playground worker -Q default \\")
    print("      --concurrency=1 --prefetch-multiplier=1 -l info")


def lab_2_2():
    separator("Lab 2.2 — acks_early vs acks_late")
    for i in range(1, 3):
        r = acks_early_task.delay(task_number=i, duration=25)
        print(f"  acks_EARLY #{i}  id={r.id}  ← will be LOST on kill")
    for i in range(1, 3):
        r = acks_late_task.delay(task_number=i, duration=25)
        print(f"  acks_LATE  #{i}  id={r.id}  ← will be RE-QUEUED on kill")
    print()
    print("Kill worker:  uv run python scripts/kill_worker.py")
    print("Check queue: redis-cli -p 6380 LLEN celery")
    print("  → Expect 2 tasks (acks_late only, the acks_early ones are gone)")


def lab_2_3():
    separator("Lab 2.3 — Worker Identity / PID Tracking")
    count = 15
    results = []
    for i in range(count):
        r = worker_identity_task.delay(task_number=i)
        results.append(r)
        print(f"  worker_identity #{i:2d}  id={r.id}")
    print(f"\nWaiting for {count} results (up to 60s)…")
    pids_seen = []
    for i, r in enumerate(results):
        try:
            res = r.get(timeout=60)
            pids_seen.append(res["pid"])
            print(f"  Task #{i:2d}  pid={res['pid']}  worker={res['worker']}")
        except Exception as e:
            print(f"  Task #{i:2d}  ERROR: {e}")
            break
    if pids_seen:
        unique = len(set(pids_seen))
        print(f"\n✅ Unique PIDs: {unique}")
        print("  → >1 PID means worker recycled (max_tasks_per_child reached)")


LABS2 = {"2.1": lab_2_1, "2.2": lab_2_2, "2.3": lab_2_3}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3
# ─────────────────────────────────────────────────────────────────────────────

def lab_3_1():
    separator("Lab 3.1 — Idempotency: same invoice submitted twice")
    print("Submitting process_invoice('INV-001') twice…")
    r1 = process_invoice.apply_async(kwargs={"invoice_id": "INV-LAB-001"})
    print(f"  1st submission  id={r1.id}")
    time.sleep(0.5)
    r2 = process_invoice.apply_async(kwargs={"invoice_id": "INV-LAB-001"})
    print(f"  2nd submission  id={r2.id}")
    print("\nWaiting for results…")
    try:
        res1 = r1.get(timeout=15)
        res2 = r2.get(timeout=15)
        print(f"  1st result: {res1}")
        print(f"  2nd result: {res2}")
        if res2.get("status") == "skipped":
            print("\n✅ Idempotency working — 2nd run skipped (already processed)")
        else:
            print("\n⚠️  Both ran — check DB constraint on ProcessedInvoice.invoice_id")
    except Exception as e:
        print(f"  ❌ {e}  — is the worker running?")


def lab_3_2():
    separator("Lab 3.2 — Retry with Exponential Backoff + Jitter")
    print("Submitting call_external_api — mocked endpoint will fail first 3 times…")
    print("Watch worker logs for retry countdown values (they should vary due to jitter).\n")
    r = call_external_api.apply_async(
        kwargs={"endpoint": "http://localhost:9999/fake", "payload": {"lab": "3.2"}}
    )
    print(f"  Task ID : {r.id}")
    print("  → Worker logs show: Retry in Xs (backoff + jitter)")
    print("  → After 5 retries: task goes to dead-letter")
    print("  → Inspect: uv run python scripts/replay_dead_letter.py --inspect")


def lab_3_3():
    separator("Lab 3.3 — soft_time_limit: CSV job saves progress on timeout")
    print("Submitting process_large_csv (file_id=1)…")
    r = process_large_csv.apply_async(kwargs={"file_id": 1})
    print(f"  Task ID : {r.id}")
    print("  → Task has soft_time_limit=5s (lab override)")
    print("  → Watch worker log for: SoftTimeLimitExceeded caught, status=timeout saved")


LABS3 = {"3.1": lab_3_1, "3.2": lab_3_2, "3.3": lab_3_3}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4
# ─────────────────────────────────────────────────────────────────────────────

def lab_4_1():
    separator("Lab 4.1 — Rate Limiting (10 SMS/min per worker)")
    print("Submitting 20 SMS tasks — worker will throttle at 10/min…")
    for i in range(1, 21):
        r = send_sms.apply_async(kwargs={"phone_number": f"+1555000{i:04d}", "message": f"Lab 4.1 msg #{i}"})
        print(f"  send_sms #{i:2d}  id={r.id}")
    print("\n  → In Flower, see tasks queuing up — worker processes only 10/min")
    print("  → To change rate dynamically (no restart):")
    print("    from celery import current_app")
    print("    current_app.control.rate_limit('demo.send_sms', '5/m')")


def lab_4_2():
    separator("Lab 4.2 — Dead Letter Queue")
    print("Submitting 3 always_fails tasks — they will exhaust retries and go to DLQ…")
    for i in range(1, 4):
        r = always_fails.apply_async(kwargs={"task_number": i})
        print(f"  always_fails #{i}  id={r.id}")
    print("\n  → Watch worker logs: retry attempts, then 'moved to dead-letter'")
    print("  → After ~30s, inspect the DLQ:")
    print("    uv run python scripts/replay_dead_letter.py --inspect")
    print("  → Replay (they'll fail again, but you see the flow):")
    print("    uv run python scripts/replay_dead_letter.py")


def lab_4_3():
    separator("Lab 4.3 — Circuit Breaker Load Test")
    print("Submitting 50 tasks rapidly with NO worker running…")
    print("Queue depth will grow — circuit breaker activates at depth > 1000\n")
    count = 0
    from production_patterns.utils.circuit_breaker import safe_enqueue, QueueFullError
    for i in range(50):
        try:
            safe_enqueue(send_bulk_email, to_address="test@example.com",
                         subject=f"Bulk #{i}", queue="notifications")
            count += 1
            print(f"  Enqueued #{i:2d}")
        except QueueFullError as e:
            print(f"  ⚡ CIRCUIT BREAKER at #{i}: {e}")
            break
    print(f"\n  Enqueued {count} tasks before circuit breaker (or all 50 if queue was shallow)")
    print("  → redis-cli -p 6380 LLEN celery  (check queue depth)")


LABS4 = {"4.1": lab_4_1, "4.2": lab_4_2, "4.3": lab_4_3}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5
# ─────────────────────────────────────────────────────────────────────────────

def lab_5_1():
    separator("Lab 5.1 — Queue Starvation Demo")
    print("Starting a SINGLE worker on all queues (the bad pattern):")
    print("  uv run celery -A celery_playground worker -Q default,notifications,media \\")
    print("      --concurrency=2 --prefetch-multiplier=1 -l info\n")
    print("Submitting 10 slow media tasks (5s each) + 5 email notifications…")
    for i in range(1, 11):
        r = starvation_slow_task.apply_async(kwargs={"task_number": i, "duration": 5})
        print(f"  slow media task #{i:2d}  id={r.id}")
    for i in range(1, 6):
        r = send_email_notification.apply_async(
            kwargs={"to_address": f"user{i}@example.com", "subject": f"Lab 5.1 email #{i}"}
        )
        print(f"  email notification #{i}  id={r.id}")
    print()
    print("  → With a single mixed worker: emails wait behind media tasks")
    print("  → Measure: time from submission to email completion")
    print()
    print("Now repeat with SEPARATE workers:")
    print("  uv run celery -A celery_playground worker -Q notifications \\")
    print("      --pool=gevent --concurrency=50 --hostname=worker-notif@%h -l info &")
    print("  uv run celery -A celery_playground worker -Q media \\")
    print("      --concurrency=2 --hostname=worker-media@%h -l info &")
    print("  → Emails complete in < 1s regardless of media queue depth")


def lab_5_2():
    separator("Lab 5.2 — 500 Notification Tasks (KEDA Autoscaling Demo)")
    print("Submitting 500 notification tasks to flood the notifications queue…")
    print("(Use with KEDA scaledobject-notifications.yaml to watch pods scale up)\n")
    for i in range(1, 501):
        send_push_notification.apply_async(
            kwargs={"device_token": f"device_{i:04d}_token", "title": f"Notification #{i}"}
        )
        if i % 100 == 0:
            print(f"  Submitted {i}/500…")
    print("\n✅ 500 tasks submitted to notifications queue")
    print("  → kubectl get pods -l queue=notifications -w  (watch scale-up)")
    print("  → redis-cli -p 6380 LLEN notifications  (queue depth)")


LABS5 = {"5.1": lab_5_1, "5.2": lab_5_2}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 6
# ─────────────────────────────────────────────────────────────────────────────

def lab_6_1():
    separator("Lab 6.1 — Leaky Task (RSS grows without max_tasks_per_child)")
    print("Start worker WITHOUT recycling:")
    print("  uv run celery -A celery_playground worker -Q default \\")
    print("      --concurrency=1 --prefetch-multiplier=1 -l info\n")
    print("Submitting 30 leaky tasks (payload_size=5000 each)…")
    for i in range(1, 31):
        r = leaky_task.apply_async(kwargs={"task_number": i, "payload_size": 5000})
        print(f"  leaky_task #{i:2d}  id={r.id}")
    print()
    print("  → Monitor RSS in real time (press Ctrl+C to stop watch):")
    print('    watch -n1 \'ps aux | grep "[c]elery worker" | awk "{print \\$6, \\"KB\\"}"\'')
    print("  → RSS will keep growing — never shrinks")
    print()
    print("Now restart worker WITH recycling:")
    print("  uv run celery -A celery_playground worker -Q default \\")
    print("      --concurrency=1 --prefetch-multiplier=1 --max-tasks-per-child=10 -l info")
    print("  → RSS resets every 10 tasks")


def lab_6_2():
    separator("Lab 6.2 — Clean Task (RSS stays flat)")
    print("Submitting 30 clean_task tasks for comparison…")
    for i in range(1, 31):
        r = clean_task.apply_async(kwargs={"task_number": i, "payload_size": 5000})
        print(f"  clean_task #{i:2d}  id={r.id}")
    print()
    print("  → Monitor RSS: should stay flat (local variables collected by GC)")


def lab_6_3():
    separator("Lab 6.3 — Memory Spike (trigger max_memory_per_child)")
    print("Start worker with low memory limit:")
    print("  uv run celery -A celery_playground worker -Q default \\")
    print("      --concurrency=1 --prefetch-multiplier=1 --max-memory-per-child=50000 -l info\n")
    print("Submitting memory_spike_task (spike_mb=100 — exceeds 50MB limit)…")
    r = memory_spike_task.apply_async(kwargs={"spike_mb": 100})
    print(f"  Task ID : {r.id}")
    print()
    print("  → Worker logs: 'Worker with pid NNN terminated due to memory limit'")
    print("  → Task is re-queued (acks_late=True) — NEW worker process starts")
    print("  → Spike task runs again on fresh worker — verify task completes eventually")


LABS6 = {"6.1": lab_6_1, "6.2": lab_6_2, "6.3": lab_6_3}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 7
# ─────────────────────────────────────────────────────────────────────────────

def lab_7_1():
    separator("Lab 7.1 — Canary Heartbeat Task")
    print("Submitting canary_heartbeat manually (normally run by Beat every 60s)…")
    r = canary_heartbeat.apply_async()
    print(f"  Task ID : {r.id}")
    try:
        result = r.get(timeout=15)
        print(f"  ✅ Result: {result}")
        print("  → Workers are alive and responsive")
    except Exception as e:
        print(f"  ❌ Canary timed out: {e}")
        print("  → ALERT: workers appear stuck or queue is backed up")


def lab_7_2():
    separator("Lab 7.2 — Dynamic Schedule: per-user daily report")
    print("Creating a per-user daily report schedule (no Beat restart needed)…")
    try:
        from demo.tasks_module_07 import schedule_user_report
        task = schedule_user_report(user_id=42, hour=8)
        print(f"  ✅ Schedule created/updated: '{task.name}'")
        print(f"     Runs: every day at 08:00 UTC")
        print(f"     Enabled: {task.enabled}")
        print()
        print("  Beat picks up the new schedule within CELERY_BEAT_MAX_LOOP_INTERVAL=30s")
        print("  No restart required — that's the power of DatabaseScheduler")
    except Exception as e:
        print(f"  ❌ {e}")
        print("  → Run 'uv run python manage.py migrate' first (django_celery_beat tables)")

    print()
    print("Submitting daily_report_task directly:")
    r = daily_report_task.apply_async(kwargs={"user_id": 42})
    print(f"  Task ID : {r.id}")
    try:
        result = r.get(timeout=15)
        print(f"  ✅ Result: {result}")
    except Exception as e:
        print(f"  ❌ {e}  — is the worker running?")


LABS7 = {"7.1": lab_7_1, "7.2": lab_7_2}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 8
# ─────────────────────────────────────────────────────────────────────────────

def lab_8_1():
    separator("Lab 8.1 — Traced CSV Task (OpenTelemetry spans)")
    print("Submitting traced_csv_task — manual spans for csv.parse and csv.write_db…")
    r = traced_csv_task.apply_async(kwargs={"file_id": 1, "row_count": 100})
    print(f"  Task ID : {r.id}")
    print()
    print("  Without OTel configured: task runs normally, no traces emitted")
    print("  With OTel (Jaeger running):")
    print("    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \\")
    print("    uv run celery -A celery_playground worker -Q default -l info")
    print("  → View in Jaeger: traced_csv_task → csv.parse → csv.write_db spans")


def lab_8_2():
    separator("Lab 8.2 — Correlation ID End-to-End Chain")
    corr_id = "lab-8-2-corr-id-abc123"
    set_correlation_id(corr_id)
    print(f"Setting correlation_id = '{corr_id}'")
    print("Submitting traceable_task → (result passed to) child_task…\n")

    r1 = traceable_task.apply_async(kwargs={"user_id": 42, "action": "purchase"})
    print(f"  traceable_task   id={r1.id}")

    r2 = child_task.apply_async(kwargs={
        "parent_result": {"task_id": r1.id, "user_id": 42},
        "step": "post-purchase-step"
    })
    print(f"  child_task       id={r2.id}")

    print()
    print("  → Both tasks share the same correlation_id in their logs")
    print(f"  → Grep worker logs: grep '{corr_id}' <logfile>")
    print("  → All lines from both tasks appear together")


LABS8 = {"8.1": lab_8_1, "8.2": lab_8_2}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 11
# ─────────────────────────────────────────────────────────────────────────────

def lab_11_1():
    separator("Lab 11.1 — CSV Import Pipeline (Chain)")
    url = "https://example.com/data.csv"
    print(f"Building chain: download → parse → validate → save")
    print(f"  URL: {url}\n")
    pipeline = build_import_pipeline(url, user_id=42)
    result = pipeline.apply_async()
    print(f"  Chain AsyncResult : {result.id}")
    print()
    print("  Waiting for final result (up to 30s)…")
    try:
        final = result.get(timeout=30)
        print(f"  ✅ Final result: {final}")
    except Exception as e:
        print(f"  ❌ {e}  — is the worker running?")
    print()
    print("  → In Flower, see 4 tasks chained in sequence:")
    print("    demo.pipeline_download → demo.pipeline_parse →")
    print("    demo.pipeline_validate → demo.pipeline_save")


def lab_11_2():
    separator("Lab 11.2 — Parallel Batch Processing (Group)")
    print("Creating 10 batches of 20 items, processing in parallel…\n")
    from celery import group
    batches = [
        [{"value": j * (i + 1)} for j in range(20)]
        for i in range(10)
    ]
    job = group(process_batch.s(batch, batch_id=i) for i, batch in enumerate(batches))
    result = job.apply_async()
    print(f"  Group submitted — {len(batches)} tasks running in parallel")
    print("  Waiting for all 10 batch results (up to 30s)…")
    try:
        outputs = result.get(timeout=30)
        grand_total = sum(o["total"] for o in outputs)
        print(f"  ✅ All batches complete. Grand total: {grand_total}")
        for o in outputs:
            print(f"     Batch #{o['batch_id']:2d}  total={o['total']}  count={o['count']}")
    except Exception as e:
        print(f"  ❌ {e}  — is the worker running?")


def lab_11_3():
    separator("Lab 11.3 — Task Versioning: old + new format")
    print("Simulating a rolling deploy — old tasks in queue alongside new format.\n")

    print("Old format (only email provided — v1 defaults apply):")
    r1 = send_email_v1.apply_async(kwargs={"email": "old@example.com"})
    print(f"  send_email_v1 (old format)  id={r1.id}")

    print("\nNew format (all args — v1 handles both):")
    r2 = send_email_v1.apply_async(kwargs={
        "email": "new@example.com", "template_id": "welcome_v2", "version": 2
    })
    print(f"  send_email_v1 (new format)  id={r2.id}")

    print("\nFully migrated to v2 task:")
    r3 = send_email_v2.apply_async(kwargs={
        "email": "migrated@example.com", "template_id": "welcome", "locale": "fr"
    })
    print(f"  send_email_v2               id={r3.id}")

    print("\nWaiting for results…")
    try:
        for label, r in [("v1 old", r1), ("v1 new", r2), ("v2    ", r3)]:
            res = r.get(timeout=10)
            print(f"  {label}  → {res}")
        print("\n✅ All three completed — no breakage across versions")
        print("  Deploy process: keep v1 alive until queue drains, then remove it")
    except Exception as e:
        print(f"  ❌ {e}  — is the worker running?")


LABS11 = {"11.1": lab_11_1, "11.2": lab_11_2, "11.3": lab_11_3}


# ─────────────────────────────────────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────────────────────────────────────

ALL_LABS = {
    **LABS,
    **LABS2,
    **LABS3,
    **LABS4,
    **LABS5,
    **LABS6,
    **LABS7,
    **LABS8,
    **LABS11,
}

ALL_GROUPS = {
    "all":   LABS,
    "all2":  LABS2,
    "all3":  LABS3,
    "all4":  LABS4,
    "all5":  LABS5,
    "all6":  LABS6,
    "all7":  LABS7,
    "all8":  LABS8,
    "all11": LABS11,
}

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "help"

    if arg in ALL_GROUPS:
        for fn in ALL_GROUPS[arg].values():
            fn()
            time.sleep(0.5)
    elif arg in ALL_LABS:
        ALL_LABS[arg]()
    else:
        print(__doc__)
        sys.exit(0 if arg == "help" else 1)

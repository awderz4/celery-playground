"""
scripts/submit_tasks.py
=======================
Module 1 — Lab helper: submit tasks and print their IDs so you can
track them in Flower and inspect them with trace_redis.sh.

Usage:
  uv run python scripts/submit_tasks.py [lab]

Labs:
  1.1   state transitions (states + failure)
  1.2   serialization payloads
  1.3   result backend (fire-and-forget vs stored)
  1.4   request context inspection
  1.5   queue depth visibility (8 observable tasks)
  all   run all labs in sequence
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_playground.settings")

import django
django.setup()

from demo.tasks import (
    task_with_states,
    task_that_fails,
    json_payload_task,
    large_payload_task,
    fire_and_forget,
    store_result,
    inspect_request,
    observable_task,
)


def separator(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def lab_1_1():
    separator("Lab 1.1 — State Transitions")
    print("Submitting task_with_states (duration=8s)…")
    r1 = task_with_states.delay(duration=8)
    print(f"  Task ID : {r1.id}")
    print(f"  State   : {r1.state}  ← should be PENDING")
    print("  → Open Flower, find this task, watch it move PENDING→STARTED→SUCCESS")

    print("\nSubmitting task_that_fails…")
    r2 = task_that_fails.delay()
    print(f"  Task ID : {r2.id}")
    print("  → After ~2s it will be FAILURE in Flower")
    print("  → Click the task ID in Flower to see the full Python traceback")


def lab_1_2():
    separator("Lab 1.2 — Serialization & Message Envelope")
    payload = {"user_id": 42, "action": "signup", "timestamp": "2026-03-02T09:00:00Z"}
    print(f"Submitting json_payload_task with {len(payload)} keys…")
    r1 = json_payload_task.delay(payload)
    print(f"  Task ID : {r1.id}")
    print("  → Run:  bash scripts/trace_redis.sh queue")
    print("    Look at the raw JSON envelope — find your payload inside it.")

    print("\nSubmitting large_payload_task (size=500)…")
    r2 = large_payload_task.delay(size=500)
    print(f"  Task ID : {r2.id}")
    print("  → After task completes, run:")
    print(f"    bash scripts/trace_redis.sh ttl {r2.id}")
    print("    Note the SIZE — this is how much Redis memory one result uses.")


def lab_1_3():
    separator("Lab 1.3 — Result Backend Strategy")
    print("Before: checking DB 1 key count…")
    print("  Run: bash scripts/trace_redis.sh dbsize")

    print("\nSubmitting fire_and_forget (ignore_result=True)…")
    r1 = fire_and_forget.delay("hello from lab 1.3")
    print(f"  Task ID : {r1.id}")

    print("\nSubmitting store_result (ignore_result=False)…")
    r2 = store_result.delay(7)
    print(f"  Task ID : {r2.id}")

    print("\nWaiting 4s for tasks to complete…")
    time.sleep(4)

    print("\nAfter: checking DB 1 key count again…")
    print("  Run: bash scripts/trace_redis.sh dbsize")
    print("  → DB 1 should have grown by exactly 1 (store_result only)")
    print(f"  Run: bash scripts/trace_redis.sh ttl {r2.id}")
    print("  → You will see the TTL countdown from CELERY_RESULT_EXPIRES=3600")


def lab_1_4():
    separator("Lab 1.4 — Message Envelope & Request Context")
    print("Submitting inspect_request…")
    r1 = inspect_request.delay(echo="module-1-lab-1.4")
    print(f"  Task ID : {r1.id}")
    print("  Waiting for result (up to 10s)…")
    try:
        result = r1.get(timeout=10)
        print("\n  ✅ Request context received by worker:")
        for k, v in result.items():
            print(f"     {k:<14} = {v}")
    except Exception as e:
        print(f"  ❌ Could not get result: {e}")
        print("  Is the worker running?  uv run celery -A celery_playground worker --loglevel=info")


def lab_1_5():
    separator("Lab 1.5 — Queue Depth Visibility (prefetch=1 demo)")
    print("Submitting 8 observable_task jobs (duration=15s each)…")
    print("Open Flower → Workers → <your worker> before they all get picked up.\n")
    results = []
    for i in range(1, 9):
        r = observable_task.delay(task_number=i, duration=15)
        results.append(r)
        print(f"  Submitted task #{i}  id={r.id}")
    print(f"\n✅ All 8 tasks submitted.")
    print("  → Flower should show: Active=1 (or concurrency), Queue depth = rest")
    print("  → With prefetch_multiplier=1: all queued tasks are visible")
    print("  → Run: bash scripts/trace_redis.sh queue  (watch the depth drop as tasks complete)")


LABS = {
    "1.1": lab_1_1,
    "1.2": lab_1_2,
    "1.3": lab_1_3,
    "1.4": lab_1_4,
    "1.5": lab_1_5,
}


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if arg == "all":
        for fn in LABS.values():
            fn()
            time.sleep(1)
    elif arg in LABS:
        LABS[arg]()
    else:
        print(__doc__)
        sys.exit(1)


#!/usr/bin/env python3
"""
scripts/replay_dead_letter.py
==============================
Module 4 — Dead Letter Queue Replay

Reads tasks from the Redis dead-letter list and re-enqueues them.

Usage:
    # Replay up to 100 tasks
    uv run python scripts/replay_dead_letter.py

    # Replay up to 50 tasks
    uv run python scripts/replay_dead_letter.py --limit 50

    # Just inspect — don't replay
    uv run python scripts/replay_dead_letter.py --inspect

    # Clear the dead-letter queue without replaying
    uv run python scripts/replay_dead_letter.py --clear

Dead-letter format (JSON per list entry):
    {
        "task_id": "uuid",
        "task_name": "demo.always_fails_task",
        "error": "RuntimeError: ...",
        "args": [],
        "kwargs": {"task_number": 1},
        "failed_at": "2026-03-04T...",
        "retry_count": 3
    }
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_playground.settings")

import django
django.setup()

import redis
from celery import current_app
from django.conf import settings

DEAD_LETTER_KEY = "celery:dead-letter"


def get_redis():
    return redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def inspect_dead_letter(limit: int = 20):
    """Print the contents of the dead-letter queue without modifying it."""
    r = get_redis()
    total = r.llen(DEAD_LETTER_KEY)
    items = r.lrange(DEAD_LETTER_KEY, 0, limit - 1)

    print(f"\n{'='*60}")
    print(f"DEAD LETTER QUEUE: {DEAD_LETTER_KEY}")
    print(f"Total entries: {total}")
    print(f"{'='*60}")

    if not items:
        print("  (empty)")
        return

    for i, raw in enumerate(items, 1):
        try:
            task = json.loads(raw)
            print(f"\n[{i}] Task: {task.get('task_name', 'unknown')}")
            print(f"     ID:      {task.get('task_id', 'unknown')}")
            print(f"     Error:   {task.get('error', 'unknown')}")
            print(f"     Retries: {task.get('retry_count', 0)}")
            print(f"     Failed:  {task.get('failed_at', 'unknown')}")
            print(f"     Args:    {task.get('args', [])}")
            print(f"     Kwargs:  {task.get('kwargs', {})}")
        except json.JSONDecodeError:
            print(f"[{i}] (invalid JSON entry)")


def replay_dead_letter(limit: int = 100):
    """Re-enqueue tasks from the dead-letter queue."""
    r = get_redis()
    total = r.llen(DEAD_LETTER_KEY)
    count = min(total, limit)

    print(f"\n{'='*60}")
    print(f"REPLAYING DEAD LETTER QUEUE: {DEAD_LETTER_KEY}")
    print(f"Total in queue: {total}  |  Replaying: {count}")
    print(f"{'='*60}\n")

    if count == 0:
        print("Nothing to replay.")
        return

    replayed = 0
    skipped = 0

    for _ in range(count):
        raw = r.rpop(DEAD_LETTER_KEY)
        if not raw:
            break
        try:
            task_data = json.loads(raw)
            task_name = task_data.get("task_name")
            task = current_app.tasks.get(task_name)
            if task:
                task.apply_async(
                    args=task_data.get("args", []),
                    kwargs=task_data.get("kwargs", {}),
                )
                replayed += 1
                print(f"  ✅ Replayed: {task_name} (was: {task_data.get('task_id', '')[:8]}...)")
            else:
                skipped += 1
                print(f"  ⚠️  Skipped: {task_name} — task not found in registry")
        except json.JSONDecodeError:
            skipped += 1
            print("  ❌ Skipped: invalid JSON entry")
        except Exception as exc:
            skipped += 1
            print(f"  ❌ Error replaying task: {exc}")

    print(f"\nDone: {replayed} replayed, {skipped} skipped")
    remaining = r.llen(DEAD_LETTER_KEY)
    print(f"Remaining in dead-letter: {remaining}")


def clear_dead_letter():
    """Delete all entries from the dead-letter queue."""
    r = get_redis()
    total = r.llen(DEAD_LETTER_KEY)
    r.delete(DEAD_LETTER_KEY)
    print(f"Cleared {total} entries from {DEAD_LETTER_KEY}")


def main():
    parser = argparse.ArgumentParser(
        description="Module 4: Dead-letter queue management"
    )
    parser.add_argument("--limit", type=int, default=100, help="Max tasks to process")
    parser.add_argument("--inspect", action="store_true", help="Inspect without replaying")
    parser.add_argument("--clear", action="store_true", help="Clear the dead-letter queue")
    args = parser.parse_args()

    if args.clear:
        clear_dead_letter()
    elif args.inspect:
        inspect_dead_letter(limit=args.limit)
    else:
        inspect_dead_letter(limit=min(args.limit, 5))  # show preview first
        print()
        answer = input("Proceed with replay? [y/N]: ").strip().lower()
        if answer == "y":
            replay_dead_letter(limit=args.limit)
        else:
            print("Replay cancelled.")


if __name__ == "__main__":
    main()


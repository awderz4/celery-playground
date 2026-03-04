"""
benchmarks/concurrency_test.py
================================
Module 2 — Worker Internals & Concurrency

Benchmark: prefork vs gevent throughput for I/O-bound and CPU-bound tasks.

Usage:
    # I/O benchmark (default) — compare prefork vs gevent
    uv run python benchmarks/concurrency_test.py

    # CPU benchmark — show gevent penalty
    uv run python benchmarks/concurrency_test.py --mode cpu

    # Custom task count
    uv run python benchmarks/concurrency_test.py --count 50

Prerequisites:
    Worker must be running. Use either:
      uv run celery -A celery_playground worker -Q default \\
          --pool=prefork --concurrency=4 --prefetch-multiplier=1 -l info

      uv run celery -A celery_playground worker -Q default \\
          --pool=gevent --concurrency=50 --prefetch-multiplier=1 -l info

    Then run this script to submit tasks and measure wall-clock throughput.
"""

import argparse
import os
import sys
import time

# ── Django setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_playground.settings")

import django
django.setup()

# ── After Django setup ────────────────────────────────────────────────────────
from celery import group
from demo.tasks_module_02 import io_bound_task, cpu_bound_task


def run_io_benchmark(count: int = 20, wait_timeout: int = 120):
    """
    Submit `count` I/O-bound tasks as a group and measure wall-clock time.

    With gevent --concurrency=50 all tasks overlap their network wait.
    With prefork --concurrency=4 only 4 run at a time.

    Expected results (httpbin.org/delay/1 → ~1s per request):
      prefork  concurrency=4:  ~count/4 seconds
      gevent   concurrency=50: ~2-3 seconds total (all overlap)
    """
    print(f"\n{'='*60}")
    print(f"I/O BENCHMARK: {count} tasks (each ~1s network wait)")
    print(f"{'='*60}")
    print("Submitting tasks...")

    jobs = group(
        io_bound_task.s(
            url="http://httpbin.org/delay/1",
            task_number=i,
        )
        for i in range(count)
    )

    start = time.monotonic()
    result = jobs.apply_async()

    print(f"All {count} tasks submitted. Waiting for results (timeout={wait_timeout}s)...")
    try:
        outputs = result.get(timeout=wait_timeout)
        wall_clock = time.monotonic() - start

        successes = sum(1 for o in outputs if o.get("status_code") == 200)
        pids = {o["pid"] for o in outputs}

        print(f"\n{'─'*60}")
        print(f"Results:")
        print(f"  Tasks submitted : {count}")
        print(f"  Successful      : {successes}")
        print(f"  Wall-clock time : {wall_clock:.2f}s")
        print(f"  Throughput      : {count / wall_clock:.1f} tasks/sec")
        print(f"  Unique PIDs     : {len(pids)}  ← 1=gevent, N=prefork")
        print(f"  Avg per task    : {wall_clock / count:.2f}s (serial would be {count:.0f}s)")
        print(f"{'─'*60}")
        print("\nInterpretation:")
        if len(pids) == 1:
            print("  Single PID → GEVENT pool: all tasks ran in one process.")
            print(f"  Concurrency efficiency: {count:.0f}s serial → {wall_clock:.1f}s actual")
        else:
            print(f"  Multiple PIDs ({len(pids)}) → PREFORK pool: tasks spread across processes.")
        return wall_clock, successes
    except Exception as exc:
        print(f"\nERROR waiting for results: {exc}")
        print("Is the worker running? Start it with:")
        print("  uv run celery -A celery_playground worker -Q default -l info")
        return None, 0


def run_cpu_benchmark(count: int = 8, wait_timeout: int = 180):
    """
    Submit `count` CPU-bound tasks as a group and measure wall-clock time.

    With prefork --concurrency=4 tasks run truly in parallel (different cores).
    With gevent --concurrency=50 tasks share one CPU core — no parallelism.

    Expected results (5M iterations each, ~0.5-1s on modern CPU):
      prefork  concurrency=4:  ~count/4 seconds (true parallelism)
      gevent   concurrency=50: ~count seconds   (sequential, GIL blocks)
    """
    print(f"\n{'='*60}")
    print(f"CPU BENCHMARK: {count} tasks (5M iterations each)")
    print(f"{'='*60}")
    print("Submitting tasks...")

    jobs = group(
        cpu_bound_task.s(iterations=5_000_000, task_number=i)
        for i in range(count)
    )

    start = time.monotonic()
    result = jobs.apply_async()

    print(f"All {count} tasks submitted. Waiting for results (timeout={wait_timeout}s)...")
    try:
        outputs = result.get(timeout=wait_timeout)
        wall_clock = time.monotonic() - start

        pids = {o["pid"] for o in outputs}
        avg_task_time = sum(o["elapsed_s"] for o in outputs) / len(outputs)

        print(f"\n{'─'*60}")
        print(f"Results:")
        print(f"  Tasks submitted : {count}")
        print(f"  Wall-clock time : {wall_clock:.2f}s")
        print(f"  Avg task time   : {avg_task_time:.2f}s")
        print(f"  Throughput      : {count / wall_clock:.1f} tasks/sec")
        print(f"  Unique PIDs     : {len(pids)}  ← N=prefork has parallelism, 1=gevent doesn't")
        print(f"{'─'*60}")
        print("\nInterpretation:")
        if len(pids) == 1:
            print("  Single PID → GEVENT pool.")
            print("  CPU-bound tasks are NOT parallelised — GIL prevents it.")
            print("  Wall clock ≈ sum of all task times → no speed-up.")
        else:
            print(f"  Multiple PIDs ({len(pids)}) → PREFORK pool: TRUE CPU parallelism.")
            speedup = (avg_task_time * count) / wall_clock
            print(f"  Parallel speed-up: ~{speedup:.1f}x vs sequential")
        return wall_clock, len(outputs)
    except Exception as exc:
        print(f"\nERROR waiting for results: {exc}")
        print("Is the worker running? Start it with:")
        print("  uv run celery -A celery_playground worker -Q default -l info")
        return None, 0


def main():
    parser = argparse.ArgumentParser(
        description="Module 2: Concurrency benchmark — prefork vs gevent"
    )
    parser.add_argument(
        "--mode",
        choices=["io", "cpu", "both"],
        default="io",
        help="Benchmark mode: io (default), cpu, or both",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="Number of tasks to submit (default: 20)",
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("MODULE 2 — CONCURRENCY BENCHMARK")
    print("="*60)
    print(f"Mode  : {args.mode}")
    print(f"Count : {args.count}")
    print("\nMake sure a worker is running before proceeding.")
    print("See README for worker startup commands.")

    if args.mode in ("io", "both"):
        run_io_benchmark(count=args.count)

    if args.mode in ("cpu", "both"):
        cpu_count = min(args.count, 8)  # keep CPU bench manageable
        run_cpu_benchmark(count=cpu_count)


if __name__ == "__main__":
    main()


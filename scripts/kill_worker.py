#!/usr/bin/env python3
"""
scripts/kill_worker.py
======================
Module 2 — Lab 2a/2b: SIGKILL a running Celery worker

Used to demonstrate the difference between acks_early (task lost) and
acks_late (task re-queued) when a worker is hard-killed.

Usage:
    # Find and kill the first prefork master process
    uv run python scripts/kill_worker.py

    # Dry run — show what would be killed without actually killing
    uv run python scripts/kill_worker.py --dry-run

    # Kill after a delay (gives time to submit tasks first)
    uv run python scripts/kill_worker.py --delay 15

Lab procedure:
    Terminal 1: uv run celery -A celery_playground worker -Q default \\
                    --pool=prefork --concurrency=1 --prefetch-multiplier=4 -l info

    Terminal 2: uv run python scripts/submit_tasks.py slow_task 8
                uv run python scripts/kill_worker.py --delay 15

    Observe: with prefetch=4 you lose tasks 2-4 (ACK'd but not executed)
             Repeat with prefetch=1 + acks_late → 0 tasks lost
"""

import argparse
import os
import signal
import sys
import time

try:
    import psutil
except ImportError:
    print("psutil not installed — install with: uv add psutil")
    print("Falling back to basic kill via pidfile search...")
    psutil = None  # type: ignore[assignment]


def find_celery_worker_pids():
    """Find all PIDs of running 'celery worker' processes."""
    pids = []
    if psutil is not None:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or [])
                if "celery" in cmdline and "worker" in cmdline:
                    pids.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    else:
        # Fallback: parse /proc
        for pid_dir in os.listdir("/proc"):
            if not pid_dir.isdigit():
                continue
            try:
                with open(f"/proc/{pid_dir}/cmdline", "rb") as f:
                    cmdline = f.read().decode("utf-8", errors="replace").replace("\x00", " ")
                if "celery" in cmdline and "worker" in cmdline:
                    pids.append(int(pid_dir))
            except (IOError, OSError):
                pass
    return pids


def kill_worker(delay: int = 0, dry_run: bool = False, signal_name: str = "SIGKILL"):
    """Find and kill the celery worker master process."""
    if delay > 0:
        print(f"Waiting {delay}s before killing worker...")
        print("(Submit your tasks now!)")
        for remaining in range(delay, 0, -1):
            print(f"  Killing in {remaining}s...", end="\r")
            time.sleep(1)
        print()

    pids = find_celery_worker_pids()

    if not pids:
        print("No Celery worker processes found. Is the worker running?")
        print("Start with: uv run celery -A celery_playground worker -Q default -l info")
        return

    sig = signal.SIGKILL if signal_name == "SIGKILL" else signal.SIGTERM
    sig_label = "SIGKILL (hard kill — no cleanup)" if sig == signal.SIGKILL else "SIGTERM (graceful shutdown)"

    print(f"\nFound {len(pids)} Celery worker process(es): {pids}")
    print(f"Signal: {sig_label}")

    if dry_run:
        print("[DRY RUN] Would kill PIDs:", pids)
        return

    for pid in pids:
        try:
            os.kill(pid, sig)
            print(f"  Sent {signal_name} to PID {pid}")
        except ProcessLookupError:
            print(f"  PID {pid} already gone")
        except PermissionError:
            print(f"  Permission denied for PID {pid} — try sudo")

    print(f"\nDone. Check Redis to see if tasks were re-queued:")
    print("  redis-cli -p 6380 LLEN celery")
    print("  redis-cli -p 6380 LRANGE celery 0 10")


def main():
    parser = argparse.ArgumentParser(
        description="Module 2 Lab 2a/2b: SIGKILL a running Celery worker"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=0,
        help="Wait N seconds before killing (gives time to submit tasks). Default: 0",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be killed without actually killing",
    )
    parser.add_argument(
        "--signal",
        choices=["SIGKILL", "SIGTERM"],
        default="SIGKILL",
        dest="signal_name",
        help="Signal to send: SIGKILL (hard) or SIGTERM (graceful). Default: SIGKILL",
    )
    args = parser.parse_args()
    kill_worker(delay=args.delay, dry_run=args.dry_run, signal_name=args.signal_name)


if __name__ == "__main__":
    main()


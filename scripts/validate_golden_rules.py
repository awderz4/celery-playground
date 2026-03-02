#!/usr/bin/env python
"""
Validate that Celery configuration follows the 10 Golden Rules.
Run this before deploying to production.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_playground.settings")
import django
django.setup()

from celery_playground.celery import app
from django.conf import settings


def validate_golden_rules():
    """Validate Golden Rules configuration."""
    rules_passed = 0
    rules_failed = 0
    warnings = 0

    print("=" * 70)
    print("CELERY PRODUCTION GOLDEN RULES VALIDATION")
    print("=" * 70)
    print()

    # Rule #2: acks_late
    print("Rule #2: Always enable acks_late=True")
    if app.conf.task_acks_late:
        print("  ✅ task_acks_late = True")
        rules_passed += 1
    else:
        print("  ❌ task_acks_late should be True (prevents task loss on crash)")
        rules_failed += 1
    print()

    # Rule #3: prefetch_multiplier
    print("Rule #3: prefetch_multiplier=1 for long tasks")
    prefetch = app.conf.worker_prefetch_multiplier
    if prefetch == 1:
        print(f"  ✅ worker_prefetch_multiplier = {prefetch}")
        rules_passed += 1
    else:
        print(f"  ❌ worker_prefetch_multiplier = {prefetch} (should be 1)")
        print("     Default=4 causes invisible task starvation")
        rules_failed += 1
    print()

    # Rule #4: visibility_timeout
    print("Rule #4: visibility_timeout > max task duration")
    broker_opts = getattr(settings, 'CELERY_BROKER_TRANSPORT_OPTIONS', {})
    vis_timeout = broker_opts.get('visibility_timeout', 3600)
    if vis_timeout >= 3600:
        print(f"  ✅ visibility_timeout = {vis_timeout}s (>= 1 hour)")
        rules_passed += 1
    else:
        print(f"  ⚠️  visibility_timeout = {vis_timeout}s (< 1 hour)")
        print("     Increase if you have tasks running > 1 hour")
        warnings += 1
    print()

    # Rule #7: JSON serializer (no pickle)
    print("Rule #7: Use JSON serializer only, never pickle")

    if app.conf.task_serializer == 'json':
        print("  ✅ task_serializer = 'json'")
        rules_passed += 1
    else:
        print(f"  ❌ task_serializer = '{app.conf.task_serializer}' (should be 'json')")
        rules_failed += 1

    if app.conf.result_serializer == 'json':
        print("  ✅ result_serializer = 'json'")
        rules_passed += 1
    else:
        print(f"  ❌ result_serializer = '{app.conf.result_serializer}' (should be 'json')")
        rules_failed += 1

    if 'pickle' not in app.conf.accept_content:
        print("  ✅ 'pickle' not in accept_content (secure)")
        rules_passed += 1
    else:
        print("  ❌ 'pickle' in accept_content (CRITICAL SECURITY RISK!)")
        print("     pickle = arbitrary code execution vulnerability")
        rules_failed += 1
    print()

    # Additional important checks
    print("Additional Production Configurations:")

    if app.conf.task_reject_on_worker_lost:
        print("  ✅ task_reject_on_worker_lost = True")
        rules_passed += 1
    else:
        print("  ⚠️  task_reject_on_worker_lost = False (consider enabling)")
        warnings += 1

    if app.conf.task_track_started:
        print("  ✅ task_track_started = True")
        rules_passed += 1
    else:
        print("  ⚠️  task_track_started = False (limits observability)")
        warnings += 1

    result_expires = getattr(settings, 'CELERY_RESULT_EXPIRES', None)
    if result_expires:
        print(f"  ✅ CELERY_RESULT_EXPIRES = {result_expires}s (prevents memory leak)")
        rules_passed += 1
    else:
        print("  ⚠️  CELERY_RESULT_EXPIRES not set (results never expire)")
        warnings += 1

    print()
    print("=" * 70)
    print(f"PASSED: {rules_passed} | FAILED: {rules_failed} | WARNINGS: {warnings}")
    print("=" * 70)
    print()

    if rules_failed == 0 and warnings == 0:
        print("🎉 Perfect! All Golden Rules validated.")
        print("   Your configuration follows production best practices.")
        return True
    elif rules_failed == 0:
        print("✅ All critical rules validated!")
        print(f"⚠️  {warnings} warning(s) - review recommendations above.")
        return True
    else:
        print(f"❌ {rules_failed} critical rule(s) failed.")
        print("   Fix these before deploying to production!")
        return False


if __name__ == '__main__':
    success = validate_golden_rules()
    sys.exit(0 if success else 1)


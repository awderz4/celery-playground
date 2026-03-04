"""
tests/test_module_02_worker_internals.py
=========================================
Module 2 — Worker Internals & Concurrency

Validates (in eager/unit-test mode):
  - All Module 2 task types execute correctly
  - acks_late=True on all reliability-critical tasks
  - reject_on_worker_lost=True where required
  - soft_time_limit and time_limit set on I/O-bound tasks
  - Worker settings: prefetch_multiplier, max_tasks_per_child
  - Concurrency pool comparison (documented behaviour)
"""

import pytest
from django.conf import settings


class TestSlowTaskBehaviour:
    """slow_task executes correctly and has correct reliability settings."""

    def test_slow_task_returns_dict(self):
        from demo.tasks_module_02 import slow_task
        r = slow_task.apply(kwargs={"task_number": 1, "duration": 0})
        assert r.successful()
        result = r.result
        assert result["task_number"] == 1
        assert "pid" in result
        assert "worker" in result

    def test_slow_task_has_acks_late(self):
        """Golden Rule #2: acks_late=True prevents task loss on worker crash."""
        from demo.tasks_module_02 import slow_task
        assert slow_task.acks_late is True, (
            "slow_task must have acks_late=True — "
            "without it, a SIGKILL will silently discard the task"
        )

    def test_slow_task_has_reject_on_worker_lost(self):
        """reject_on_worker_lost=True causes immediate NACK on SIGKILL."""
        from demo.tasks_module_02 import slow_task
        assert slow_task.reject_on_worker_lost is True, (
            "slow_task must have reject_on_worker_lost=True so that "
            "a SIGKILL causes an immediate NACK rather than waiting for visibility_timeout"
        )


class TestAcksModeTasks:
    """acks_early vs acks_late task anatomy."""

    def test_acks_early_task_executes(self):
        from demo.tasks_module_02 import acks_early_task
        r = acks_early_task.apply(kwargs={"task_number": 1, "duration": 0})
        assert r.successful()
        result = r.result
        assert result["acks_mode"] == "early"
        assert "pid" in result

    def test_acks_early_task_is_indeed_acks_early(self):
        """Intentionally acks_late=False to demonstrate the DANGER in labs."""
        from demo.tasks_module_02 import acks_early_task
        # This task deliberately has acks_late=False to show what NOT to do
        assert acks_early_task.acks_late is False, (
            "acks_early_task intentionally uses acks_late=False to demonstrate "
            "task-loss risk in Lab 2.2 — DO NOT change this"
        )

    def test_acks_late_task_executes(self):
        from demo.tasks_module_02 import acks_late_task
        r = acks_late_task.apply(kwargs={"task_number": 1, "duration": 0})
        assert r.successful()
        result = r.result
        assert result["acks_mode"] == "late"
        assert "pid" in result

    def test_acks_late_task_has_correct_settings(self):
        """acks_late + reject_on_worker_lost is the safe production pattern."""
        from demo.tasks_module_02 import acks_late_task
        assert acks_late_task.acks_late is True
        assert acks_late_task.reject_on_worker_lost is True


class TestIOBoundTask:
    """io_bound_task has correct pool recommendation and time limits."""

    def test_io_bound_task_has_time_limits(self):
        """Golden Rule #6: every task must have time limits."""
        from demo.tasks_module_02 import io_bound_task
        assert io_bound_task.soft_time_limit is not None, (
            "io_bound_task missing soft_time_limit — a hung HTTP call "
            "will freeze the worker forever without this"
        )
        assert io_bound_task.time_limit is not None, (
            "io_bound_task missing time_limit — absolute safety net required"
        )

    def test_io_bound_task_soft_limit_less_than_hard(self):
        """soft_time_limit must be < time_limit to allow cleanup before hard kill."""
        from demo.tasks_module_02 import io_bound_task
        assert io_bound_task.soft_time_limit < io_bound_task.time_limit, (
            f"soft_time_limit ({io_bound_task.soft_time_limit}) must be less than "
            f"time_limit ({io_bound_task.time_limit})"
        )

    def test_io_bound_task_has_acks_late(self):
        from demo.tasks_module_02 import io_bound_task
        assert io_bound_task.acks_late is True

    def test_io_bound_task_returns_expected_structure(self):
        """Mock requests.get to avoid real HTTP in unit tests."""
        from unittest.mock import MagicMock, patch
        from demo.tasks_module_02 import io_bound_task
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("demo.tasks_module_02.requests.get", return_value=mock_resp):
            r = io_bound_task.apply(kwargs={"url": "http://mock", "task_number": 99})
        assert r.successful()
        result = r.result
        assert result["task_number"] == 99
        assert result["status_code"] == 200
        assert "elapsed_s" in result
        assert "pid" in result


class TestCPUBoundTask:
    """cpu_bound_task executes correctly."""

    def test_cpu_bound_task_returns_dict(self):
        from demo.tasks_module_02 import cpu_bound_task
        r = cpu_bound_task.apply(kwargs={"iterations": 1000, "task_number": 1})
        assert r.successful()
        result = r.result
        assert result["task_number"] == 1
        assert result["iterations"] == 1000
        assert "elapsed_s" in result
        assert "pid" in result

    def test_cpu_bound_task_has_time_limits(self):
        from demo.tasks_module_02 import cpu_bound_task
        assert cpu_bound_task.soft_time_limit is not None
        assert cpu_bound_task.time_limit is not None

    def test_cpu_bound_task_has_acks_late(self):
        from demo.tasks_module_02 import cpu_bound_task
        assert cpu_bound_task.acks_late is True


class TestWorkerIdentityTask:
    """worker_identity_task returns correct metadata."""

    def test_worker_identity_returns_pid_and_hostname(self):
        from demo.tasks_module_02 import worker_identity_task
        r = worker_identity_task.apply(kwargs={"task_number": 42})
        assert r.successful()
        result = r.result
        assert result["task_number"] == 42
        assert "pid" in result
        assert "hostname" in result
        assert "worker" in result
        assert isinstance(result["pid"], int)


class TestWorkerSettings:
    """Critical worker settings are correctly configured."""

    def test_prefetch_multiplier_is_one(self):
        """
        Golden Rule #3: CELERYD_PREFETCH_MULTIPLIER must be 1.

        Default=4 causes silent task starvation:
          - Worker grabs 4 tasks before executing task 1
          - Tasks 2-4 are invisible to Flower and other workers
          - Deploy → restart → tasks 2-4 lost (if acks_early)
        """
        value = getattr(settings, "CELERYD_PREFETCH_MULTIPLIER", None)
        assert value == 1, (
            f"CELERYD_PREFETCH_MULTIPLIER={value} — must be 1 in production. "
            "Default=4 causes silent task starvation. See Golden Rule #3."
        )

    def test_max_tasks_per_child_is_configured(self):
        """Worker processes must recycle to prevent memory leak accumulation."""
        value = getattr(settings, "CELERYD_MAX_TASKS_PER_CHILD", None)
        assert value is not None, (
            "CELERYD_MAX_TASKS_PER_CHILD not set — worker processes will accumulate "
            "memory leaks indefinitely. Set to 50-500 depending on task memory profile."
        )
        assert 10 <= value <= 1000, (
            f"CELERYD_MAX_TASKS_PER_CHILD={value} seems out of range. "
            "Typical values: 50-500. Too low = excessive overhead. Too high = leaks accumulate."
        )

    def test_max_memory_per_child_is_configured(self):
        """Hard memory guard prevents Kubernetes OOMKill surprises."""
        value = getattr(settings, "CELERYD_MAX_MEMORY_PER_CHILD", None)
        assert value is not None, (
            "CELERYD_MAX_MEMORY_PER_CHILD not set — no hard memory guard. "
            "Workers can grow unbounded until Kubernetes OOMKills the pod. "
            "Set to 60-80% of your pod memory limit in KB."
        )
        assert value >= 50_000, (
            f"CELERYD_MAX_MEMORY_PER_CHILD={value}KB seems too low. "
            "Typical Django worker uses 100-400MB. Minimum recommended: 50MB (50000KB)."
        )

    def test_acks_late_globally_enabled(self):
        """Golden Rule #2: global acks_late=True as default."""
        assert settings.CELERY_TASK_ACKS_LATE is True, (
            "CELERY_TASK_ACKS_LATE must be True globally. "
            "Tasks that crash without ACK must be re-queued, not silently lost."
        )

    def test_reject_on_worker_lost_globally_enabled(self):
        """SIGKILL events must cause immediate NACK, not wait for visibility_timeout."""
        assert settings.CELERY_TASK_REJECT_ON_WORKER_LOST is True, (
            "CELERY_TASK_REJECT_ON_WORKER_LOST must be True. "
            "Without it, SIGKILL'd tasks wait for visibility_timeout before re-queue."
        )

    def test_visibility_timeout_exceeds_max_task_duration(self):
        """
        Golden Rule #4: visibility_timeout must exceed your longest task duration.

        Trap: task takes 90 min, visibility_timeout=3600s (1hr default).
        At T+60min Redis re-queues the still-running task → runs TWICE.
        """
        transport_opts = getattr(settings, "CELERY_BROKER_TRANSPORT_OPTIONS", {})
        vt = transport_opts.get("visibility_timeout", 3600)
        assert vt >= 3600, (
            f"visibility_timeout={vt}s — should be at least 3600s (1 hour). "
            "For tasks longer than 1 hour, set to 86400 (24 hours). "
            "This prevents Redis re-queueing running tasks as 'lost'. See Golden Rule #4."
        )


class TestConcurrencyDocumentation:
    """Verify the concurrency pool decision matrix is reflected in task design."""

    def test_io_bound_task_uses_acks_late(self):
        """
        I/O-bound tasks suitable for gevent MUST still have acks_late=True.
        gevent does NOT change acknowledgment behaviour.
        """
        from demo.tasks_module_02 import io_bound_task
        assert io_bound_task.acks_late is True

    def test_cpu_bound_task_uses_acks_late(self):
        """CPU-bound tasks on prefork pool must also have acks_late=True."""
        from demo.tasks_module_02 import cpu_bound_task
        assert cpu_bound_task.acks_late is True

    def test_all_module2_tasks_have_task_names(self):
        """All tasks should have explicit names for easier monitoring."""
        from demo.tasks_module_02 import (
            slow_task, acks_early_task, acks_late_task,
            io_bound_task, cpu_bound_task, worker_identity_task,
        )
        tasks = [slow_task, acks_early_task, acks_late_task,
                 io_bound_task, cpu_bound_task, worker_identity_task]
        for task in tasks:
            assert task.name is not None
            assert len(task.name) > 0


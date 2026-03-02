"""
tests/test_module_01_architecture.py
=====================================
Module 1 — Task Lifecycle & Internals

Validates:
  - All five new task types execute correctly
  - Serialization settings (JSON only, never pickle)
  - Result backend behaviour (ignore vs store)
  - Task request metadata is populated
  - Broker transport options (visibility_timeout)
"""

import pytest
from django.conf import settings


class TestTaskExecution:
    """New Module 1 tasks run correctly in eager mode."""

    def test_slow_add_still_works(self):
        """Baseline from Module 0 must not be broken."""
        from demo.tasks import slow_add
        r = slow_add.apply(args=[3, 4])
        assert r.successful()
        assert r.result == 7

    def test_task_with_states_returns_dict(self):
        from demo.tasks import task_with_states
        r = task_with_states.apply(kwargs={"duration": 0})
        assert r.successful()
        result = r.result
        assert "task_id" in result
        assert "worker" in result
        assert "pid" in result

    def test_task_that_fails_raises(self):
        from demo.tasks import task_that_fails
        r = task_that_fails.apply()
        assert r.failed()
        assert isinstance(r.result, ValueError)

    def test_json_payload_task(self):
        from demo.tasks import json_payload_task
        data = {"a": 1, "b": 2, "c": 3}
        r = json_payload_task.apply(kwargs={"data": data})
        assert r.successful()
        assert r.result["count"] == 3
        assert set(r.result["received_keys"]) == {"a", "b", "c"}

    def test_large_payload_task(self):
        from demo.tasks import large_payload_task
        r = large_payload_task.apply(kwargs={"size": 10})
        assert r.successful()
        assert r.result["keys"] == 10

    def test_fire_and_forget_executes(self):
        from demo.tasks import fire_and_forget
        r = fire_and_forget.apply(kwargs={"message": "test"})
        # Task must execute without error even though result is ignored
        assert r.successful()

    def test_store_result_returns_computation(self):
        from demo.tasks import store_result
        r = store_result.apply(kwargs={"value": 4})
        assert r.successful()
        assert r.result["input"] == 4
        assert r.result["squared"] == 16
        assert r.result["cubed"] == 64

    def test_inspect_request_returns_metadata(self):
        from demo.tasks import inspect_request
        r = inspect_request.apply(kwargs={"echo": "test-echo"})
        assert r.successful()
        result = r.result
        assert result["echo"] == "test-echo"
        assert "task_id" in result
        assert "pid" in result

    def test_observable_task_returns_number(self):
        from demo.tasks import observable_task
        r = observable_task.apply(kwargs={"task_number": 5, "duration": 0})
        assert r.successful()
        assert r.result["task_number"] == 5


class TestSerializationSecurity:
    """Golden Rule #7: JSON only, pickle never."""

    def test_task_serializer_is_json(self):
        from celery_playground.celery import app
        assert app.conf.task_serializer == "json"

    def test_result_serializer_is_json(self):
        from celery_playground.celery import app
        assert app.conf.result_serializer == "json"

    def test_pickle_not_in_accept_content(self):
        from celery_playground.celery import app
        assert "pickle" not in app.conf.accept_content

    def test_only_json_in_accept_content(self):
        from celery_playground.celery import app
        assert "json" in app.conf.accept_content


class TestResultBackend:
    """Result backend is configured with TTL to prevent memory leaks."""

    def test_result_expires_is_set(self):
        expires = getattr(settings, "CELERY_RESULT_EXPIRES", None)
        assert expires is not None, "CELERY_RESULT_EXPIRES must be set"
        assert expires > 0, "CELERY_RESULT_EXPIRES must be positive"

    def test_result_backend_is_configured(self):
        result_backend = getattr(settings, "CELERY_RESULT_BACKEND", None)
        assert result_backend, "CELERY_RESULT_BACKEND must be set"

    def test_fire_and_forget_flag(self):
        """fire_and_forget task must declare ignore_result=True."""
        from demo.tasks import fire_and_forget
        assert fire_and_forget.ignore_result is True

    def test_store_result_flag(self):
        """store_result task must NOT ignore result."""
        from demo.tasks import store_result
        assert store_result.ignore_result is False


class TestBrokerTransportOptions:
    """Golden Rule #4: visibility_timeout must exceed max task duration."""

    def test_visibility_timeout_configured(self):
        opts = getattr(settings, "CELERY_BROKER_TRANSPORT_OPTIONS", {})
        assert "visibility_timeout" in opts, (
            "visibility_timeout must be set in CELERY_BROKER_TRANSPORT_OPTIONS"
        )

    def test_visibility_timeout_at_least_one_hour(self):
        opts = getattr(settings, "CELERY_BROKER_TRANSPORT_OPTIONS", {})
        vt = opts.get("visibility_timeout", 0)
        assert vt >= 3600, (
            f"visibility_timeout={vt}s is too short — "
            "must be >= 3600s (and ideally > your longest task)"
        )

    def test_retry_on_timeout_enabled(self):
        opts = getattr(settings, "CELERY_BROKER_TRANSPORT_OPTIONS", {})
        assert opts.get("retry_on_timeout") is True, (
            "retry_on_timeout should be True to handle transient Redis disconnects"
        )


class TestWorkerReliabilitySettings:
    """Module 0 Golden Rules still hold in Module 1."""

    def test_acks_late(self):
        from celery_playground.celery import app
        assert app.conf.task_acks_late is True

    def test_prefetch_multiplier(self):
        from celery_playground.celery import app
        assert app.conf.worker_prefetch_multiplier == 1

    def test_reject_on_worker_lost(self):
        from celery_playground.celery import app
        assert app.conf.task_reject_on_worker_lost is True

    def test_track_started(self):
        from celery_playground.celery import app
        # Required for Lab 1.1 state transition observation
        assert app.conf.task_track_started is True


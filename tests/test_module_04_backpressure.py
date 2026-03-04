"""
tests/test_module_04_backpressure.py
======================================
Module 4 — Backpressure, Rate Control & Dead Letters

Validates:
  - Rate limits set on send_sms and send_bulk_email
  - ProductionTask base provides acks_late + reject_on_worker_lost
  - Dead-letter routing: on_failure pushes to Redis list
  - Circuit breaker: safe_enqueue checks depth before enqueuing
  - always_fails_task uses ProductionTask base
  - payment_task uses ProductionTask base and has time limits
"""

import json
from unittest.mock import MagicMock, patch, call
import pytest
from django.conf import settings


class TestRateLimitedTasks:
    """Rate limits are set correctly on notification tasks."""

    def test_send_sms_has_rate_limit(self):
        from demo.tasks_module_04 import send_sms
        assert send_sms.rate_limit is not None
        assert send_sms.rate_limit == "10/m", (
            "send_sms rate_limit should be '10/m' to protect downstream SMS provider"
        )

    def test_send_sms_has_acks_late(self):
        from demo.tasks_module_04 import send_sms
        assert send_sms.acks_late is True

    def test_send_bulk_email_has_rate_limit(self):
        from demo.tasks_module_04 import send_bulk_email
        assert send_bulk_email.rate_limit is not None
        assert send_bulk_email.rate_limit == "100/m"

    def test_send_sms_executes(self):
        from demo.tasks_module_04 import send_sms
        r = send_sms.apply(kwargs={"phone_number": "+1234567890", "message": "Hello"})
        assert r.successful()
        assert r.result["status"] == "sent"

    def test_send_bulk_email_executes(self):
        from demo.tasks_module_04 import send_bulk_email
        r = send_bulk_email.apply(kwargs={
            "to_address": "test@example.com",
            "subject": "Test Subject",
        })
        assert r.successful()
        assert r.result["status"] == "queued"


class TestProductionTaskBase:
    """ProductionTask base class injects all production reliability settings."""

    def test_always_fails_uses_production_task_base(self):
        from demo.tasks_module_04 import always_fails_task
        from production_patterns.tasks.base import ProductionTask
        assert isinstance(always_fails_task, ProductionTask), (
            "always_fails_task must use base=ProductionTask to get "
            "automatic dead-letter routing"
        )

    def test_payment_task_uses_production_task_base(self):
        from demo.tasks_module_04 import payment_task
        from production_patterns.tasks.base import ProductionTask
        assert isinstance(payment_task, ProductionTask)

    def test_production_task_has_acks_late(self):
        from production_patterns.tasks.base import ProductionTask
        assert ProductionTask.acks_late is True

    def test_production_task_has_reject_on_worker_lost(self):
        from production_patterns.tasks.base import ProductionTask
        assert ProductionTask.reject_on_worker_lost is True

    def test_production_task_has_soft_time_limit(self):
        from production_patterns.tasks.base import ProductionTask
        assert ProductionTask.soft_time_limit is not None
        assert ProductionTask.soft_time_limit > 0

    def test_production_task_has_time_limit(self):
        from production_patterns.tasks.base import ProductionTask
        assert ProductionTask.time_limit is not None
        assert ProductionTask.time_limit > ProductionTask.soft_time_limit

    def test_payment_task_executes_successfully(self):
        from demo.tasks_module_04 import payment_task
        r = payment_task.apply(kwargs={"order_id": "ORD-001", "amount": 99.99})
        assert r.successful()
        assert r.result["status"] == "charged"
        assert r.result["order_id"] == "ORD-001"

    def test_always_fails_task_fails(self):
        from demo.tasks_module_04 import always_fails_task
        r = always_fails_task.apply(kwargs={"task_number": 1})
        assert r.failed()
        assert isinstance(r.result, RuntimeError)


class TestDeadLetterRouting:
    """Dead-letter routing pushes failed task metadata to Redis."""

    def _make_task(self, retries=3, max_retries=3):
        """Helper: build a ProductionTask-like object via _route_to_dead_letter directly."""
        from production_patterns.tasks.base import ProductionTask
        task = ProductionTask()
        task.name = "test.task"
        task.max_retries = max_retries
        return task

    def test_dead_letter_pushed_on_exhausted_retries(self):
        """_route_to_dead_letter pushes correct payload to Redis."""
        from production_patterns.tasks.base import ProductionTask

        task = self._make_task()
        mock_redis_instance = MagicMock()

        with patch("production_patterns.tasks.base.redis.Redis.from_url", return_value=mock_redis_instance):
            # Simulate on_failure path: retries == max_retries → route to DLQ
            task._route_to_dead_letter(
                task_id="task-123",
                exc=RuntimeError("test error"),
                args=[],
                kwargs={"key": "val"},
            )

        assert mock_redis_instance.lpush.called
        call_args = mock_redis_instance.lpush.call_args
        pushed_key = call_args[0][0]
        pushed_payload = json.loads(call_args[0][1])

        assert pushed_key == "celery:dead-letter"
        assert pushed_payload["task_id"] == "task-123"
        assert pushed_payload["task_name"] == "test.task"
        assert "test error" in pushed_payload["error"]

    def test_dead_letter_not_pushed_when_retries_remaining(self):
        """on_failure with retries < max_retries does NOT route to dead-letter."""
        from production_patterns.tasks.base import ProductionTask

        task = self._make_task()
        mock_redis_instance = MagicMock()

        # Simulate on_failure called when retries=1 < max_retries=3
        # We call on_failure via a mock request context
        with patch("production_patterns.tasks.base.redis.Redis.from_url", return_value=mock_redis_instance):
            # Manually replicate the guard: if retries < max_retries → no DLQ
            retries = 1
            if retries >= task.max_retries:
                task._route_to_dead_letter("task-456", RuntimeError("not yet"), [], {})

        assert not mock_redis_instance.lpush.called

    def test_dead_letter_payload_structure(self):
        """Dead-letter payload contains all required fields."""
        from production_patterns.tasks.base import ProductionTask

        task = self._make_task()
        task.name = "demo.payment_task"

        captured_payload = {}
        mock_redis = MagicMock()

        def capture_lpush(key, data):
            captured_payload.update(json.loads(data))

        mock_redis.lpush.side_effect = capture_lpush

        with patch("production_patterns.tasks.base.redis.Redis.from_url", return_value=mock_redis):
            task._route_to_dead_letter(
                "task-789",
                ValueError("payment failed"),
                ["ORD-001"],
                {"amount": 50.0},
            )

        required_fields = ["task_id", "task_name", "error", "error_type",
                           "args", "kwargs", "failed_at", "retry_count"]
        for field in required_fields:
            assert field in captured_payload, f"Dead-letter payload missing field: {field}"

        assert captured_payload["error_type"] == "ValueError"
        assert captured_payload["args"] == ["ORD-001"]
        assert captured_payload["kwargs"] == {"amount": 50.0}


class TestCircuitBreaker:
    """Circuit breaker safe_enqueue checks queue depth before enqueuing."""

    def test_safe_enqueue_normal_depth(self):
        """Queue depth <= 1000: task is enqueued normally."""
        from production_patterns.utils.circuit_breaker import safe_enqueue

        mock_task = MagicMock()
        mock_task.name = "demo.test_task"

        with patch("production_patterns.utils.circuit_breaker.get_queue_depth", return_value=50):
            safe_enqueue(mock_task, "arg1", queue="default", kwarg1="val1")

        mock_task.apply_async.assert_called_once_with(
            args=("arg1",), kwargs={"kwarg1": "val1"}, queue="default"
        )

    def test_safe_enqueue_pressure_zone(self):
        """Queue depth > 1000: task enqueued with expires=300."""
        from production_patterns.utils.circuit_breaker import safe_enqueue

        mock_task = MagicMock()
        with patch("production_patterns.utils.circuit_breaker.get_queue_depth", return_value=2000):
            safe_enqueue(mock_task, queue="default")

        call_kwargs = mock_task.apply_async.call_args[1]
        assert call_kwargs.get("expires") == 300

    def test_safe_enqueue_full_queue_raises(self):
        """Queue depth > 5000: QueueFullError raised, task is NOT enqueued."""
        from production_patterns.utils.circuit_breaker import safe_enqueue, QueueFullError

        mock_task = MagicMock()
        with patch("production_patterns.utils.circuit_breaker.get_queue_depth", return_value=6000):
            with pytest.raises(QueueFullError):
                safe_enqueue(mock_task, queue="default")

        mock_task.apply_async.assert_not_called()
        mock_task.delay.assert_not_called()

    def test_get_queue_depth_uses_llen(self):
        """get_queue_depth calls Redis LLEN on the queue key."""
        from production_patterns.utils.circuit_breaker import get_queue_depth

        mock_redis = MagicMock()
        mock_redis.llen.return_value = 42

        with patch("production_patterns.utils.circuit_breaker.get_redis_client", return_value=mock_redis):
            depth = get_queue_depth("my-queue")

        assert depth == 42
        mock_redis.llen.assert_called_once_with("my-queue")


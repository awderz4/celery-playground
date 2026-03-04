"""
tests/test_module_08_monitoring.py
=====================================
Module 8 — Monitoring, Logging & Distributed Tracing
"""
import pytest
from unittest.mock import patch, MagicMock


class TestCorrelationIDPropagation:
    def test_get_set_correlation_id(self):
        from demo.tasks_module_08 import get_correlation_id, set_correlation_id
        set_correlation_id("test-corr-id-123")
        assert get_correlation_id() == "test-corr-id-123"

    def test_correlation_task_base_class_exists(self):
        from demo.tasks_module_08 import CorrelationTask
        from celery import Task
        assert issubclass(CorrelationTask, Task)

    def test_traceable_task_returns_correlation_id(self):
        from demo.tasks_module_08 import traceable_task, set_correlation_id
        set_correlation_id("abc-xyz-789")
        r = traceable_task.apply(kwargs={"user_id": 42, "action": "test"})
        assert r.successful()
        assert r.result["user_id"] == 42
        assert "correlation_id" in r.result
        # In eager mode the thread-local value propagates directly
        assert r.result["correlation_id"] == "abc-xyz-789"

    def test_child_task_executes(self):
        from demo.tasks_module_08 import child_task, set_correlation_id
        set_correlation_id("child-corr-id")
        r = child_task.apply(kwargs={
            "parent_result": {"task_id": "parent-123"},
            "step": "step2",
        })
        assert r.successful()
        assert r.result["step"] == "step2"
        assert r.result["parent_task_id"] == "parent-123"
        assert "correlation_id" in r.result


class TestTraceableTasks:
    def test_traceable_task_has_acks_late(self):
        from demo.tasks_module_08 import traceable_task
        assert traceable_task.acks_late is True

    def test_traceable_task_has_time_limits(self):
        from demo.tasks_module_08 import traceable_task
        assert traceable_task.soft_time_limit is not None
        assert traceable_task.time_limit is not None


    def test_traced_csv_task_executes(self):
        from demo.tasks_module_08 import traced_csv_task
        r = traced_csv_task.apply(kwargs={"file_id": 1, "row_count": 10})
        assert r.successful()
        assert r.result["rows_processed"] == 10


class TestMonitoringCanary:
    def test_canary_executes(self):
        from demo.tasks_module_08 import monitoring_canary
        r = monitoring_canary.apply()
        assert r.successful()
        assert r.result["alive"] is True

    def test_canary_has_time_limit(self):
        from demo.tasks_module_08 import monitoring_canary
        assert monitoring_canary.time_limit is not None
        assert monitoring_canary.time_limit <= 30


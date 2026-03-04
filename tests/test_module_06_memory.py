"""
tests/test_module_06_memory.py
================================
Module 6 — Memory Management & Performance
"""
import pytest
from django.conf import settings


class TestMemorySettings:
    def test_max_tasks_per_child_set(self):
        assert getattr(settings, "CELERYD_MAX_TASKS_PER_CHILD", None) is not None

    def test_max_memory_per_child_set(self):
        assert getattr(settings, "CELERYD_MAX_MEMORY_PER_CHILD", None) is not None

    def test_max_memory_per_child_reasonable(self):
        val = settings.CELERYD_MAX_MEMORY_PER_CHILD
        assert val >= 50_000, "Should be at least 50MB (50000KB)"


class TestLeakyTask:
    def test_leaky_task_executes(self):
        from demo.tasks_module_06 import leaky_task
        r = leaky_task.apply(kwargs={"task_number": 1, "payload_size": 10})
        assert r.successful()
        result = r.result
        assert result["task_number"] == 1
        assert "pid" in result
        assert "rss_kb" in result
        assert result["accumulator_len"] >= 10

    def test_leaky_task_accumulates_across_calls(self):
        from demo.tasks_module_06 import leaky_task, _LEAKY_ACCUMULATOR
        initial = len(_LEAKY_ACCUMULATOR)
        leaky_task.apply(kwargs={"task_number": 99, "payload_size": 5})
        assert len(_LEAKY_ACCUMULATOR) >= initial + 5

    def test_leaky_task_has_acks_late(self):
        from demo.tasks_module_06 import leaky_task
        assert leaky_task.acks_late is True


class TestCleanTask:
    def test_clean_task_executes(self):
        from demo.tasks_module_06 import clean_task
        r = clean_task.apply(kwargs={"task_number": 1, "payload_size": 10})
        assert r.successful()
        assert r.result["processed"] == 10

    def test_clean_task_has_acks_late(self):
        from demo.tasks_module_06 import clean_task
        assert clean_task.acks_late is True


class TestProfiledTask:
    def test_profiled_task_executes(self):
        from demo.tasks_module_06 import profiled_task
        r = profiled_task.apply(kwargs={"payload_size": 100})
        assert r.successful()
        result = r.result
        assert result["payload_size"] == 100
        assert "rss_before_kb" in result
        assert "rss_after_kb" in result
        assert "delta_kb" in result
        assert "top_allocator" in result

    def test_profiled_task_has_time_limits(self):
        from demo.tasks_module_06 import profiled_task
        assert profiled_task.soft_time_limit is not None
        assert profiled_task.time_limit is not None


class TestMemorySpikeTask:
    def test_memory_spike_task_executes(self):
        from demo.tasks_module_06 import memory_spike_task
        r = memory_spike_task.apply(kwargs={"spike_mb": 1})  # small spike for tests
        assert r.successful()
        result = r.result
        assert result["spike_mb"] == 1
        assert result["delta_kb"] >= 0

    def test_memory_spike_task_has_acks_late(self):
        from demo.tasks_module_06 import memory_spike_task
        assert memory_spike_task.acks_late is True

    def test_memory_spike_task_has_reject_on_worker_lost(self):
        from demo.tasks_module_06 import memory_spike_task
        assert memory_spike_task.reject_on_worker_lost is True


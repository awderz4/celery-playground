"""
Module 0: Baseline Environment Tests
Validates that the basic Celery setup is working correctly.
"""
import pytest
from demo.tasks import slow_add


class TestBaselineEnvironment:
    """Test baseline Celery configuration."""

    def test_task_execution(self):
        """Test that a basic task can be executed."""
        result = slow_add.apply(args=[2, 3])
        assert result.successful()
        assert result.result == 5

    def test_task_serialization(self):
        """Test that tasks use JSON serialization (Golden Rule #7)."""
        from celery_playground.celery import app
        assert app.conf.task_serializer == 'json'
        assert app.conf.result_serializer == 'json'
        assert 'json' in app.conf.accept_content
        assert 'pickle' not in app.conf.accept_content

    def test_acks_late_enabled(self):
        """Test that acks_late is enabled (Golden Rule #2)."""
        from celery_playground.celery import app
        assert app.conf.task_acks_late is True

    def test_prefetch_multiplier(self):
        """Test that prefetch_multiplier=1 (Golden Rule #3)."""
        from celery_playground.celery import app
        assert app.conf.worker_prefetch_multiplier == 1

    def test_reject_on_worker_lost(self):
        """Test that reject_on_worker_lost is enabled."""
        from celery_playground.celery import app
        assert app.conf.task_reject_on_worker_lost is True


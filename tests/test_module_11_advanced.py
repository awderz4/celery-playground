"""
tests/test_module_11_advanced.py
===================================
Module 11 — Advanced Patterns & Task Versioning
"""
import pytest
from unittest.mock import patch, MagicMock


class TestCanvasPrimitives:
    """Chain, group, chord pipeline tasks execute correctly."""

    def test_pipeline_download_executes(self):
        from demo.tasks_module_11 import pipeline_download
        r = pipeline_download.apply(kwargs={"url": "http://example.com/data.csv"})
        assert r.successful()
        result = r.result
        assert "local_path" in result
        assert result["rows"] == 100

    def test_pipeline_parse_executes(self):
        from demo.tasks_module_11 import pipeline_parse
        download_result = {"local_path": "/tmp/test.csv", "rows": 5}
        r = pipeline_parse.apply(kwargs={"download_result": download_result})
        assert r.successful()
        assert r.result["count"] == 5

    def test_pipeline_validate_executes(self):
        from demo.tasks_module_11 import pipeline_validate
        # value=-1 fails the >= 0 check, value=10 passes → 1 valid row
        parse_result = {"rows": [{"id": 1, "value": 10}, {"id": 2, "value": -1}]}
        r = pipeline_validate.apply(kwargs={"parse_result": parse_result})
        assert r.successful()
        assert r.result["valid_count"] == 1

    def test_pipeline_save_executes(self):
        from demo.tasks_module_11 import pipeline_save
        validate_result = {"valid_rows": [{"id": 1}], "valid_count": 1}
        r = pipeline_save.apply(kwargs={"validate_result": validate_result, "user_id": 42})
        assert r.successful()
        assert r.result["saved"] == 1
        assert r.result["status"] == "done"

    def test_build_import_pipeline_creates_chain(self):
        from demo.tasks_module_11 import build_import_pipeline
        from celery import chain
        pipeline = build_import_pipeline("http://example.com/data.csv", user_id=1)
        assert pipeline is not None

    def test_process_batch_executes(self):
        from demo.tasks_module_11 import process_batch
        batch = [{"value": 10}, {"value": 20}, {"value": 30}]
        r = process_batch.apply(kwargs={"batch": batch, "batch_id": 1})
        assert r.successful()
        assert r.result["total"] == 60
        assert r.result["count"] == 3

    def test_aggregate_results_executes(self):
        from demo.tasks_module_11 import aggregate_results
        batch_results = [
            {"batch_id": 0, "total": 100, "count": 5},
            {"batch_id": 1, "total": 200, "count": 10},
        ]
        r = aggregate_results.apply(kwargs={"batch_results": batch_results})
        assert r.successful()
        assert r.result["grand_total"] == 300
        assert r.result["total_items"] == 15
        assert r.result["batch_count"] == 2


class TestTaskVersioning:
    """Version-safe task signatures handle old and new message formats."""

    def test_send_email_v1_with_defaults(self):
        """Old message format: only email provided."""
        from demo.tasks_module_11 import send_email_v1
        r = send_email_v1.apply(kwargs={"email": "user@example.com"})
        assert r.successful()
        assert r.result["template_id"] == "default"
        assert r.result["version"] == 1

    def test_send_email_v1_with_new_args(self):
        """New message format: all args provided."""
        from demo.tasks_module_11 import send_email_v1
        r = send_email_v1.apply(kwargs={
            "email": "user@example.com", "template_id": "welcome", "version": 2
        })
        assert r.successful()
        assert r.result["template_id"] == "welcome"
        assert r.result["version"] == 2

    def test_send_email_v2_executes(self):
        from demo.tasks_module_11 import send_email_v2
        r = send_email_v2.apply(kwargs={
            "email": "user@example.com", "template_id": "promo", "locale": "fr"
        })
        assert r.successful()
        assert r.result["locale"] == "fr"

    def test_both_versions_coexist(self):
        """Both v1 and v2 are importable — safe during rolling deploy."""
        from demo.tasks_module_11 import send_email_v1, send_email_v2
        assert send_email_v1 is not None
        assert send_email_v2 is not None
        assert send_email_v1.name != send_email_v2.name


class TestDistributedLock:
    """Distributed lock prevents concurrent execution."""

    def test_distributed_lock_acquired_and_released(self):
        from production_patterns.utils.distributed_lock import distributed_lock
        mock_redis = MagicMock()
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.lock.return_value = mock_lock

        with patch("production_patterns.utils.distributed_lock.redis.Redis.from_url",
                   return_value=mock_redis):
            with distributed_lock("lock:test", timeout=300, blocking=False) as acquired:
                assert acquired is True
        mock_lock.release.assert_called_once()

    def test_distributed_lock_non_blocking_returns_false_when_held(self):
        from production_patterns.utils.distributed_lock import distributed_lock
        mock_redis = MagicMock()
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = False  # lock is held
        mock_redis.lock.return_value = mock_lock

        with patch("production_patterns.utils.distributed_lock.redis.Redis.from_url",
                   return_value=mock_redis):
            with distributed_lock("lock:test", timeout=300, blocking=False) as acquired:
                assert acquired is False
        # Should NOT attempt to release a lock we didn't acquire
        mock_lock.release.assert_not_called()

    def test_sync_inventory_skips_when_lock_held(self):
        from demo.tasks_module_11 import sync_inventory_from_erp
        mock_redis = MagicMock()
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = False  # another worker holds lock
        mock_redis.lock.return_value = mock_lock

        with patch("production_patterns.utils.distributed_lock.redis.Redis.from_url",
                   return_value=mock_redis):
            r = sync_inventory_from_erp.apply()
        assert r.successful()
        assert r.result["status"] == "skipped"
        assert r.result["reason"] == "lock_held"


class TestETAAndExpires:
    """ETA, countdown, and expires task configurations."""

    def test_expire_discount_executes(self):
        from demo.tasks_module_11 import expire_discount
        r = expire_discount.apply(kwargs={"discount_id": 42})
        assert r.successful()
        assert r.result["status"] == "expired"

    def test_send_followup_email_executes(self):
        from demo.tasks_module_11 import send_followup_email
        r = send_followup_email.apply(kwargs={"user_id": 99})
        assert r.successful()
        assert r.result["status"] == "sent"

    def test_all_canvas_tasks_have_acks_late(self):
        from demo.tasks_module_11 import (
            pipeline_download, pipeline_parse, pipeline_validate,
            pipeline_save, process_batch, aggregate_results,
        )
        for task in [pipeline_download, pipeline_parse, pipeline_validate,
                     pipeline_save, process_batch, aggregate_results]:
            assert task.acks_late is True, f"{task.name} missing acks_late=True"


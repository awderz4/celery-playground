"""
tests/test_module_07_beat.py
==============================
Module 7 — Scheduling & django-celery-beat
"""
import pytest
from django.conf import settings


class TestBeatSettings:
    def test_beat_scheduler_is_database(self):
        scheduler = getattr(settings, "CELERY_BEAT_SCHEDULER", None)
        assert scheduler == "django_celery_beat.schedulers:DatabaseScheduler", (
            "Must use DatabaseScheduler for dynamic schedule management. "
            "Rule #8: only ONE Beat instance must run."
        )

    def test_beat_max_loop_interval_set(self):
        interval = getattr(settings, "CELERY_BEAT_MAX_LOOP_INTERVAL", None)
        assert interval is not None
        assert interval >= 10, "CELERY_BEAT_MAX_LOOP_INTERVAL should be >= 10s"


class TestHeartbeatTask:
    def test_heartbeat_task_executes(self):
        from demo.tasks_module_07 import heartbeat_task
        r = heartbeat_task.apply()
        assert r.successful()
        assert r.result["alive"] is True
        assert "worker" in r.result
        assert "ts" in r.result

    def test_heartbeat_has_acks_late(self):
        from demo.tasks_module_07 import heartbeat_task
        assert heartbeat_task.acks_late is True


class TestDailyReportTask:
    def test_daily_report_executes(self):
        from demo.tasks_module_07 import daily_report_task
        r = daily_report_task.apply(kwargs={"user_id": 42})
        assert r.successful()
        assert r.result["user_id"] == 42
        assert r.result["report"] == "generated"

    def test_daily_report_has_time_limits(self):
        from demo.tasks_module_07 import daily_report_task
        assert daily_report_task.soft_time_limit is not None
        assert daily_report_task.time_limit is not None


class TestCanaryTask:
    def test_canary_heartbeat_executes(self):
        from demo.tasks_module_07 import canary_heartbeat
        r = canary_heartbeat.apply()
        assert r.successful()
        assert r.result["alive"] is True


class TestDynamicScheduleManagement:
    @pytest.mark.django_db
    def test_schedule_user_report_creates_periodic_task(self):
        from demo.tasks_module_07 import schedule_user_report
        from django_celery_beat.models import PeriodicTask

        task = schedule_user_report(user_id=9999, hour=9)
        assert task is not None
        assert PeriodicTask.objects.filter(name="daily-report-user-9999").exists()

    @pytest.mark.django_db
    def test_disable_user_report_disables_task(self):
        from demo.tasks_module_07 import schedule_user_report, disable_user_report
        from django_celery_beat.models import PeriodicTask

        schedule_user_report(user_id=8888, hour=10)
        disable_user_report(user_id=8888)

        task = PeriodicTask.objects.get(name="daily-report-user-8888")
        assert task.enabled is False

    @pytest.mark.django_db
    def test_pause_all_tasks(self):
        from demo.tasks_module_07 import schedule_user_report, pause_all_scheduled_tasks
        from django_celery_beat.models import PeriodicTask

        schedule_user_report(user_id=7777, hour=7)
        pause_all_scheduled_tasks()

        enabled_count = PeriodicTask.objects.filter(enabled=True).count()
        assert enabled_count == 0


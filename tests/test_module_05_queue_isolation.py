"""
tests/test_module_05_queue_isolation.py
========================================
Module 5 — Queue Architecture & Isolation
"""
import pytest
from django.conf import settings


class TestQueueRouting:
    """Tasks are explicitly routed to the correct named queues."""

    def test_charge_payment_routes_to_critical(self):
        from demo.tasks_module_05 import charge_payment
        assert charge_payment.queue == "critical"

    def test_revoke_auth_token_routes_to_critical(self):
        from demo.tasks_module_05 import revoke_auth_token
        assert revoke_auth_token.queue == "critical"

    def test_send_email_notification_routes_to_notifications(self):
        from demo.tasks_module_05 import send_email_notification
        assert send_email_notification.queue == "notifications"

    def test_send_push_notification_routes_to_notifications(self):
        from demo.tasks_module_05 import send_push_notification
        assert send_push_notification.queue == "notifications"

    def test_resize_image_routes_to_media(self):
        from demo.tasks_module_05 import resize_image
        assert resize_image.queue == "media"

    def test_transcode_video_routes_to_media(self):
        from demo.tasks_module_05 import transcode_video
        assert transcode_video.queue == "media"

    def test_import_csv_routes_to_imports(self):
        from demo.tasks_module_05 import import_csv
        assert import_csv.queue == "imports"

    def test_bulk_user_create_routes_to_imports(self):
        from demo.tasks_module_05 import bulk_user_create
        assert bulk_user_create.queue == "imports"


class TestCriticalQueueTasks:
    """Critical queue tasks have strict SLA settings."""

    def test_charge_payment_has_acks_late(self):
        from demo.tasks_module_05 import charge_payment
        assert charge_payment.acks_late is True

    def test_charge_payment_has_time_limits(self):
        from demo.tasks_module_05 import charge_payment
        assert charge_payment.soft_time_limit is not None
        assert charge_payment.time_limit is not None
        assert charge_payment.soft_time_limit < charge_payment.time_limit

    def test_charge_payment_executes(self):
        from demo.tasks_module_05 import charge_payment
        r = charge_payment.apply(kwargs={"order_id": "ORD-001", "amount": 99.99})
        assert r.successful()
        assert r.result["status"] == "charged"


class TestNotificationQueueTasks:
    """Notification tasks have rate limits and gevent-appropriate settings."""

    def test_send_email_has_rate_limit(self):
        from demo.tasks_module_05 import send_email_notification
        assert send_email_notification.rate_limit is not None

    def test_send_email_executes(self):
        from demo.tasks_module_05 import send_email_notification
        r = send_email_notification.apply(kwargs={
            "to_address": "test@example.com", "subject": "Hi"
        })
        assert r.successful()
        assert r.result["status"] == "sent"


class TestMediaQueueTasks:
    """Media tasks have long time limits for CPU-heavy work."""

    def test_resize_image_has_long_time_limit(self):
        from demo.tasks_module_05 import resize_image
        assert resize_image.soft_time_limit >= 600

    def test_resize_image_executes(self):
        from demo.tasks_module_05 import resize_image
        r = resize_image.apply(kwargs={"image_id": 1, "width": 800, "height": 600})
        assert r.successful()
        assert r.result["status"] == "resized"


class TestImportQueueTasks:
    """Import tasks have the longest time limits."""

    def test_import_csv_has_very_long_time_limit(self):
        from demo.tasks_module_05 import import_csv
        assert import_csv.soft_time_limit >= 1800  # 30 minutes

    def test_import_csv_executes(self):
        from demo.tasks_module_05 import import_csv
        r = import_csv.apply(kwargs={"file_id": 1, "user_id": 42})
        assert r.successful()
        assert r.result["rows_imported"] == 1000


class TestQueueSettings:
    """Multi-queue routing configuration is present in settings."""

    def test_task_queues_configured(self):
        queues = getattr(settings, "CELERY_TASK_QUEUES", None)
        assert queues is not None, "CELERY_TASK_QUEUES must be configured"

    def test_default_queue_is_set(self):
        default_q = getattr(settings, "CELERY_TASK_DEFAULT_QUEUE", None)
        assert default_q is not None
        assert default_q == "default"

    def test_task_routes_configured(self):
        routes = getattr(settings, "CELERY_TASK_ROUTES", None)
        assert routes is not None, "CELERY_TASK_ROUTES must be configured"
        assert len(routes) > 0


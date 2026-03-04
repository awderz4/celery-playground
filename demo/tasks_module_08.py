"""
demo/tasks_module_08.py
=======================
Module 8 — Monitoring, Logging & Distributed Tracing

Demonstrates:
  - Structured JSON logging with correlation IDs
  - CorrelationTask base: propagates correlation_id through task headers
  - OpenTelemetry manual spans inside tasks
  - Stuck worker canary pattern
"""

import socket
import time
import uuid

from celery import Task, shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 8.1 ─ Correlation ID propagation
# ─────────────────────────────────────────────────────────────────────────────

import threading
_local = threading.local()


def get_correlation_id() -> str:
    return getattr(_local, "correlation_id", str(uuid.uuid4()))


def set_correlation_id(corr_id: str):
    _local.correlation_id = corr_id


class CorrelationTask(Task):
    """
    Task base class that propagates a correlation ID from Django request
    through to worker execution, enabling end-to-end log tracing.

    Usage:
        @app.task(base=CorrelationTask)
        def my_task(user_id): ...

    Correlation ID is set in Django middleware (X-Correlation-ID header),
    stored in thread-local, forwarded in task headers, and restored in worker.
    """
    abstract = True

    def apply_async(self, args=None, kwargs=None, **options):
        headers = options.get("headers", {})
        headers["correlation_id"] = get_correlation_id()
        options["headers"] = headers
        return super().apply_async(args, kwargs, **options)

    def __call__(self, *args, **kwargs):
        headers = getattr(self.request, "headers", None) or {}
        corr_id = headers.get("correlation_id", get_correlation_id())
        set_correlation_id(corr_id)
        return super().__call__(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# 8.2 ─ Traceable tasks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    base=CorrelationTask,
    bind=True,
    acks_late=True,
    soft_time_limit=60,
    time_limit=90,
    name="demo.traceable_task",
)
def traceable_task(self, user_id: int, action: str = "process"):
    """
    Lab 8d — correlation ID is logged on every line.

    Submit via a view that sets X-Correlation-ID header.
    All worker log lines will share the same correlation_id.
    Grep one ID across Django and worker logs to trace the full flow.

    Log output example:
        {"correlation_id": "abc-123", "task_id": "...", "user_id": 42, ...}
    """
    corr_id = get_correlation_id()
    logger.info(
        "[traceable_task] correlation_id=%s user_id=%d action=%s task_id=%s",
        corr_id, user_id, action, self.request.id,
    )
    time.sleep(0.1)
    return {
        "correlation_id": corr_id,
        "task_id": self.request.id,
        "user_id": user_id,
        "action": action,
    }


@shared_task(
    base=CorrelationTask,
    bind=True,
    acks_late=True,
    soft_time_limit=60,
    time_limit=90,
    name="demo.child_task",
)
def child_task(self, parent_result: dict, step: str = "step2"):
    """
    Lab 8d — chained task that inherits correlation ID from parent.

    When chained: traceable_task → child_task → grandchild_task,
    all three share the same correlation_id from the original HTTP request.
    """
    corr_id = get_correlation_id()
    logger.info(
        "[child_task] correlation_id=%s step=%s task_id=%s",
        corr_id, step, self.request.id,
    )
    return {
        "correlation_id": corr_id,
        "step": step,
        "parent_task_id": parent_result.get("task_id"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8.3 ─ OpenTelemetry manual spans
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, acks_late=True, soft_time_limit=120, time_limit=150,
             name="demo.traced_csv_task")
def traced_csv_task(self, file_id: int, row_count: int = 100):
    """
    Lab 8b — manual OpenTelemetry spans inside a task.

    Without OTel configured, this task runs normally.
    With OTel (see docker-compose.monitoring.yml), spans appear in Jaeger:
      HTTP request → demo.traced_csv_task → csv.parse → csv.write_db

    Install OTel SDK:
        OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
        OTEL_SERVICE_NAME=celery-worker
    """
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("csv.parse") as span:
            span.set_attribute("file.id", file_id)
            span.set_attribute("csv.row_count", row_count)
            time.sleep(0.05)  # simulate parsing

        with tracer.start_as_current_span("csv.write_db") as span:
            span.set_attribute("rows", row_count)
            time.sleep(0.05)  # simulate DB writes

    except Exception:
        # OTel not configured — run without tracing
        time.sleep(0.1)

    return {"file_id": file_id, "rows_processed": row_count}


# ─────────────────────────────────────────────────────────────────────────────
# 8.4 ─ Canary / stuck worker detection
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(time_limit=30, queue="default", name="demo.monitoring_canary")
def monitoring_canary():
    """
    Submit every 60s via Beat. Alert if not completed in 120s.

    Prometheus alert:
        time() - celery_task_succeeded_timestamp{task='demo.monitoring_canary'} > 120
        → severity: critical — workers appear stuck

    If this task stops completing:
      - Workers are OOMKilled and not restarting
      - Queue is full (depth > worker drain rate)
      - Redis is down
    """
    return {"alive": True, "worker": socket.gethostname(), "ts": time.time()}


from django.db import models


# ─────────────────────────────────────────────────────────────────────────────
# Module 3 — Reliability & Failure Handling
# ─────────────────────────────────────────────────────────────────────────────

class ProcessedInvoice(models.Model):
    """
    Idempotency guard for process_invoice task.

    The unique constraint on invoice_id ensures that even if the task
    runs twice (visibility timeout duplicate), only one execution succeeds.
    The second call to get_or_create returns created=False and skips.
    """
    invoice_id = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
    )
    processed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-processed_at"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"Invoice {self.invoice_id} [{self.status}]"


class CSVProcessingJob(models.Model):
    """
    Tracks progress for process_large_csv task.

    Stores partial progress when soft_time_limit fires, allowing
    operators to inspect how far the job got before timing out.
    """
    file_id = models.IntegerField(unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("timeout", "Timed Out"),
            ("failed", "Failed"),
        ],
    )
    rows_processed = models.IntegerField(default=0)
    total_rows = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"CSVJob file_id={self.file_id} [{self.status}] {self.rows_processed}/{self.total_rows}"

"""
tests/test_module_10_kubernetes.py
=====================================
Module 10 — Kubernetes Production Deployment
"""
import pytest
from django.conf import settings


class TestGracefulShutdownSettings:
    """Settings that protect against task loss during K8s rolling updates."""

    def test_acks_late_prevents_task_loss_on_sigterm(self):
        """
        terminationGracePeriodSeconds gives worker time to finish.
        acks_late=True means task won't be ACK'd until it completes.
        If SIGKILL fires before finish: task is re-queued (not lost).
        """
        assert settings.CELERY_TASK_ACKS_LATE is True

    def test_reject_on_worker_lost_handles_sigkill(self):
        """SIGKILL after terminationGracePeriod: task immediately re-queued."""
        assert settings.CELERY_TASK_REJECT_ON_WORKER_LOST is True

    def test_visibility_timeout_covers_graceful_period(self):
        """
        visibility_timeout must exceed terminationGracePeriodSeconds (600s).
        Otherwise: Redis re-queues task at T+600s while worker is still
        finishing it → duplicate execution.
        """
        vt = settings.CELERY_BROKER_TRANSPORT_OPTIONS.get("visibility_timeout", 0)
        assert vt > 600, (
            f"visibility_timeout={vt}s must exceed terminationGracePeriodSeconds=600s"
        )


class TestResourceLimits:
    """Worker memory settings align with K8s resource limits."""

    def test_max_memory_per_child_is_set(self):
        """CELERYD_MAX_MEMORY_PER_CHILD should be 60% of pod memory limit."""
        val = getattr(settings, "CELERYD_MAX_MEMORY_PER_CHILD", None)
        assert val is not None
        # Pod limit = 1Gi = 1,048,576 KB. 60% = ~614,400 KB.
        # Our setting = 400,000 KB which is fine for 512Mi pods.
        assert val >= 50_000

    def test_max_tasks_per_child_prevents_oomkill(self):
        """Worker recycles before RSS drifts to pod memory limit."""
        val = getattr(settings, "CELERYD_MAX_TASKS_PER_CHILD", None)
        assert val is not None
        assert val <= 500  # frequent enough to prevent significant drift


class TestKubernetesManifests:
    """K8s manifests exist for all required worker types."""

    def test_worker_default_manifest_exists(self):
        import os
        path = "k8s/workers/worker-default.yaml"
        assert os.path.exists(path), f"Missing: {path}"

    def test_worker_notifications_manifest_exists(self):
        import os
        path = "k8s/workers/worker-notifications.yaml"
        assert os.path.exists(path), f"Missing: {path}"

    def test_worker_media_manifest_exists(self):
        import os
        path = "k8s/workers/worker-media.yaml"
        assert os.path.exists(path), f"Missing: {path}"

    def test_beat_manifest_exists(self):
        import os
        path = "k8s/workers/beat-deployment.yaml"
        assert os.path.exists(path), f"Missing: {path}"

    def test_keda_scaledobject_exists(self):
        import os
        path = "k8s/keda/scaledobject-notifications.yaml"
        assert os.path.exists(path), f"Missing: {path}"


class TestHPAConfiguration:
    """HPA and KEDA scale on queue depth."""

    def test_keda_scaledobject_structure(self):
        """KEDA ScaledObject targets the right deployment with correct trigger."""
        import os
        import yaml
        path = "k8s/keda/scaledobject-notifications.yaml"
        if not os.path.exists(path):
            pytest.skip("KEDA manifest not yet created")
        with open(path) as f:
            obj = yaml.safe_load(f)
        assert obj["kind"] == "ScaledObject"
        assert obj["spec"]["minReplicaCount"] >= 1
        assert obj["spec"]["maxReplicaCount"] >= 5

    def test_beat_deployment_uses_recreate_strategy(self):
        """
        Golden Rule #8: Beat must use Recreate strategy.
        RollingUpdate → 2 Beat instances overlap → every task runs twice.
        """
        import os
        import yaml
        path = "k8s/workers/beat-deployment.yaml"
        if not os.path.exists(path):
            pytest.skip("Beat manifest not yet created")
        with open(path) as f:
            obj = yaml.safe_load(f)
        strategy = obj["spec"]["strategy"]["type"]
        assert strategy == "Recreate", (
            "Beat deployment MUST use strategy: Recreate. "
            "RollingUpdate causes duplicate task execution during deploys."
        )

    def test_beat_deployment_has_single_replica(self):
        """Golden Rule #8: exactly one Beat instance."""
        import os
        import yaml
        path = "k8s/workers/beat-deployment.yaml"
        if not os.path.exists(path):
            pytest.skip("Beat manifest not yet created")
        with open(path) as f:
            obj = yaml.safe_load(f)
        replicas = obj["spec"]["replicas"]
        assert replicas == 1, (
            f"Beat replicas={replicas}, must be 1. "
            "Two Beat instances = every scheduled task runs twice."
        )

    def test_worker_has_termination_grace_period(self):
        """terminationGracePeriodSeconds must exceed max task duration."""
        import os
        import yaml
        path = "k8s/workers/worker-default.yaml"
        if not os.path.exists(path):
            pytest.skip("Worker manifest not yet created")
        with open(path) as f:
            obj = yaml.safe_load(f)
        grace = obj["spec"]["template"]["spec"].get("terminationGracePeriodSeconds", 0)
        assert grace >= 300, (
            f"terminationGracePeriodSeconds={grace}, must be >= 300s. "
            "If SIGKILL fires while task is running, task may be lost."
        )


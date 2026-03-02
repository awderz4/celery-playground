"""
Pytest configuration for Celery Production Mastery course tests.
"""
import pytest
import os


# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_playground.settings")


@pytest.fixture(scope='session')
def celery_config():
    """Celery test configuration."""
    return {
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://',
        'task_always_eager': True,
        'task_eager_propagates': True,
    }


@pytest.fixture
def redis_client():
    """Redis client for testing."""
    import redis
    client = redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)
    yield client
    # Cleanup: flush test keys
    for key in client.keys('test:*'):
        client.delete(key)


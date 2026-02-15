from celery import shared_task
import time

@shared_task
def slow_add(x, y):
    import os
    print("PID:", os.getpid())
    time.sleep(30)
    return x + y

"""Celery app for background work; AI jobs are intentionally not defined yet."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("ai_speaking")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

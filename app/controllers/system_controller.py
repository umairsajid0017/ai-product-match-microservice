"""
System and Monitoring logic (Controller).

Handles health checks and queue management.
"""

from app.schemas.requests import HealthResponse
from app.services.task_queue import get_queue_status, get_dead_letters, clear_dead_letters


async def health_check():
    """Returns application health status."""
    return HealthResponse(status="ok")


async def queue_status():
    """Returns persistent task queue status."""
    return get_queue_status()


async def dead_letters():
    """Returns tasks in dead letter queue."""
    return {"tasks": get_dead_letters()}


async def clear_dead_letter_queue():
    """Clears the dead letter queue."""
    clear_dead_letters()
    return {"status": "dead letter queue cleared"}

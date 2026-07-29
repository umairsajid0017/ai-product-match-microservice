"""
System and Monitoring logic (Controller).

Handles health checks and queue management (SQS).
"""

from app.schemas.requests import HealthResponse
from app.services import sqs_queue


async def health_check():
    """Returns application health status."""
    return HealthResponse(status="ok")


async def queue_status():
    """Returns SQS queue status."""
    return sqs_queue.get_queue_status()


async def dead_letters():
    """Returns tasks peeked from the SQS dead letter queue."""
    return {"tasks": sqs_queue.get_dead_letters()}


async def clear_dead_letter_queue():
    """Clears / purges the SQS dead letter queue."""
    deleted = sqs_queue.clear_dead_letters()
    return {
        "status": "dead letter queue cleared",
        "deleted": deleted,
    }

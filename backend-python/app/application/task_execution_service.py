"""Task execution facade for Crew orchestration."""

from app.services.orchestration_service import OrchestrationService

TaskExecutionService = OrchestrationService

__all__ = ["OrchestrationService", "TaskExecutionService"]

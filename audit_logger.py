from typing import Any, Dict, Optional

from runtime_models import CommandContext, CorrectionResult, ExecutionResult, RouteDecision
from storage.sqlite_store import SQLiteStore


class AuditLogger:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def log_command(
        self,
        context: CommandContext,
        correction: CorrectionResult,
        route: RouteDecision,
        execution: ExecutionResult,
    ) -> None:
        self.store.log_command_history(
            raw_text=context.raw_text,
            corrected_text=correction.corrected_text,
            route=route.provider,
            action=execution.action,
            target=execution.target,
            success=execution.success,
            confidence=execution.confidence,
            latency_ms=execution.latency_ms,
        )

    def log_integration_event(
        self,
        platform: str,
        event_type: str,
        confidence: float,
        decision: str,
        details: Dict[str, Any],
        task_id: Optional[int] = None,
    ) -> None:
        self.store.add_integration_event(
            task_id=task_id,
            platform=platform,
            event_type=event_type,
            confidence=confidence,
            decision=decision,
            details=details,
        )

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class CommandContext:
    raw_text: str
    normalized_text: str
    timestamp: str
    source: str
    session_id: str
    scan_snapshot_ref: str

    @classmethod
    def from_text(
        cls,
        raw_text: str,
        normalized_text: str,
        source: str = "voice",
        session_id: str = "default",
        scan_snapshot_ref: str = "",
    ) -> "CommandContext":
        return cls(
            raw_text=raw_text,
            normalized_text=normalized_text,
            timestamp=datetime.utcnow().isoformat(),
            source=source,
            session_id=session_id,
            scan_snapshot_ref=scan_snapshot_ref,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CorrectionResult:
    original_text: str
    corrected_text: str
    confidence: float
    strategy_scores: Dict[str, float] = field(default_factory=dict)
    requires_confirmation: bool = False
    candidates: List[str] = field(default_factory=list)
    reason: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteDecision:
    provider: str
    reason: str
    cache_hit: bool
    estimated_cost: float
    result_type: str
    fallback_chain: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    success: bool
    action: str
    target: Optional[str]
    response: str
    confidence: float
    provider: str
    latency_ms: int
    side_effects: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IntegrationTask:
    platform: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 5
    safe_mode: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

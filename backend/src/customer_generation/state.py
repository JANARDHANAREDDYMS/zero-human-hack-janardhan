"""Explicit run state and limits; no hidden conversation memory."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RunLimits:
    max_stage_calls: int = 6
    max_total_tokens: int = 40000
    max_tokens_per_call: int = 6000
    max_cost_usd: float = 1.0
    timeout_seconds: float = 120
    max_elapsed_seconds: float = 900
    max_corrections: int = 1
    pilot_per_segment: int = 2


@dataclass
class StageResponse:
    data: dict[str, Any]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)


class StageBackend(Protocol):
    """Future adapter dispatches model/research stages; fixtures use no services.

    Live implementations must apply timeout/token/cost allowances at transport
    boundaries and report actual aggregate stage usage. The harness cannot
    cancel a synchronous provider already executing or reverse a provider bill.
    """
    mode: str
    name: str

    def execute(self, stage: str, payload: dict, allowances: dict) -> StageResponse: ...


@dataclass
class RunState:
    run_id: str
    status: str = 'running'
    stage: str = 'created'
    mode: str = 'offline_fixture'
    backend: str = ''
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    stage_calls: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    corrections: int = 0
    cost_uncertain: bool = False
    artifacts: dict[str, str] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    error: dict | None = None

    def to_dict(self):
        return asdict(self)

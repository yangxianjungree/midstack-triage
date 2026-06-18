"""Execution mode contracts for evidence collection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Literal


ExecutionModeName = Literal["remote", "local", "offline"]


@dataclass(frozen=True)
class ExecutionMode:
    """One supported execution-plane mode."""

    name: ExecutionModeName
    description: str
    collects_live_evidence: bool
    requires_transport: bool


REMOTE_MODE = ExecutionMode(
    name="remote",
    description="Collect live evidence through a jump host or fault-domain host.",
    collects_live_evidence=True,
    requires_transport=True,
)
LOCAL_MODE = ExecutionMode(
    name="local",
    description="Collect live evidence from the local machine without SSH transport.",
    collects_live_evidence=True,
    requires_transport=False,
)
OFFLINE_MODE = ExecutionMode(
    name="offline",
    description="Analyse existing incident, fixture, or remote-run files without executing collection commands.",
    collects_live_evidence=False,
    requires_transport=False,
)

SUPPORTED_EXECUTION_MODES: Dict[str, ExecutionMode] = {
    item.name: item for item in (REMOTE_MODE, LOCAL_MODE, OFFLINE_MODE)
}
DEFAULT_EXECUTION_MODE = REMOTE_MODE.name


def resolve_execution_mode(value: str | None) -> ExecutionMode:
    name = str(value or DEFAULT_EXECUTION_MODE).strip().lower()
    try:
        return SUPPORTED_EXECUTION_MODES[name]
    except KeyError as exc:
        raise ValueError("unsupported execution mode: %s" % name) from exc


def execution_mode_names() -> Iterable[str]:
    return SUPPORTED_EXECUTION_MODES.keys()


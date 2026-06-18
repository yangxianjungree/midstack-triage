"""Event relation helpers for Phase 2 inventory."""

from __future__ import annotations

from typing import Any, Dict, List


def related_event(event: Dict[str, Any], names: List[str]) -> bool:
    involved = event.get("involvedObject") or event.get("regarding") or {}
    return str(involved.get("name") or "") in names

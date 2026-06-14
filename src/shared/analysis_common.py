"""Small shared helpers for reading and flattening analysis payloads."""

from __future__ import annotations

from typing import Any, Dict, List


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def flatten_strings(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: List[str] = []
        for item in value.values():
            result.extend(flatten_strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(flatten_strings(item))
        return result
    return []


def analysis_text(analysis: Dict[str, Any]) -> str:
    return "\n".join(flatten_strings(analysis)).lower()

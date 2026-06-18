"""Rule-based Phase 4 analysers by middleware."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Tuple


_ANALYSER_MODULES = {
    "mongodb": "phases.phase4.rules.mongodb",
    "pulsar": "phases.phase4.rules.pulsar",
}
_SUPPORT_STATES = {
    "mongodb": "active_mvp",
    "pulsar": "contract_path",
}


def supported_middlewares() -> Tuple[str, ...]:
    return tuple(sorted(_ANALYSER_MODULES))


def middleware_support_state(middleware: str) -> str:
    return _SUPPORT_STATES.get(middleware, "unsupported")


def generate_rule_analysis(middleware: str, input_dir: Path) -> Dict[str, Any]:
    module_name = _ANALYSER_MODULES.get(middleware)
    if not module_name:
        raise KeyError("unsupported rule analysis middleware: %s" % middleware)
    module = import_module(module_name)
    return module.generate_analysis(input_dir)

generate_rule_draft = generate_rule_analysis

__all__ = ["generate_rule_analysis", "generate_rule_draft", "middleware_support_state", "supported_middlewares"]

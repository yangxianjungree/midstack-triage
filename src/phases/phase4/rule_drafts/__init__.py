"""Rule-based Phase 4 draft analysers by middleware."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Tuple


_ANALYSER_MODULES = {
    "mongodb": "phases.phase4.rule_drafts.mongodb",
    "pulsar": "phases.phase4.rule_drafts.pulsar",
}


def supported_middlewares() -> Tuple[str, ...]:
    return tuple(sorted(_ANALYSER_MODULES))


def generate_rule_draft(middleware: str, input_dir: Path) -> Dict[str, Any]:
    module_name = _ANALYSER_MODULES.get(middleware)
    if not module_name:
        raise KeyError("unsupported rule draft middleware: %s" % middleware)
    module = import_module(module_name)
    return module.generate_analysis(input_dir)


__all__ = ["generate_rule_draft", "supported_middlewares"]

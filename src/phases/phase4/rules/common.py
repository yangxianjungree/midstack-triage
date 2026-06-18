"""Shared helpers for Phase 4 rule analysers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import sys

SRC_DIR = Path(__file__).resolve().parents[3]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.io import load_yaml_object, write_yaml_object


def load_yaml(path: Path) -> Dict[str, Any]:
    return load_yaml_object(path)


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    write_yaml_object(path, payload)

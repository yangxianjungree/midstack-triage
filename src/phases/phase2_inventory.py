"""Compatibility module for legacy Phase 2 imports."""

from __future__ import annotations

import sys

from phases.phase2 import inventory as _impl


sys.modules[__name__] = _impl

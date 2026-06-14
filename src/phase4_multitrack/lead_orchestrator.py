"""Compatibility module for legacy Phase 4 lead orchestrator imports."""

from __future__ import annotations

import sys

from phases.phase4.multitrack import lead_orchestrator as _impl


sys.modules[__name__] = _impl

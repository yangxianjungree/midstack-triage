"""Compatibility module for legacy Phase 4 agent interface imports."""

from __future__ import annotations

import sys

from phases.phase4.multitrack import agent_interface as _impl


sys.modules[__name__] = _impl

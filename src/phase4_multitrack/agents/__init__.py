"""Compatibility package for legacy Phase 4 agent imports."""

from __future__ import annotations

import sys

from phases.phase4.multitrack import agents as _impl


sys.modules[__name__] = _impl

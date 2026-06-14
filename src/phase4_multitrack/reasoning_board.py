"""Compatibility module for legacy Phase 4 reasoning board imports."""

from __future__ import annotations

import sys

from phases.phase4.multitrack import reasoning_board as _impl


sys.modules[__name__] = _impl

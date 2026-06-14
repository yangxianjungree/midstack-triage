"""Compatibility module for legacy Phase 4 imports."""

from __future__ import annotations

import sys

from phases.phase4 import reasoning as _impl


sys.modules[__name__] = _impl

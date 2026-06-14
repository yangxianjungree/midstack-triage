"""Compatibility module for legacy Phase 1 imports."""

from __future__ import annotations

import sys

from phases.phase1 import startup as _impl


sys.modules[__name__] = _impl

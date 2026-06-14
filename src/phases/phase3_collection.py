"""Compatibility module for legacy Phase 3 imports."""

from __future__ import annotations

import sys

from phases.phase3 import collection as _impl


sys.modules[__name__] = _impl

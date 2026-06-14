"""Compatibility module for legacy Phase 4 hypothesis track imports."""

from __future__ import annotations

import sys

from phases.phase4.multitrack import hypothesis_track as _impl


sys.modules[__name__] = _impl

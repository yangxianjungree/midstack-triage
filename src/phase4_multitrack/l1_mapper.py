"""Compatibility module for legacy Phase 4 L1 mapper imports."""

from __future__ import annotations

import sys

from phases.phase4.multitrack import l1_mapper as _impl


sys.modules[__name__] = _impl

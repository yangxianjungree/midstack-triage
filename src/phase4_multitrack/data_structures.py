"""Compatibility module for legacy Phase 4 data structure imports."""

from __future__ import annotations

import sys

from phases.phase4.multitrack import data_structures as _impl


sys.modules[__name__] = _impl

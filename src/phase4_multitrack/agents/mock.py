"""Compatibility module for legacy Phase 4 mock agent imports."""

from __future__ import annotations

import sys

from phases.phase4.multitrack.agents import mock as _impl


sys.modules[__name__] = _impl

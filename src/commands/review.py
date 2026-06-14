"""Review command runtime."""

from __future__ import annotations

from phases.phase5.review import run_review


def run(args) -> int:
    return run_review(args)

"""Finalize-analysis command runtime."""

from __future__ import annotations

from phases.phase5.finalize import finalize_analysis


def run(args, normalize_collection_report_gaps) -> int:
    return finalize_analysis(args, normalize_collection_report_gaps)

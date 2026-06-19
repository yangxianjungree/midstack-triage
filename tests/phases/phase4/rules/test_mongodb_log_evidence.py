#!/usr/bin/env python3

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase4.rules.mongodb_log_evidence import evidence_from_log_highlights


def test_log_highlight_evidence_filters_deduplicates_and_prioritizes_material_logs():
    signal_bundle = {
        "log_highlights": [
            {
                "pod_ref": "mongo-0",
                "log_type": "current",
                "category": "info",
                "message": "waiting for startup",
            },
            {
                "pod_ref": "mongo-0",
                "log_type": "current",
                "category": "connection",
                "message": 'HostUnreachable: {"host":"mongo-1:27017"} connection refused',
            },
            {
                "pod_ref": "mongo-0",
                "log_type": "current",
                "category": "connection",
                "message": 'HostUnreachable: {"host":"mongo-1:27017"} connection refused',
            },
            {
                "pod_ref": "mongo-0",
                "log_type": "file_tail",
                "category": "storage",
                "message": "WiredTiger fatal read error",
            },
        ]
    }

    evidence = evidence_from_log_highlights(signal_bundle)

    assert len(evidence) == 2
    assert "file_tail" in evidence[0]["detail"]
    assert "WiredTiger fatal read error" in evidence[0]["detail"]
    assert "HostUnreachable" in evidence[1]["detail"]

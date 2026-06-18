#!/usr/bin/env python3

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.asset_resolver import knowledge_candidates_for_scenario  # noqa: E402


def write_metadata(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_knowledge_candidates_scan_runbook_command_and_skill_in_order(tmp_path):
    write_metadata(
        tmp_path / "domains" / "mongodb" / "skills" / "connectivity" / "triage" / "metadata.yaml",
        {
            "id": "mongodb-triage-connection-failure",
            "title": "Triage MongoDB Connection Failure",
            "middleware": "mongodb",
            "primary_scenario": "connection-failure",
        },
    )
    write_metadata(
        tmp_path / "domains" / "mongodb" / "commands" / "connectivity" / "check" / "metadata.yaml",
        {
            "id": "mongodb-check-connectivity",
            "title": "Check MongoDB Connectivity",
            "middleware": "mongodb",
            "scenario": "connection-failure",
        },
    )
    write_metadata(
        tmp_path / "domains" / "mongodb" / "runbooks" / "connectivity" / "connection" / "metadata.yaml",
        {
            "id": "mongodb-connection-failure",
            "title": "MongoDB Connection Failure",
            "middleware": "mongodb",
            "scenario": "connection-failure",
        },
    )
    write_metadata(
        tmp_path / "domains" / "pulsar" / "runbooks" / "broker" / "topic" / "metadata.yaml",
        {
            "id": "pulsar-topic-backlog",
            "title": "Pulsar Topic Backlog",
            "middleware": "pulsar",
            "scenario": "connection-failure",
        },
    )

    candidates = knowledge_candidates_for_scenario("mongodb", "connection-failure", tmp_path)

    assert [item["candidate_type"] for item in candidates] == ["runbook", "command", "skill"]
    assert [item["title"] for item in candidates] == [
        "MongoDB Connection Failure",
        "Check MongoDB Connectivity",
        "Triage MongoDB Connection Failure",
    ]
    assert candidates[0]["asset_path"] == "domains/mongodb/runbooks/connectivity/connection"
    assert candidates[0]["reason"] == "Existing MongoDB runbook asset matches scenario connection-failure."


def test_knowledge_candidates_ignore_unknown_baseline_and_mismatched_middleware(tmp_path):
    write_metadata(
        tmp_path / "domains" / "mongodb" / "runbooks" / "connectivity" / "connection" / "metadata.yaml",
        {
            "id": "mongodb-connection-failure",
            "title": "MongoDB Connection Failure",
            "middleware": "pulsar",
            "scenario": "connection-failure",
        },
    )

    assert knowledge_candidates_for_scenario("mongodb", "", tmp_path) == []
    assert knowledge_candidates_for_scenario("mongodb", "baseline", tmp_path) == []
    assert knowledge_candidates_for_scenario("mongodb", "connection-failure", tmp_path) == []

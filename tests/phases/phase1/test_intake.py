import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase1.intake import build_start_intake  # noqa: E402


def args(**overrides):
    values = {
        "middleware": "mongodb",
        "environment_mode": "remote",
        "environment_ip": ["192.0.2.10"],
        "username": "root",
        "password": "secret",
        "port": 22,
        "customer_clue": "MongoDB member is unhealthy",
        "namespace": "",
        "cluster_id": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_remote_intake_requires_ssh_access_fields():
    intake = build_start_intake(args(environment_ip=[], username="", password=""))

    assert intake["environment_mode"] == "remote"
    assert intake["execution_mode"] == "remote"
    assert intake["status"] == "blocked"
    assert [item["code"] for item in intake["blocking_items"]] == [
        "missing_environment_ip",
        "missing_username",
        "missing_password",
    ]
    assert [item["field"] for item in intake["follow_up_questions"]] == [
        "environment_ip",
        "username",
        "password",
    ]


def test_remote_intake_is_ready_for_validation_when_required_fields_exist():
    intake = build_start_intake(args())

    assert intake["environment_mode"] == "remote"
    assert intake["status"] == "ready_for_validation"
    assert intake["blocking_items"] == []
    assert intake["follow_up_questions"] == []


def test_local_intake_does_not_require_ssh_credentials_but_blocks_until_executor_exists():
    intake = build_start_intake(args(environment_mode="local", environment_ip=[], username="", password=""))

    assert intake["environment_mode"] == "local"
    assert intake["execution_mode"] == "local"
    assert intake["status"] == "blocked"
    assert [item["code"] for item in intake["blocking_items"]] == ["local_start_not_implemented"]
    assert intake["follow_up_questions"][0]["field"] == "execution_mode"


def test_offline_intake_guides_user_to_existing_artifacts():
    intake = build_start_intake(args(environment_mode="offline", environment_ip=[], username="", password=""))

    assert intake["environment_mode"] == "offline"
    assert intake["execution_mode"] == "offline"
    assert intake["status"] == "blocked"
    assert [item["code"] for item in intake["blocking_items"]] == ["offline_start_needs_artifacts"]
    assert intake["follow_up_questions"][0]["field"] == "artifact_source"

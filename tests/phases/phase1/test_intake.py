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
        "artifact_source": "",
        "pasted_evidence": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_remote_intake_requires_ssh_access_fields():
    intake = build_start_intake(args(environment_ip=[], username="", password=""))

    assert intake["environment_mode"] == "remote"
    assert intake["execution_mode"] == "remote"
    assert intake["intake_scenario"]["id"] == "remote_ssh"
    assert intake["status"] == "blocked"
    assert [item["code"] for item in intake["blocking_items"]] == [
        "missing_environment_ip",
        "missing_username",
        "missing_password",
    ]
    assert [item["field"] for item in intake["follow_up_questions"]] == [
        "environment_mode",
        "environment_ip",
        "username",
        "password",
    ]


def test_remote_intake_is_ready_for_validation_when_required_fields_exist():
    intake = build_start_intake(args())

    assert intake["environment_mode"] == "remote"
    assert intake["intake_scenario"] == {
        "id": "remote_ssh",
        "environment_class": "unknown",
        "access_pattern": "ssh_runtime",
        "evidence_source": "live_remote",
        "readiness": "supported",
    }
    assert intake["status"] == "ready_for_validation"
    assert intake["blocking_items"] == []
    assert intake["follow_up_questions"] == []


def test_local_intake_does_not_require_ssh_credentials_but_blocks_until_executor_exists():
    intake = build_start_intake(args(environment_mode="local", environment_ip=[], username="", password=""))

    assert intake["environment_mode"] == "local"
    assert intake["execution_mode"] == "local"
    assert intake["intake_scenario"]["id"] == "local_fault_cluster"
    assert intake["intake_scenario"]["readiness"] == "blocked_until_local_executor"
    assert intake["status"] == "blocked"
    assert [item["code"] for item in intake["blocking_items"]] == ["local_start_not_implemented"]
    assert intake["follow_up_questions"][0]["field"] == "execution_mode"


def test_local_intake_follow_up_mentions_available_local_context():
    intake = build_start_intake(
        args(
            environment_mode="local",
            environment_ip=[],
            username="",
            password="",
            local_context={
                "status": "available",
                "reason": "",
                "current_context": "prod-cluster",
            },
        )
    )

    assert intake["status"] == "blocked"
    assert intake["local_context"]["current_context"] == "prod-cluster"
    assert "prod-cluster" in intake["follow_up_questions"][0]["question"]


def test_offline_intake_guides_user_to_existing_artifacts():
    intake = build_start_intake(args(environment_mode="offline", environment_ip=[], username="", password=""))

    assert intake["environment_mode"] == "offline"
    assert intake["execution_mode"] == "offline"
    assert intake["intake_scenario"]["id"] == "offline_existing_artifacts"
    assert intake["status"] == "blocked"
    assert [item["code"] for item in intake["blocking_items"]] == ["offline_start_needs_artifacts"]
    assert intake["follow_up_questions"][0]["field"] == "artifact_source"


def test_offline_production_clue_is_classified_separately_from_existing_artifacts():
    intake = build_start_intake(args(environment_mode="offline", customer_clue="线上生产告警，已有 SRE 事件和监控数据"))

    assert intake["intake_scenario"] == {
        "id": "offline_production",
        "environment_class": "production",
        "access_pattern": "platform_or_artifacts",
        "evidence_source": "existing_artifacts",
        "readiness": "blocked_until_artifacts_supplied",
    }
    assert intake["follow_up_questions"][0]["field"] == "incident_reference"
    assert "SRE 事件编号" in intake["follow_up_questions"][0]["question"]


def test_manual_offline_clue_is_classified_for_todesk_style_guidance():
    intake = build_start_intake(args(environment_mode="offline", customer_clue="ToDesk 环境，只能粘贴命令输出和截图"))

    assert intake["intake_scenario"]["id"] == "manual_guided_offline"
    assert intake["intake_scenario"]["access_pattern"] == "operator_paste"
    assert intake["follow_up_questions"][0]["field"] == "manual_input"


def test_manual_offline_pasted_evidence_is_captured_but_not_ready():
    intake = build_start_intake(
        args(
            environment_mode="offline",
            customer_clue="ToDesk 环境，只能粘贴命令输出",
            pasted_evidence="kubectl get pods output",
        )
    )

    assert intake["status"] == "blocked"
    assert intake["manual_evidence"] == {
        "status": "captured",
        "kind": "pasted_text",
    }
    assert intake["blocking_items"][0]["code"] == "offline_start_needs_artifacts"


def test_offline_intake_blocks_when_artifact_source_does_not_exist(tmp_path):
    missing = tmp_path / "missing-artifacts"
    intake = build_start_intake(args(environment_mode="offline", artifact_source=str(missing)))

    assert intake["status"] == "blocked"
    assert intake["offline_artifact"]["status"] == "not_found"
    assert intake["blocking_items"][0]["code"] == "offline_artifact_source_not_found"


def test_offline_intake_blocks_when_artifact_source_is_incomplete(tmp_path):
    artifact_dir = tmp_path / "incomplete-artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "input.yaml").write_text("middleware: mongodb\n", encoding="utf-8")

    intake = build_start_intake(args(environment_mode="offline", artifact_source=str(artifact_dir)))

    assert intake["status"] == "blocked"
    assert intake["offline_artifact"]["status"] == "incomplete"
    assert intake["offline_artifact"]["missing_files"] == [
        "structured_record.yaml",
        "signal_bundle.yaml",
        "collection_report.yaml",
    ]
    assert intake["blocking_items"][0]["code"] == "offline_artifacts_incomplete"


def test_offline_intake_ready_when_artifact_source_has_required_files(tmp_path):
    artifact_dir = tmp_path / "ready-artifacts"
    artifact_dir.mkdir()
    for filename in ("input.yaml", "structured_record.yaml", "signal_bundle.yaml", "collection_report.yaml"):
        (artifact_dir / filename).write_text("{}\n", encoding="utf-8")

    intake = build_start_intake(args(environment_mode="offline", artifact_source=str(artifact_dir)))

    assert intake["status"] == "ready_for_validation"
    assert intake["offline_artifact"] == {
        "status": "ready",
        "source": str(artifact_dir),
        "required_files": [
            "input.yaml",
            "structured_record.yaml",
            "signal_bundle.yaml",
            "collection_report.yaml",
        ],
        "missing_files": [],
    }
    assert intake["blocking_items"] == []

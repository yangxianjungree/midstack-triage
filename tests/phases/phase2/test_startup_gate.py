import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase2.startup_gate import evaluate_startup_readiness  # noqa: E402


def _intake(**overrides):
    data = {
        "status": "ready_for_validation",
        "environment_mode": "remote",
        "execution_mode": "remote",
        "blocking_items": [],
        "follow_up_questions": [],
    }
    data.update(overrides)
    return data


def _args(**overrides):
    class Args:
        middleware = "mongodb"
        environment_ip = ["192.0.2.10"]
        username = "root"
        password = "secret"
        port = 22
        namespace = ""

    args = Args()
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_remote_readiness_gate_adds_follow_up_for_remote_validation_failure():
    result = evaluate_startup_readiness(
        _args(),
        _intake(),
        validate_remote_environment=lambda access: {"status": "failed", "checks": []},
        discover_mongodb_inventory=lambda access, namespace: {"status": "skipped"},
        probe_local_context=lambda: {"status": "not_checked", "reason": "", "current_context": ""},
    )

    assert result["status"] == "blocked"
    assert result["remote_validation"]["status"] == "failed"
    assert result["blocking_items"][0]["code"] == "remote_environment_validation_failed"
    assert result["follow_up_questions"][0]["field"] == "remote_access"


def test_remote_readiness_gate_adds_namespace_follow_up_for_ambiguous_inventory():
    result = evaluate_startup_readiness(
        _args(),
        _intake(),
        validate_remote_environment=lambda access: {"status": "passed", "checks": []},
        discover_mongodb_inventory=lambda access, namespace: {
            "status": "ambiguous",
            "namespace_source": "ambiguous",
            "candidate_namespaces": ["mongo-a", "mongo-b"],
        },
        probe_local_context=lambda: {"status": "not_checked", "reason": "", "current_context": ""},
    )

    assert result["status"] == "blocked"
    assert result["object_inventory"]["status"] == "ambiguous"
    assert result["blocking_items"][0]["code"] == "multiple_mongodb_namespaces_detected"
    assert result["blocking_items"][0]["candidate_namespaces"] == ["mongo-a", "mongo-b"]
    assert result["follow_up_questions"][0]["field"] == "namespace"
    assert "mongo-a, mongo-b" in result["follow_up_questions"][0]["question"]


def test_remote_readiness_gate_updates_namespace_when_auto_discovered():
    args = _args()

    result = evaluate_startup_readiness(
        args,
        _intake(),
        validate_remote_environment=lambda access: {"status": "passed", "checks": []},
        discover_mongodb_inventory=lambda access, namespace: {
            "status": "passed",
            "namespace_source": "auto_discovered",
            "selected_namespace": "psmdb-test",
        },
        probe_local_context=lambda: {"status": "not_checked", "reason": "", "current_context": ""},
    )

    assert result["status"] == "ready"
    assert args.namespace == "psmdb-test"
    assert result["object_inventory"]["selected_namespace"] == "psmdb-test"


def test_local_readiness_gate_uses_local_context_and_inventory_without_remote_validation():
    calls = []

    def fail_remote_validation(access):
        raise AssertionError("local readiness must not call remote validation")

    def discover_inventory(access, namespace):
        calls.append((access, namespace))
        return {
            "status": "passed",
            "namespace_source": "auto_discovered",
            "selected_namespace": "psmdb-test",
        }

    args = _args(environment_ip=[], username="", password="")
    result = evaluate_startup_readiness(
        args,
        _intake(status="ready_for_validation", environment_mode="local", execution_mode="local"),
        validate_remote_environment=fail_remote_validation,
        discover_mongodb_inventory=discover_inventory,
        probe_local_context=lambda: {
            "status": "available",
            "reason": "",
            "current_context": "prod-cluster",
        },
    )

    assert result["status"] == "ready"
    assert result["remote_validation"]["status"] == "skipped"
    assert result["object_inventory"]["status"] == "passed"
    assert result["local_context"]["current_context"] == "prod-cluster"
    assert args.namespace == "psmdb-test"
    assert calls == [({"execution_mode": "local", "current_context": "prod-cluster"}, "")]


def test_local_readiness_gate_blocks_when_local_context_is_unavailable():
    result = evaluate_startup_readiness(
        _args(environment_ip=[], username="", password=""),
        _intake(status="ready_for_validation", environment_mode="local", execution_mode="local"),
        validate_remote_environment=lambda access: {"status": "should_not_run"},
        discover_mongodb_inventory=lambda access, namespace: {"status": "should_not_run"},
        probe_local_context=lambda: {
            "status": "unavailable",
            "reason": "kubectl_not_found",
            "current_context": "",
        },
    )

    assert result["status"] == "blocked"
    assert result["blocking_items"][0]["code"] == "local_context_unavailable"
    assert result["follow_up_questions"][0]["field"] == "execution_mode"

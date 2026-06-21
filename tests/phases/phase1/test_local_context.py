import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase1.local_context import probe_local_context  # noqa: E402


def test_probe_local_context_reports_missing_kubectl():
    result = probe_local_context(which_fn=lambda name: None)

    assert result == {
        "status": "unavailable",
        "reason": "kubectl_not_found",
        "current_context": "",
    }


def test_probe_local_context_reports_available_current_context():
    calls = []

    def fake_run(cmd, timeout, text, capture_output):
        calls.append(cmd)
        if cmd == ["kubectl", "config", "current-context"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="prod-cluster\n", stderr="")
        if cmd == ["kubectl", "cluster-info"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="Kubernetes control plane\n", stderr="")
        raise AssertionError("unexpected command: %r" % (cmd,))

    result = probe_local_context(which_fn=lambda name: "/usr/bin/kubectl", run_fn=fake_run)

    assert result == {
        "status": "available",
        "reason": "",
        "current_context": "prod-cluster",
    }
    assert calls == [["kubectl", "config", "current-context"], ["kubectl", "cluster-info"]]


def test_probe_local_context_reports_configured_but_unreachable_context():
    def fake_run(cmd, timeout, text, capture_output):
        if cmd == ["kubectl", "config", "current-context"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="prod-cluster\n", stderr="")
        if cmd == ["kubectl", "cluster-info"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="connection refused")
        raise AssertionError("unexpected command: %r" % (cmd,))

    result = probe_local_context(which_fn=lambda name: "/usr/bin/kubectl", run_fn=fake_run)

    assert result == {
        "status": "unreachable",
        "reason": "cluster_info_failed",
        "current_context": "prod-cluster",
    }


def test_probe_local_context_reports_current_context_timeout_as_unavailable():
    def fake_run(cmd, timeout, text, capture_output):
        raise subprocess.TimeoutExpired(cmd, timeout)

    result = probe_local_context(which_fn=lambda name: "/usr/bin/kubectl", run_fn=fake_run)

    assert result == {
        "status": "unavailable",
        "reason": "current_context_timeout",
        "current_context": "",
    }


def test_probe_local_context_reports_cluster_info_timeout_as_unreachable():
    def fake_run(cmd, timeout, text, capture_output):
        if cmd == ["kubectl", "config", "current-context"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="prod-cluster\n", stderr="")
        if cmd == ["kubectl", "cluster-info"]:
            raise subprocess.TimeoutExpired(cmd, timeout)
        raise AssertionError("unexpected command: %r" % (cmd,))

    result = probe_local_context(which_fn=lambda name: "/usr/bin/kubectl", run_fn=fake_run)

    assert result == {
        "status": "unreachable",
        "reason": "cluster_info_timeout",
        "current_context": "prod-cluster",
    }

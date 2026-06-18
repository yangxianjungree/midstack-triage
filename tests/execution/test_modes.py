import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution.modes import (
    execution_mode_names,
    mode_allows_existing_artifacts,
    mode_allows_remote_collection,
    resolve_execution_mode,
)


def test_remote_mode_is_current_default_live_transport_mode():
    mode = resolve_execution_mode(None)
    assert mode.name == "remote"
    assert mode.collects_live_evidence is True
    assert mode.requires_transport is True


def test_offline_mode_does_not_execute_collection_transport():
    mode = resolve_execution_mode("offline")
    assert mode.collects_live_evidence is False
    assert mode.requires_transport is False


def test_execution_modes_are_explicit():
    assert set(execution_mode_names()) == {"remote", "local", "offline"}


def test_execution_mode_capabilities_are_explicit():
    remote = resolve_execution_mode("remote")
    local = resolve_execution_mode("local")
    offline = resolve_execution_mode("offline")

    assert mode_allows_remote_collection(remote) is True
    assert mode_allows_existing_artifacts(remote) is True
    assert mode_allows_remote_collection(local) is False
    assert mode_allows_existing_artifacts(local) is False
    assert mode_allows_remote_collection(offline) is False
    assert mode_allows_existing_artifacts(offline) is True


def test_unknown_execution_mode_is_rejected():
    try:
        resolve_execution_mode("sshpass")
    except ValueError as exc:
        assert "unsupported execution mode" in str(exc)
    else:
        raise AssertionError("unknown execution mode should fail")

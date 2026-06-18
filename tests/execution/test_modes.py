import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution.modes import execution_mode_names, resolve_execution_mode


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


def test_unknown_execution_mode_is_rejected():
    try:
        resolve_execution_mode("sshpass")
    except ValueError as exc:
        assert "unsupported execution mode" in str(exc)
    else:
        raise AssertionError("unknown execution mode should fail")

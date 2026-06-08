#!/usr/bin/env python3

import importlib.util
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]


def load_remote_smoke_module() -> Any:
    path = ROOT / "tools" / "remote-smoke" / "mongodb-smoke.py"
    spec = importlib.util.spec_from_file_location("mongodb_smoke", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_multiline_ssh_quoting() -> None:
    module = load_remote_smoke_module()
    captured: Dict[str, Any] = {}

    def fake_ssh_base(access: Dict[str, Any]) -> Any:
        return ["ssh", "root@example"], {}

    def fake_run_process(command: List[str], env: Dict[str, str], timeout: int) -> CompletedProcess:
        captured["command"] = command
        captured["timeout"] = timeout
        return CompletedProcess(command, 0, "ok", "")

    module.ssh_base = fake_ssh_base
    module.run_process = fake_run_process
    script = "echo one\necho two"
    module.run_ssh({"username": "root", "primary_ip": "example", "password": "secret"}, script)
    remote_arg = captured["command"][-1]
    if "\\n" in remote_arg:
        raise AssertionError("run_ssh must not pass literal backslash-n to bash -lc: %r" % remote_arg)
    if "\n" not in remote_arg:
        raise AssertionError("run_ssh must preserve real newlines for multiline remote scripts: %r" % remote_arg)


def main() -> int:
    validate_multiline_ssh_quoting()
    print("Remote smoke validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

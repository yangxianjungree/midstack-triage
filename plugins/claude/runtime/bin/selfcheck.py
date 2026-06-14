#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PLUGIN_ROOT / "runtime"


def path_status(path: Path, label: str) -> dict[str, str]:
    return {
        "label": label,
        "path": str(path),
        "status": "present" if path.exists() else "missing",
    }


def command_status(name: str, required_for: str) -> dict[str, str]:
    return {
        "type": "command",
        "name": name,
        "required_for": required_for,
        "status": "present" if shutil.which(name) else "missing",
    }


def python_module_status(name: str, required_for: str, required: bool) -> dict[str, str]:
    try:
        __import__(name)
        status = "present"
    except ImportError:
        status = "missing"
    return {
        "type": "python_module",
        "name": name,
        "required_for": required_for,
        "required": "yes" if required else "no",
        "status": status,
    }


def env_var_status(name: str, required_for: str) -> dict[str, str]:
    return {
        "type": "env_var",
        "name": name,
        "required_for": required_for,
        "status": "present" if os.environ.get(name) else "missing",
    }


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    required_paths = [
        (RUNTIME_ROOT / "bin" / "midstack-local.py", "runtime wrapper"),
        (RUNTIME_ROOT / "tools" / "plugin" / "midstack-local.py", "plugin runtime"),
        (RUNTIME_ROOT / "tools" / "remote-executor" / "mongodb-executor.py", "remote executor"),
        (RUNTIME_ROOT / "tools" / "analyse" / "mongodb-analyse.py", "mongodb analyser"),
        (RUNTIME_ROOT / "src" / "commands" / "plugin_cli.py", "plugin CLI adapter"),
        (RUNTIME_ROOT / "src" / "phases" / "phase3" / "remote_executor.py", "phase3 remote executor"),
        (RUNTIME_ROOT / "src" / "phases" / "phase4" / "rule_drafts" / "__init__.py", "phase4 rule draft package"),
        (RUNTIME_ROOT / "src" / "phases" / "phase4" / "rule_drafts" / "mongodb.py", "mongodb rule draft analyser"),
        (RUNTIME_ROOT / "src" / "phases" / "phase4" / "rule_drafts" / "pulsar.py", "pulsar rule draft analyser"),
        (RUNTIME_ROOT / "src" / "shared" / "__init__.py", "shared runtime package"),
        (RUNTIME_ROOT / "src" / "shared" / "patch_merge.py", "patch merge library"),
        (RUNTIME_ROOT / "src" / "shared" / "scenario_router.py", "scenario routing library"),
        (RUNTIME_ROOT / "src" / "shared" / "skill_resolver.py", "skill resolver library"),
        (RUNTIME_ROOT / "src" / "shared" / "mongodb_collection_runtime.py", "mongo collection runtime"),
        (RUNTIME_ROOT / "src" / "phases" / "phase4" / "multitrack" / "__init__.py", "phase4 package"),
        (RUNTIME_ROOT / "domains" / "mongodb" / "scripts" / "manifest.yaml", "mongodb script manifest"),
        (RUNTIME_ROOT / "interfaces" / "plugin" / "script-runtime-map.example.yaml", "script runtime map"),
        (RUNTIME_ROOT / "core" / "routing" / "scenario-signal-map.yaml", "scenario routing map"),
    ]
    path_checks = [path_status(path, label) for path, label in required_paths]
    for item in path_checks:
        if item["status"] != "present":
            errors.append(f"missing {item['label']}: {item['path']}")

    required_local_dependencies = [
        command_status("python3", "all plugin commands"),
        command_status("bash", "Claude shell command execution"),
        command_status("ssh", "live remote collection"),
        command_status("sshpass", "live /midstack:start against password-auth jump hosts"),
        command_status("claude", "/midstack:validate and local plugin validation"),
        python_module_status("yaml", "all plugin commands", required=True),
    ]
    for item in required_local_dependencies:
        if item["status"] != "present":
            kind = item["type"].replace("_", " ")
            errors.append(f"missing required local {kind}: {item['name']}")

    optional_local_dependencies = [
        python_module_status("anthropic", "real Phase 4 Claude agent", required=False),
        env_var_status("ANTHROPIC_API_KEY", "real Phase 4 Claude agent"),
    ]
    if optional_local_dependencies[0]["status"] == "missing" or optional_local_dependencies[1]["status"] == "missing":
        warnings.append("real Phase 4 Claude agent is unavailable; bundled runtime will use the default mock agent")

    validate = subprocess.run(
        ["claude", "plugin", "validate", str(PLUGIN_ROOT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if validate.returncode != 0:
        errors.append("claude plugin validate failed")

    status = "passed" if not errors else "failed"
    payload = {
        "status": status,
        "plugin_root": str(PLUGIN_ROOT),
        "runtime_root": str(RUNTIME_ROOT),
        "dependency_boundary": {
            "source_repo_required": False,
            "bundled_runtime_mode": "plugin-local runtime payload",
            "phase4_default_agent": "mock",
        },
        "bundled_runtime_checks": path_checks,
        "required_local_dependencies": required_local_dependencies,
        "optional_local_dependencies": optional_local_dependencies,
        "remote_runtime_requirements": [
            "jump host reachable with the supplied SSH credentials",
            "kubectl available on the jump host with a working kube context",
            "permission to run kubectl get/describe/exec against the target cluster",
            "MongoDB shell available where the selected collection script requires it",
        ],
        "errors": errors,
        "warnings": warnings,
        "validate_stdout": validate.stdout.strip(),
        "validate_stderr": validate.stderr.strip(),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

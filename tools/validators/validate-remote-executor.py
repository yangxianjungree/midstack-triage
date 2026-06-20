#!/usr/bin/env python3

import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase2 import build_auth_hints, mongodb_auth_secret_refs  # noqa: E402
from phases.phase3.recollection import directed_recollection_script_ids  # noqa: E402


def load_remote_executor_module() -> Any:
    return importlib.reload(importlib.import_module("execution.remote.executor"))


def validate_multiline_ssh_quoting() -> None:
    module = importlib.reload(importlib.import_module("execution.remote.access"))
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


def validate_runtime_map_resolution() -> None:
    module = load_remote_executor_module()
    manifest_paths = [
        ROOT / "domains" / "mongodb" / "scripts" / "manifest.yaml",
        ROOT / "domains" / "kubernetes" / "scripts" / "manifest.yaml",
    ]
    entries = module.load_script_entries(
        manifest_paths,
        ROOT / "interfaces" / "plugin" / "script-runtime-map.example.yaml",
    )
    if len(entries) != 12:
        raise AssertionError("expected 12 runtime-map-backed script entries, got %d" % len(entries))
    entry_ids = [item["script_id"] for item in entries]
    for script_id in ("kubernetes.collect.logs.current", "kubernetes.collect.logs.previous"):
        if script_id not in entry_ids:
            raise AssertionError("default runtime-map-backed script entries must include %s: %r" % (script_id, entry_ids))
    for script_id in ("mongodb.collect.logs.current", "mongodb.collect.logs.previous"):
        if script_id in entry_ids:
            raise AssertionError("legacy MongoDB kubectl log alias must not be a default script entry: %r" % entry_ids)
    directed_entries = module.load_script_entries(
        manifest_paths,
        ROOT / "interfaces" / "plugin" / "script-runtime-map.example.yaml",
        [
            "mongodb.collect.logs.discover_sink",
            "mongodb.collect.logs.file_tail",
            "mongodb.collect.dns.coredns",
        ],
    )
    if [item["script_id"] for item in directed_entries] != [
        "mongodb.collect.logs.discover_sink",
        "mongodb.collect.logs.file_tail",
        "mongodb.collect.dns.coredns",
    ]:
        raise AssertionError("selected directed recollection script did not resolve correctly: %r" % directed_entries)
    first = entries[0]
    if not str(first.get("runtime_path") or "").startswith("assets/scripts/mongodb/"):
        raise AssertionError("runtime_path must be runtime-relative: %r" % first)
    if not Path(first["source_path"]).exists():
        raise AssertionError("source_path must resolve to an existing file: %r" % first)


def validate_directed_recollection_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="midstack-directed-gate-") as tmp:
        incident = Path(tmp)
        (incident / "structured_record.yaml").write_text(
            yaml.safe_dump(
                {
                    "details": {
                        "raw_logs": [
                            {
                                "pod_ref": "mongo-shard0-2",
                                "log_type": "current",
                                "line_count": 15,
                                "byte_size": 1800,
                            }
                        ]
                    }
                },
                sort_keys=False,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )
        (incident / "signal_bundle.yaml").write_text(
            yaml.safe_dump(
                {
                    "abnormal_signals": [
                        {
                            "signal_id": "pod-crashloop",
                            "object_ref": "pod/mongo-shard0-2",
                            "detail": "Pod container is restarting",
                        }
                    ],
                    "log_highlights": [
                        {
                            "pod_ref": "mongo-shard0-2",
                            "category": "timeout",
                            "message": "cannot resolve host mongo on 10.96.0.10:53: i/o timeout",
                        }
                    ],
                },
                sort_keys=False,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )
        (incident / "collection_report.yaml").write_text(
            yaml.safe_dump({"evidence_gaps": []}, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        selected = directed_recollection_script_ids(incident)
        expected = [
            "mongodb.collect.dns.coredns",
            "mongodb.collect.network.overlay",
            "mongodb.collect.logs.node_file_tail",
        ]
        if selected != expected:
            raise AssertionError("directed recollection gate selected %r, expected %r" % (selected, expected))


def validate_inventory_profile_and_executor_outputs() -> None:
    module = load_remote_executor_module()
    with tempfile.TemporaryDirectory(prefix="midstack-remote-executor-validate-") as tmp:
        tmp_path = Path(tmp)
        inventory_path = tmp_path / "object-inventory.yaml"
        inventory_path.write_text(
            yaml.safe_dump(
                {
                    "deployment_architecture_candidates": ["bitnami"],
                    "topology_hints": {"candidate_topology_type": "sharded_cluster"},
                    "auth_hints": {
                        "secret_ref_candidates": [
                            {
                                "namespace": "mongo",
                                "name": "mongo-root-secret",
                                "key": "mongodb-root-password",
                                "source_kind": "StatefulSet",
                                "source_name": "mongo-shard0",
                                "source_container": "mongodb",
                                "env_name": "MONGODB_ROOT_PASSWORD",
                                "score": 55,
                            }
                        ],
                        "selected_secret_ref": {
                            "namespace": "mongo",
                            "name": "mongo-root-secret",
                            "key": "mongodb-root-password",
                        },
                    },
                    "targets": {
                        "namespace": "mongo",
                        "statefulset_refs": ["mongo-shard0"],
                        "service_refs": ["mongo-mongos"],
                        "pod_refs": ["mongo-mongos-0"],
                        "node_refs": ["worker-01"],
                        "mongos_pod_ref": "mongo-mongos-0",
                    },
                },
                sort_keys=False,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )
        profile = module.context_profile_from_inventory(str(inventory_path), "mongo")
        if profile["deployment_architecture"] != "bitnami":
            raise AssertionError("inventory deployment architecture was not propagated")
        if profile["targets"]["mongos_pod_ref"] != "mongo-mongos-0":
            raise AssertionError("inventory targets were not propagated")

        captured: Dict[str, Any] = {"commands": []}

        def fake_run_ssh(access: Dict[str, Any], remote_script: str, timeout: int = 60) -> CompletedProcess:
            captured["commands"].append(remote_script)
            return CompletedProcess(["ssh"], 0, "ok", "")

        def fake_scp_to(access: Dict[str, Any], local_path: Path, remote_path: str) -> None:
            captured.setdefault("uploads", []).append((str(local_path), remote_path))

        def fake_scp_from(access: Dict[str, Any], remote_path: str, local_path: Path, recursive: bool = False) -> None:
            if recursive:
                local_path.mkdir(parents=True, exist_ok=True)
                (local_path / "artifact.txt").write_text("artifact\n", encoding="utf-8")
                return
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(
                yaml.safe_dump(
                    {
                        "script_id": "mongodb.collect.pods.state",
                        "status": "success",
                        "summary": "ok",
                        "started_at": "2026-06-10T00:00:00+08:00",
                        "finished_at": "2026-06-10T00:00:01+08:00",
                        "artifacts": [],
                        "structured_record_patch": {},
                        "signal_bundle_patch": {},
                        "collection_report_patch": {},
                        "warnings": [],
                        "evidence_gaps": [],
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )

        module.run_ssh = fake_run_ssh
        module.scp_to = fake_scp_to
        module.scp_from = fake_scp_from
        local_dir = tmp_path / "run"
        local_dir.mkdir(parents=True, exist_ok=True)
        module.run_script(
            {"primary_ip": "192.0.2.10", "username": "root", "password": "secret", "port": 22},
            "mongodb-remote-run-20260610-000000",
            {
                "script_id": "mongodb.collect.pods.state",
                "runtime_path": "assets/scripts/mongodb/collect-pods-state.sh",
                "runtime": "shell",
                "readonly": True,
            },
            "mongo",
            local_dir,
            "/tmp/midstack-triage",
            ["mongodb.collect.pods.state"],
            profile,
            "midstack-triage",
            [{"name": "ssh", "status": "success", "detail": "ssh ok"}],
        )
        script_dir = local_dir / "mongodb.collect.pods.state"
        request = yaml.safe_load((script_dir / "remote-executor-request.yaml").read_text(encoding="utf-8")) or {}
        result = yaml.safe_load((script_dir / "remote-executor-result.yaml").read_text(encoding="utf-8")) or {}
        context = yaml.safe_load((script_dir / "context.yaml").read_text(encoding="utf-8")) or {}
        if request.get("script", {}).get("runtime_path") != "assets/scripts/mongodb/collect-pods-state.sh":
            raise AssertionError("request did not record runtime-map runtime_path")
        if result.get("status") != "success":
            raise AssertionError("expected success executor result, got %r" % result.get("status"))
        if not result.get("capability_checks"):
            raise AssertionError("executor result must record capability checks")
        if context.get("targets", {}).get("mongos_pod_ref") != "mongo-mongos-0":
            raise AssertionError("context did not consume inventory targets")
        if context.get("mongos_query", {}).get("secret_ref", {}).get("name") != "mongo-root-secret":
            raise AssertionError("context did not consume inventory auth secret_ref")
        if context.get("replicaset_query", {}).get("secret_ref", {}).get("key") != "mongodb-root-password":
            raise AssertionError("replicaset query did not inherit inventory auth secret_ref")
        if not captured.get("uploads"):
            raise AssertionError("expected context upload via scp_to")


def validate_inventory_secret_ref_extraction() -> None:
    statefulset = {
        "metadata": {"namespace": "mongo", "name": "mongo-shard0"},
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "mongodb",
                            "env": [
                                {
                                    "name": "MONGODB_ROOT_PASSWORD",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "mongo-root-secret",
                                            "key": "mongodb-root-password",
                                        }
                                    },
                                }
                            ],
                        }
                    ]
                }
            }
        },
    }
    roles = ["shard", "replicaset"]
    candidates = mongodb_auth_secret_refs("StatefulSet", statefulset, roles)
    if len(candidates) != 1:
        raise AssertionError("expected one secret_ref candidate, got %r" % candidates)
    candidate = candidates[0]
    if candidate.get("name") != "mongo-root-secret" or candidate.get("key") != "mongodb-root-password":
        raise AssertionError("unexpected secret_ref candidate: %r" % candidate)
    hints = build_auth_hints("mongo", candidates)
    selected = hints.get("selected_secret_ref") or {}
    if selected.get("name") != "mongo-root-secret":
        raise AssertionError("expected selected secret_ref to be propagated, got %r" % selected)


def validate_mongos_script_capability_checks() -> None:
    module = load_remote_executor_module()
    with tempfile.TemporaryDirectory(prefix="midstack-remote-executor-mongos-") as tmp:
        tmp_path = Path(tmp)
        profile = module.default_context_profile("mongo")
        captured: Dict[str, Any] = {"commands": []}

        def fake_run_ssh(access: Dict[str, Any], remote_script: str, timeout: int = 60) -> CompletedProcess:
            captured["commands"].append(remote_script)
            if "kubectl get pods -n mongo -o json" in remote_script:
                return CompletedProcess(
                    ["ssh"],
                    0,
                    json.dumps(
                        {
                            "items": [
                                {
                                    "metadata": {"name": "mongo-mongos-0", "labels": {"app.kubernetes.io/component": "mongos"}},
                                    "spec": {"containers": [{"name": "mongos"}]},
                                    "status": {"phase": "Running"},
                                }
                            ]
                        }
                    ),
                    "",
                )
            if "kubectl exec -n mongo mongo-mongos-0 -c mongos -- bash -c" in remote_script:
                return CompletedProcess(["ssh"], 0, "mongosh\n", "")
            return CompletedProcess(["ssh"], 0, "ok", "")

        def fake_scp_to(access: Dict[str, Any], local_path: Path, remote_path: str) -> None:
            captured.setdefault("uploads", []).append((str(local_path), remote_path))

        def fake_scp_from(access: Dict[str, Any], remote_path: str, local_path: Path, recursive: bool = False) -> None:
            if recursive:
                local_path.mkdir(parents=True, exist_ok=True)
                (local_path / "artifact.txt").write_text("artifact\n", encoding="utf-8")
                return
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(
                yaml.safe_dump(
                    {
                        "script_id": "mongodb.collect.mongos.get_shard_map",
                        "status": "success",
                        "summary": "ok",
                        "started_at": "2026-06-10T00:00:00+08:00",
                        "finished_at": "2026-06-10T00:00:01+08:00",
                        "artifacts": [],
                        "structured_record_patch": {},
                        "signal_bundle_patch": {},
                        "collection_report_patch": {},
                        "warnings": [],
                        "evidence_gaps": [],
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )

        module.run_ssh = fake_run_ssh
        module.scp_to = fake_scp_to
        module.scp_from = fake_scp_from
        local_dir = tmp_path / "run"
        local_dir.mkdir(parents=True, exist_ok=True)
        module.run_script(
            {"primary_ip": "192.0.2.10", "username": "root", "password": "secret", "port": 22},
            "mongodb-remote-run-20260610-000000",
            {
                "script_id": "mongodb.collect.mongos.get_shard_map",
                "runtime_path": "assets/scripts/mongodb/collect-mongos-get-shard-map.sh",
                "runtime": "shell",
                "readonly": True,
            },
            "mongo",
            local_dir,
            "/tmp/midstack-triage",
            ["mongodb.collect.mongos.get_shard_map"],
            profile,
            "midstack-triage",
            [{"name": "ssh", "status": "success", "detail": "ssh ok"}],
        )
        script_dir = local_dir / "mongodb.collect.mongos.get_shard_map"
        request = yaml.safe_load((script_dir / "remote-executor-request.yaml").read_text(encoding="utf-8")) or {}
        result = yaml.safe_load((script_dir / "remote-executor-result.yaml").read_text(encoding="utf-8")) or {}
        context = yaml.safe_load((script_dir / "context.yaml").read_text(encoding="utf-8")) or {}
        required_pod_tools = request.get("required_capabilities", {}).get("pod_tools") or []
        if not required_pod_tools or required_pod_tools[0].get("required") is not True:
            raise AssertionError("mongos script must mark pod tool as required")
        if context.get("targets", {}).get("mongos_pod_ref") != "mongo-mongos-0":
            raise AssertionError("executor did not resolve mongos target pod into context")
        checks = result.get("capability_checks") or []
        check_names = {item.get("name"): item for item in checks if isinstance(item, dict)}
        if check_names.get("target_pod.mongos", {}).get("status") != "success":
            raise AssertionError("expected target_pod.mongos success capability check, got %r" % check_names.get("target_pod.mongos"))
        if check_names.get("pod_tool.mongosh", {}).get("status") != "success":
            raise AssertionError("expected pod_tool.mongosh success capability check, got %r" % check_names.get("pod_tool.mongosh"))
        mongo_exec = context.get("mongo_exec") or {}
        pod_targets = mongo_exec.get("pod_targets") or {}
        if pod_targets.get("mongo-mongos-0", {}).get("shell") != "mongosh":
            raise AssertionError("expected mongo_exec to record detected mongosh target, got %r" % pod_targets)
        if not captured.get("uploads"):
            raise AssertionError("expected mongos script context upload")


def validate_replicaset_target_filtering() -> None:
    module = load_remote_executor_module()
    with tempfile.TemporaryDirectory(prefix="midstack-remote-executor-replicaset-") as tmp:
        tmp_path = Path(tmp)
        profile = module.default_context_profile("mongo")
        profile["targets"]["pod_refs"] = ["mongo-mongos-0", "mongo-shard0-0", "mongo-configsvr-0"]
        captured: Dict[str, Any] = {"commands": []}

        def fake_run_ssh(access: Dict[str, Any], remote_script: str, timeout: int = 60) -> CompletedProcess:
            captured["commands"].append(remote_script)
            if "kubectl get pods -n mongo -o json" in remote_script:
                return CompletedProcess(
                    ["ssh"],
                    0,
                    json.dumps(
                        {
                            "items": [
                                {
                                    "metadata": {"name": "mongo-mongos-0", "labels": {"app.kubernetes.io/component": "mongos"}},
                                    "spec": {"containers": [{"name": "mongos"}]},
                                    "status": {"phase": "Running"},
                                },
                                {
                                    "metadata": {"name": "mongo-shard0-0", "labels": {"app.kubernetes.io/component": "shard"}},
                                    "spec": {"containers": [{"name": "mongod"}]},
                                    "status": {"phase": "Running"},
                                },
                                {
                                    "metadata": {"name": "mongo-configsvr-0", "labels": {"app.kubernetes.io/component": "configsvr"}},
                                    "spec": {"containers": [{"name": "mongod"}]},
                                    "status": {"phase": "Running"},
                                },
                            ]
                        }
                    ),
                    "",
                )
            if "kubectl exec -n mongo mongo-shard0-0 -c mongod -- bash -c" in remote_script:
                return CompletedProcess(["ssh"], 0, "mongosh\n", "")
            if "kubectl exec -n mongo mongo-configsvr-0 -c mongod -- bash -c" in remote_script:
                return CompletedProcess(["ssh"], 0, "mongosh\n", "")
            return CompletedProcess(["ssh"], 0, "ok", "")

        def fake_scp_to(access: Dict[str, Any], local_path: Path, remote_path: str) -> None:
            captured.setdefault("uploads", []).append((str(local_path), remote_path))

        def fake_scp_from(access: Dict[str, Any], remote_path: str, local_path: Path, recursive: bool = False) -> None:
            if recursive:
                local_path.mkdir(parents=True, exist_ok=True)
                (local_path / "artifact.txt").write_text("artifact\n", encoding="utf-8")
                return
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(
                yaml.safe_dump(
                    {
                        "script_id": "mongodb.collect.replicaset.rs_status",
                        "status": "partial",
                        "summary": "ok",
                        "started_at": "2026-06-10T00:00:00+08:00",
                        "finished_at": "2026-06-10T00:00:01+08:00",
                        "artifacts": [],
                        "structured_record_patch": {},
                        "signal_bundle_patch": {},
                        "collection_report_patch": {},
                        "warnings": [],
                        "evidence_gaps": [],
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )

        module.run_ssh = fake_run_ssh
        module.scp_to = fake_scp_to
        module.scp_from = fake_scp_from
        local_dir = tmp_path / "run"
        local_dir.mkdir(parents=True, exist_ok=True)
        module.run_script(
            {"primary_ip": "192.0.2.10", "username": "root", "password": "secret", "port": 22},
            "mongodb-remote-run-20260610-000000",
            {
                "script_id": "mongodb.collect.replicaset.rs_status",
                "runtime_path": "assets/scripts/mongodb/collect-replicaset-rs-status.sh",
                "runtime": "shell",
                "readonly": True,
            },
            "mongo",
            local_dir,
            "/tmp/midstack-triage",
            ["mongodb.collect.replicaset.rs_status"],
            profile,
            "midstack-triage",
            [{"name": "ssh", "status": "success", "detail": "ssh ok"}],
        )
        script_dir = local_dir / "mongodb.collect.replicaset.rs_status"
        context = yaml.safe_load((script_dir / "context.yaml").read_text(encoding="utf-8")) or {}
        pod_refs = context.get("targets", {}).get("pod_refs") or []
        if "mongo-mongos-0" in pod_refs:
            raise AssertionError("replicaset target filtering must exclude mongos pod refs")
        if sorted(pod_refs) != ["mongo-configsvr-0", "mongo-shard0-0"]:
            raise AssertionError("unexpected filtered replicaset pod refs: %r" % pod_refs)
        result = yaml.safe_load((script_dir / "remote-executor-result.yaml").read_text(encoding="utf-8")) or {}
        checks = result.get("capability_checks") or []
        check_names = {item.get("name"): item for item in checks if isinstance(item, dict)}
        if check_names.get("target_pod.replicaset", {}).get("status") != "success":
            raise AssertionError("expected target_pod.replicaset success capability check, got %r" % check_names.get("target_pod.replicaset"))
        if check_names.get("pod_tool.mongosh", {}).get("status") != "success":
            raise AssertionError("expected replicaset pod_tool.mongosh success capability check, got %r" % check_names.get("pod_tool.mongosh"))
        mongo_exec = context.get("mongo_exec") or {}
        pod_targets = mongo_exec.get("pod_targets") or {}
        if sorted(pod_targets) != ["mongo-configsvr-0", "mongo-shard0-0"]:
            raise AssertionError("expected mongo_exec pod targets for filtered mongod pods, got %r" % pod_targets)


def validate_script_output_contract_checks() -> None:
    module = load_remote_executor_module()
    with tempfile.TemporaryDirectory(prefix="midstack-remote-executor-contract-") as tmp:
        tmp_path = Path(tmp)
        good_path = tmp_path / "good-output.yaml"
        good_path.write_text(
            yaml.safe_dump(
                {
                    "script_id": "mongodb.collect.pods.state",
                    "status": "blocked",
                    "summary": "target pod is missing",
                    "started_at": "2026-06-10T00:00:00+08:00",
                    "finished_at": "2026-06-10T00:00:01+08:00",
                    "artifacts": [{"path": "stderr.txt", "kind": "debug", "description": "stderr"}],
                    "structured_record_patch": {},
                    "signal_bundle_patch": {},
                    "collection_report_patch": {},
                    "warnings": ["target pod was not found"],
                    "evidence_gaps": [{"gap": "pod missing", "related_stage": "signal_collection", "why_important": "no evidence"}],
                },
                sort_keys=False,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )
        ok, _, message = module.validate_script_output_contract(good_path, "mongodb.collect.pods.state")
        if not ok:
            raise AssertionError("expected valid output-file contract, got %s" % message)

        bad_path = tmp_path / "bad-output.yaml"
        bad_path.write_text(
            yaml.safe_dump(
                {
                    "script_id": "mongodb.collect.pods.state",
                    "status": "success",
                    "started_at": "2026-06-10T00:00:00+08:00",
                    "finished_at": "2026-06-10T00:00:01+08:00",
                    "artifacts": [{"path": "/tmp/absolute.txt", "kind": "debug", "description": "bad path"}],
                    "structured_record_patch": {},
                    "signal_bundle_patch": {},
                    "collection_report_patch": {},
                    "warnings": [],
                    "evidence_gaps": [],
                },
                sort_keys=False,
                allow_unicode=False,
            ),
            encoding="utf-8",
        )
        ok, _, message = module.validate_script_output_contract(bad_path, "mongodb.collect.pods.state")
        if ok:
            raise AssertionError("expected invalid output-file contract to fail")
        if "missing required fields" not in message:
            raise AssertionError("expected missing field message, got %s" % message)


def validate_blocked_remote_run_import() -> None:
    with tempfile.TemporaryDirectory(prefix="midstack-remote-executor-import-") as tmp:
        tmp_path = Path(tmp)
        remote_run_dir = tmp_path / "remote-run"
        remote_run_dir.mkdir(parents=True, exist_ok=True)
        run_result = {
            "incident_id": "mongodb-remote-run-20260610-000000",
            "plugin_name": "midstack-triage",
            "status": "blocked",
            "selected_ip": "192.0.2.10",
            "namespace": "mongo",
            "started_at": "2026-06-10T00:00:00+08:00",
            "finished_at": "2026-06-10T00:00:01+08:00",
            "capability_checks": [
                {"name": "ssh", "status": "success", "detail": "ssh ok"},
                {"name": "kubectl", "status": "blocked", "detail": "kubectl is missing", "error_code": "kubectl_missing"},
            ],
            "script_results": [],
            "error": {"code": "kubectl_missing", "message": "kubectl is not installed on the jump host"},
            "warnings": [],
        }
        (remote_run_dir / "remote-executor-run.yaml").write_text(
            yaml.safe_dump(run_result, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        (remote_run_dir / "capability-checks.yaml").write_text(
            yaml.safe_dump({"checks": run_result["capability_checks"], "error": run_result["error"]}, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        output_dir = tmp_path / "incident"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "plugin" / "midstack-local.py"),
                "analyse",
                "--remote-run-dir",
                str(remote_run_dir),
                "--output-dir",
                str(output_dir),
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if proc.returncode != 0:
            raise AssertionError("expected blocked analyse import to exit 0, got %s stderr=%s" % (proc.returncode, proc.stderr.strip()))
        adapter = yaml.safe_load((output_dir / "adapter-output.yaml").read_text(encoding="utf-8")) or {}
        if adapter.get("status") != "blocked":
            raise AssertionError("expected adapter output status blocked, got %r" % adapter.get("status"))
        input_data = yaml.safe_load((output_dir / "input.yaml").read_text(encoding="utf-8")) or {}
        if input_data.get("incident_id") != "mongodb-remote-run-20260610-000000":
            raise AssertionError("expected blocked remote run import to preserve run-level incident_id, got %r" % input_data.get("incident_id"))
        collection_report = yaml.safe_load((output_dir / "collection_report.yaml").read_text(encoding="utf-8")) or {}
        if not (collection_report.get("failed_items") or []):
            raise AssertionError("expected collection_report to preserve remote executor batch failure")
        if not (output_dir / "remote-executor-run.yaml").exists():
            raise AssertionError("expected incident import to preserve remote-executor-run.yaml")


def main() -> int:
    validate_multiline_ssh_quoting()
    validate_runtime_map_resolution()
    validate_directed_recollection_gate()
    validate_inventory_profile_and_executor_outputs()
    validate_inventory_secret_ref_extraction()
    validate_mongos_script_capability_checks()
    validate_replicaset_target_filtering()
    validate_script_output_contract_checks()
    validate_blocked_remote_run_import()
    print("Remote execution contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

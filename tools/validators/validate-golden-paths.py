#!/usr/bin/env python3

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from support.common import ROOT, load_yaml, run_command  # noqa: E402

SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.patch_merge import apply_script_output  # noqa: E402

GOLDEN_ROOT = ROOT / "tests" / "golden-paths"
REQUIRED_OUTPUT_FIELDS = {
    "script_id",
    "status",
    "summary",
    "started_at",
    "finished_at",
    "artifacts",
    "structured_record_patch",
    "signal_bundle_patch",
    "collection_report_patch",
    "warnings",
    "evidence_gaps",
}


def fail(errors: List[str], message: str) -> None:
    errors.append(message)


def load_manifest(middleware: str = "mongodb") -> Dict[str, Dict[str, Any]]:
    manifest_path = ROOT / "domains" / middleware / "scripts" / "manifest.yaml"
    data = load_yaml(manifest_path)
    by_id: Dict[str, Dict[str, Any]] = {}
    for item in data.get("scripts") or []:
        if isinstance(item, dict) and item.get("script_id"):
            by_id[str(item["script_id"])] = item
    return by_id


def load_asset_ref_manifest(middleware: str = "mongodb") -> Dict[str, Dict[str, Any]]:
    by_id = load_manifest(middleware)
    kubernetes_manifest = ROOT / "domains" / "kubernetes" / "scripts" / "manifest.yaml"
    if kubernetes_manifest.exists():
        data = load_yaml(kubernetes_manifest)
        for item in data.get("scripts") or []:
            if isinstance(item, dict) and str(item.get("script_id") or "").startswith("kubernetes."):
                by_id[str(item["script_id"])] = item
    return by_id


def load_metadata_index(domain: str, asset_kind: str) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    root = ROOT / "domains" / domain / asset_kind
    if not root.exists():
        return index
    for path in sorted(root.glob("**/metadata.yaml")):
        data = load_yaml(path)
        asset_id = data.get("id")
        if isinstance(asset_id, str) and asset_id:
            index[asset_id] = path
    return index


def validate_structured_ref(
    ref: Dict[str, Any],
    context: str,
    manifest_by_id: Dict[str, Dict[str, Any]],
    runbooks: Dict[str, Path],
    commands: Dict[str, Path],
    skills: Dict[str, Path],
    scenarios: Set[str],
    errors: List[str],
) -> None:
    ref_type = ref.get("type")
    ref_id = ref.get("id")
    if not isinstance(ref_type, str) or not isinstance(ref_id, str) or not ref_id:
        fail(errors, "%s structured ref must include type and id" % context)
        return

    if ref_type == "scenario":
        if ref_id not in scenarios:
            fail(errors, "%s scenario id does not exist: %s" % (context, ref_id))
    elif ref_type == "runbook":
        if ref_id not in runbooks:
            fail(errors, "%s runbook id does not exist: %s" % (context, ref_id))
    elif ref_type == "command":
        if ref_id not in commands:
            fail(errors, "%s command id does not exist: %s" % (context, ref_id))
    elif ref_type == "skill":
        if ref_id not in skills:
            fail(errors, "%s skill id does not exist: %s" % (context, ref_id))
    elif ref_type == "script":
        if ref_id not in manifest_by_id:
            fail(errors, "%s script_id does not exist in manifest: %s" % (context, ref_id))
    else:
        fail(errors, "%s unsupported asset ref type: %s" % (context, ref_type))


def validate_asset_file_ref(asset: Dict[str, Any], errors: List[str]) -> None:
    rel_path = asset.get("path")
    asset_id = asset.get("id")
    asset_type = asset.get("type")
    if not isinstance(rel_path, str):
        fail(errors, "asset_refs entry missing path: %s" % asset)
        return
    path = ROOT / rel_path
    if not path.exists():
        fail(errors, "asset_refs path does not exist: %s" % rel_path)
        return
    data = load_yaml(path)
    if data.get("id") != asset_id:
        fail(errors, "%s id mismatch: expected %s got %s" % (rel_path, asset_id, data.get("id")))
    if asset_type == "scenario" and data.get("id") != path.parent.name:
        fail(errors, "%s scenario id must match directory name" % rel_path)


def validate_patch_merge_fixture(path_id: str, fixture_dir: Path, errors: List[str]) -> None:
    if not fixture_dir.exists():
        fail(errors, "%s patch_merge_fixture does not exist: %s" % (path_id, fixture_dir))
        return

    required = [
        "pods-script-output.yaml",
        "rs-status-script-output.yaml",
        "expected-structured_record.yaml",
    ]
    for name in required:
        if not (fixture_dir / name).exists():
            fail(errors, "%s patch_merge_fixture missing %s" % (path_id, name))
            return

    structured_record: Dict[str, Any] = {"summary": {}, "details": {}}
    signal_bundle: Dict[str, Any] = {}
    collection_report: Dict[str, Any] = {"collection_actions": []}
    for name in ("pods-script-output.yaml", "rs-status-script-output.yaml"):
        apply_script_output(
            structured_record,
            signal_bundle,
            collection_report,
            load_yaml(fixture_dir / name),
        )

    expected = load_yaml(fixture_dir / "expected-structured_record.yaml")
    if (structured_record.get("summary") or {}) != (expected.get("summary") or {}):
        fail(errors, "%s patch merge summary mismatch" % path_id)
    if (structured_record.get("details") or {}) != (expected.get("details") or {}):
        fail(errors, "%s patch merge details mismatch" % path_id)
    if len(collection_report.get("collection_actions") or []) != 2:
        fail(errors, "%s patch merge should append two collection_actions" % path_id)


def run_contract_step(step: Dict[str, Any], errors: List[str]) -> None:
    step_id = step.get("step_id", "unknown-step")
    script_source = step.get("script_source")
    context_fixture = step.get("context_fixture")
    expect = step.get("expect") or {}

    if not isinstance(script_source, str) or not isinstance(context_fixture, str):
        fail(errors, "%s missing script_source or context_fixture" % step_id)
        return

    script_path = ROOT / script_source
    context_path = ROOT / context_fixture
    if not script_path.exists():
        fail(errors, "%s script does not exist: %s" % (step_id, script_source))
        return
    if not context_path.exists():
        fail(errors, "%s context fixture does not exist: %s" % (step_id, context_fixture))
        return

    with tempfile.TemporaryDirectory(prefix="midstack-golden-") as tmp:
        tmp_path = Path(tmp)
        output_file = tmp_path / "output.yaml"
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if script_path.suffix == ".py":
            command = [sys.executable, str(script_path)]
        else:
            command = ["bash", str(script_path)]
        proc = run_command(
            command
            + [
                "--context-file",
                str(context_path),
                "--output-file",
                str(output_file),
                "--artifact-dir",
                str(artifact_dir),
            ]
        )
        expected_exit = int(expect.get("exit_code", 0))
        if proc.returncode != expected_exit:
            fail(
                errors,
                "%s exit code expected %d got %d stderr=%s"
                % (step_id, expected_exit, proc.returncode, proc.stderr.strip()),
            )
            return
        if not output_file.exists():
            fail(errors, "%s did not write output-file" % step_id)
            return

        output = load_yaml(output_file)
        expected_output = expect.get("output") or {}
        for key, value in expected_output.items():
            if key == "required_fields":
                for field in value or []:
                    if field not in output:
                        fail(errors, "%s output missing field: %s" % (step_id, field))
                continue
            if output.get(key) != value:
                fail(errors, "%s output.%s expected %r got %r" % (step_id, key, value, output.get(key)))

        for field in REQUIRED_OUTPUT_FIELDS:
            if field not in output:
                fail(errors, "%s output missing contract field: %s" % (step_id, field))


def validate_golden_path(path: Path, errors: List[str], live: bool) -> None:
    data = load_yaml(path)
    path_id = data.get("id")
    if not isinstance(path_id, str) or not path_id:
        fail(errors, "%s missing id" % path)
        return

    scenario_id = data.get("scenario")
    middleware = str(data.get("middleware") or "mongodb")
    if middleware not in ("mongodb", "pulsar"):
        fail(errors, "%s unsupported middleware: %s" % (path, middleware))

    runbooks = load_metadata_index(middleware, "runbooks")
    commands = load_metadata_index(middleware, "commands")
    skills = load_metadata_index(middleware, "skills")
    manifest_by_id = load_manifest(middleware)
    asset_ref_manifest_by_id = load_asset_ref_manifest(middleware)
    scenarios = {p.parent.name for p in (ROOT / "scenarios").glob("*/scenario.yaml")}

    routing = data.get("routing") or {}
    expected = routing.get("expected") or {}
    if expected.get("scenario_id") != scenario_id:
        fail(errors, "%s routing.expected.scenario_id must match scenario" % path)
    if scenario_id not in scenarios:
        fail(errors, "%s scenario does not exist: %s" % (path, scenario_id))

    for key in ("skill_id", "runbook_id", "command_id"):
        asset_id = expected.get(key)
        if not isinstance(asset_id, str):
            fail(errors, "%s routing.expected missing %s" % (path, key))
            continue
        if key == "skill_id" and asset_id not in skills:
            fail(errors, "%s skill id does not exist: %s" % (path, asset_id))
        if key == "runbook_id" and asset_id not in runbooks:
            fail(errors, "%s runbook id does not exist: %s" % (path, asset_id))
        if key == "command_id" and asset_id not in commands:
            fail(errors, "%s command id does not exist: %s" % (path, asset_id))

    skill_meta = load_yaml(skills[expected["skill_id"]])
    for ref in skill_meta.get("required_assets") or []:
        if isinstance(ref, dict):
            validate_structured_ref(
                ref,
                "%s skill required_assets" % path,
                asset_ref_manifest_by_id,
                runbooks,
                commands,
                skills,
                scenarios,
                errors,
            )
        elif isinstance(ref, str):
            ref_path = ROOT / ref
            if not ref_path.exists():
                fail(errors, "%s legacy skill asset path missing: %s" % (path, ref))

    for _, asset in (data.get("asset_refs") or {}).items():
        if isinstance(asset, dict):
            validate_asset_file_ref(asset, errors)
            validate_structured_ref(
                asset,
                "%s asset_refs" % path,
                asset_ref_manifest_by_id,
                runbooks,
                commands,
                skills,
                scenarios,
                errors,
            )

    for script_id in data.get("analyse_mvp_scripts") or []:
        if script_id not in manifest_by_id:
            fail(errors, "%s analyse_mvp_scripts missing manifest entry: %s" % (path, script_id))

    for step in data.get("contract_steps") or []:
        if isinstance(step, dict):
            run_contract_step(step, errors)

    patch_merge_fixture = data.get("patch_merge_fixture")
    if isinstance(patch_merge_fixture, str):
        validate_patch_merge_fixture(path_id, ROOT / patch_merge_fixture, errors)

    if live:
        fail(errors, "%s live mode is not implemented yet; use contract_steps for CI" % path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate golden path definitions and script contracts.")
    parser.add_argument("--path", help="Validate a single golden path file.")
    parser.add_argument("--all", action="store_true", help="Validate all golden path YAML files.")
    parser.add_argument("--live", action="store_true", help="Reserved for future kubectl-backed checks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: List[str] = []
    if args.all:
        targets = sorted(GOLDEN_ROOT.glob("*.yaml"))
    else:
        target = Path(args.path or str(GOLDEN_ROOT / "mongodb-analyse-minimal.yaml"))
        targets = [target]
    if not targets:
        fail(errors, "no golden path files found")
    for target in targets:
        if not target.exists():
            fail(errors, "golden path does not exist: %s" % target)
            continue
        validate_golden_path(target, errors, args.live)

    if errors:
        print("Golden path validation failed:", file=sys.stderr)
        for item in errors:
            print("- %s" % item, file=sys.stderr)
        return 1

    for target in targets:
        print("Golden path validation passed: %s" % target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

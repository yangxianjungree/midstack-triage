#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
from typing import Sequence


TOOLS_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from support.common import ROOT, load_yaml  # noqa: E402

from .contracts import (  # noqa: E402
    load_scenarios,
    load_taxonomies,
    validate_adapter_output,
    validate_context_example,
    validate_manifest,
    validate_output_example,
    validate_remote_request,
    validate_remote_result,
    validate_runtime_map,
)
from .domain_assets import validate_domain_assets, validate_fixtures  # noqa: E402


def shared_kubernetes_manifest_by_id() -> dict:
    manifest = ROOT / "domains" / "kubernetes" / "scripts" / "manifest.yaml"
    if not manifest.exists():
        return {}
    data = load_yaml(manifest)
    return {
        str(item.get("script_id")): item
        for item in data.get("scripts") or []
        if isinstance(item, dict) and str(item.get("script_id") or "").startswith("kubernetes.")
    }


def validate_default_collection_set(manifest_by_id: dict, shared_by_id: dict, errors: list[str]) -> None:
    combined = dict(manifest_by_id)
    combined.update(shared_by_id)
    default_ids = {
        str(script_id)
        for script_id, item in combined.items()
        if isinstance(item, dict) and item.get("mvp") is True
    }
    expected_log_ids = {"kubernetes.collect.logs.current", "kubernetes.collect.logs.previous"}
    legacy_log_ids = {"mongodb.collect.logs.current", "mongodb.collect.logs.previous"}
    if len(default_ids) != 12:
        errors.append(
            "default MongoDB collection set must contain 12 MVP scripts across MongoDB and shared Kubernetes manifests, got %d"
            % len(default_ids)
        )
    if not expected_log_ids <= default_ids:
        errors.append("default MongoDB collection set must use shared Kubernetes log scripts: missing=%s" % sorted(expected_log_ids - default_ids))
    legacy_defaults = legacy_log_ids & default_ids
    if legacy_defaults:
        errors.append("legacy MongoDB kubectl log aliases must not be default MVP scripts: %s" % sorted(legacy_defaults))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MongoDB script manifest and plugin runtime map.")
    parser.add_argument("--manifest", default="domains/mongodb/scripts/manifest.yaml")
    parser.add_argument("--runtime-map", default="interfaces/plugin/script-runtime-map.example.yaml")
    parser.add_argument("--context-example", default="domains/mongodb/scripts/context.example.yaml")
    parser.add_argument("--output-example", default="domains/mongodb/scripts/output.example.yaml")
    parser.add_argument("--remote-request", default="interfaces/plugin/remote-executor-request.example.yaml")
    parser.add_argument("--remote-result", default="interfaces/plugin/remote-executor-result.example.yaml")
    parser.add_argument("--adapter-output", default="interfaces/plugin/adapter-output.example.yaml")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    errors: list[str] = []
    taxonomies = load_taxonomies(ROOT / "core/taxonomies", errors)
    scenarios = load_scenarios(ROOT / "scenarios", "mongodb", errors)
    manifest_by_id = validate_manifest(ROOT / args.manifest, errors)
    shared_by_id = shared_kubernetes_manifest_by_id()
    asset_ref_manifest_by_id = dict(manifest_by_id)
    asset_ref_manifest_by_id.update(shared_by_id)
    validate_default_collection_set(manifest_by_id, shared_by_id, errors)
    runtime_by_id = validate_runtime_map(ROOT / args.runtime_map, manifest_by_id, errors)
    validate_context_example(ROOT / args.context_example, manifest_by_id, errors)
    validate_output_example(ROOT / args.output_example, manifest_by_id, taxonomies, errors)
    validate_remote_request(ROOT / args.remote_request, manifest_by_id, runtime_by_id, errors)
    validate_remote_result(ROOT / args.remote_result, manifest_by_id, taxonomies, errors)
    validate_domain_assets(taxonomies, scenarios, asset_ref_manifest_by_id, errors)
    validate_fixtures(errors)
    validate_adapter_output(ROOT / args.adapter_output, taxonomies, errors)
    if errors:
        for error in errors:
            print("ERROR: %s" % error, file=sys.stderr)
        return 1
    print("ok: validated %d MongoDB script(s)" % len(manifest_by_id))
    return 0

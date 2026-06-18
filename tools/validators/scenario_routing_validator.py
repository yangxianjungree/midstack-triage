#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from support.common import ROOT, load_yaml


AssetPairs = Set[Tuple[str, str]]


def load_scenario_pairs(root: Path = ROOT) -> Dict[Tuple[str, str], Path]:
    pairs: Dict[Tuple[str, str], Path] = {}
    for scenario_file in sorted((root / "scenarios").glob("*/scenario.yaml")):
        data = load_yaml(scenario_file)
        scenario_id = str(data.get("id") or scenario_file.parent.name)
        for middleware in data.get("applicable_middleware") or []:
            pairs[(scenario_id, str(middleware))] = scenario_file
    return pairs


def load_routing_pairs(root: Path = ROOT) -> Dict[Tuple[str, str], Path]:
    routing_map = root / "core" / "routing" / "scenario-signal-map.yaml"
    data = load_yaml(routing_map)
    pairs: Dict[Tuple[str, str], Path] = {}
    for route in data.get("routes") or []:
        if not isinstance(route, dict):
            continue
        scenario = str(route.get("scenario") or "")
        if not scenario:
            continue
        for middleware in route.get("middleware") or []:
            pairs[(scenario, str(middleware))] = routing_map
    return pairs


def metadata_scenario(data: Dict[str, Any]) -> str:
    return str(data.get("scenario") or data.get("primary_scenario") or "")


def load_domain_asset_pairs(root: Path = ROOT) -> Dict[Tuple[str, str], List[Path]]:
    pairs: Dict[Tuple[str, str], List[Path]] = {}
    domains_root = root / "domains"
    for domain_dir in sorted(path for path in domains_root.iterdir() if path.is_dir()):
        middleware = domain_dir.name
        for asset_kind in ("runbooks", "skills", "commands"):
            asset_root = domain_dir / asset_kind
            if not asset_root.exists():
                continue
            for metadata_file in sorted(asset_root.glob("**/metadata.yaml")):
                data = load_yaml(metadata_file)
                if str(data.get("middleware") or middleware) != middleware:
                    continue
                scenario = metadata_scenario(data)
                if not scenario:
                    continue
                pairs.setdefault((scenario, middleware), []).append(metadata_file)
    return pairs


def validate_contract(root: Path = ROOT, explicit_unrouted_pairs: AssetPairs | None = None) -> List[str]:
    explicit_unrouted_pairs = explicit_unrouted_pairs or set()
    scenario_pairs = load_scenario_pairs(root)
    routing_pairs = load_routing_pairs(root)
    domain_asset_pairs = load_domain_asset_pairs(root)
    errors: List[str] = []

    for pair, scenario_file in sorted(scenario_pairs.items()):
        if pair in explicit_unrouted_pairs:
            continue
        scenario, middleware = pair
        if pair not in routing_pairs:
            errors.append(
                "%s declares middleware %s for scenario %s but routing map has no matching route"
                % (scenario_file, middleware, scenario)
            )
        if pair not in domain_asset_pairs:
            errors.append(
                "%s declares middleware %s for scenario %s but domains/%s has no matching runbook, skill, or command metadata"
                % (scenario_file, middleware, scenario, middleware)
            )

    for pair, routing_file in sorted(routing_pairs.items()):
        if pair in explicit_unrouted_pairs:
            continue
        scenario, middleware = pair
        if pair not in scenario_pairs:
            errors.append(
                "%s routes scenario %s for middleware %s but scenarios/%s/scenario.yaml does not declare that middleware"
                % (routing_file, scenario, middleware, scenario)
            )
        if pair not in domain_asset_pairs:
            errors.append(
                "%s routes scenario %s for middleware %s but domains/%s has no matching runbook, skill, or command metadata"
                % (routing_file, scenario, middleware, middleware)
            )

    return errors

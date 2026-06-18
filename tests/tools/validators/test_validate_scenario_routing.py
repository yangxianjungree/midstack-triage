import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = ROOT / "tools"
VALIDATORS_DIR = TOOLS_DIR / "validators"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))

from scenario_routing_validator import validate_contract  # noqa: E402


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def add_scenario(root: Path, scenario: str, middleware: list[str]) -> None:
    write_yaml(
        root / "scenarios" / scenario / "scenario.yaml",
        {
            "id": scenario,
            "title": scenario,
            "summary": scenario,
            "applicable_middleware": middleware,
        },
    )


def add_route(root: Path, scenario: str, middleware: list[str]) -> None:
    routing_map = root / "core" / "routing" / "scenario-signal-map.yaml"
    data = yaml.safe_load(routing_map.read_text(encoding="utf-8")) if routing_map.exists() else {"routes": []}
    data.setdefault("routes", []).append({"scenario": scenario, "middleware": middleware, "when_any_signal": ["demo"]})
    write_yaml(routing_map, data)


def add_domain_asset(root: Path, middleware: str, scenario: str, kind: str = "runbooks") -> None:
    field = "primary_scenario" if kind == "skills" else "scenario"
    write_yaml(
        root / "domains" / middleware / kind / scenario / "metadata.yaml",
        {
            "id": "%s.%s.%s" % (middleware, kind, scenario),
            "title": scenario,
            "middleware": middleware,
            field: scenario,
        },
    )


def test_validator_accepts_matching_scenario_route_and_domain_asset(tmp_path):
    add_scenario(tmp_path, "queue-backlog", ["pulsar"])
    add_route(tmp_path, "queue-backlog", ["pulsar"])
    add_domain_asset(tmp_path, "pulsar", "queue-backlog")

    assert validate_contract(tmp_path) == []


def test_validator_reports_scenario_declared_middleware_without_route_or_assets(tmp_path):
    add_scenario(tmp_path, "queue-backlog", ["pulsar", "mongodb"])
    add_route(tmp_path, "queue-backlog", ["pulsar"])
    add_domain_asset(tmp_path, "pulsar", "queue-backlog")

    errors = validate_contract(tmp_path)

    assert any("middleware mongodb" in item and "no matching route" in item for item in errors)
    assert any("domains/mongodb" in item and "no matching runbook" in item for item in errors)


def test_validator_reports_route_without_scenario_declaration(tmp_path):
    add_scenario(tmp_path, "queue-backlog", ["pulsar"])
    add_route(tmp_path, "queue-backlog", ["mongodb"])
    add_domain_asset(tmp_path, "mongodb", "queue-backlog")

    errors = validate_contract(tmp_path)

    assert any("routes scenario queue-backlog for middleware mongodb" in item for item in errors)

#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_FILES = [
    "input.yaml",
    "structured_record.yaml",
    "signal_bundle.yaml",
    "collection_report.yaml",
    "expected_analysis.yaml",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze a MongoDB incident or remote run into a replay fixture.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--incident-dir")
    source.add_argument("--remote-run-dir")
    parser.add_argument("--fixture-dir", required=True)
    parser.add_argument("--case-id", help="Fixture case id. Defaults to fixture directory name.")
    parser.add_argument("--scenario", default="baseline")
    parser.add_argument("--customer-clue", default="")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def build_incident_from_remote_run(remote_run_dir: Path, case_id: str, scenario: str, customer_clue: str) -> Path:
    incident_dir = ROOT / ".local" / "incidents" / ("%s-freeze-source" % case_id)
    command = [
        sys.executable,
        str(ROOT / "tools" / "plugin" / "midstack-local.py"),
        "analyse",
        "--remote-run-dir",
        str(remote_run_dir),
        "--output-dir",
        str(incident_dir),
        "--scenario",
        scenario,
    ]
    if customer_clue:
        command.extend(["--customer-clue", customer_clue])
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("failed to build incident from remote run: %s" % proc.stderr.strip())
    return incident_dir


def ensure_analysis(incident_dir: Path) -> None:
    if (incident_dir / "analysis.yaml").exists():
        return
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "analyse" / "mongodb-analyse.py"),
            "--input-dir",
            str(incident_dir),
            "--output-file",
            str(incident_dir / "analysis.yaml"),
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("failed to generate analysis for fixture: %s" % proc.stderr.strip())


def sanitize_input(source_input: Dict[str, Any], case_id: str, scenario: str, customer_clue: str) -> Dict[str, Any]:
    return {
        "incident_id": "fixture-mongodb-%s" % case_id,
        "middleware": str(source_input.get("middleware") or "mongodb"),
        "scenario": scenario or str(source_input.get("scenario") or "unknown"),
        "customer_clue": customer_clue or str(source_input.get("customer_clue") or "Frozen MongoDB replay fixture."),
        "input_source": "fixture",
        "received_at": now_iso(),
    }


def freeze_fixture(incident_dir: Path, fixture_dir: Path, case_id: str, scenario: str, customer_clue: str, overwrite: bool) -> None:
    if fixture_dir.exists() and any(fixture_dir.iterdir()) and not overwrite:
        raise FileExistsError("fixture dir is not empty; pass --overwrite: %s" % fixture_dir)
    fixture_dir.mkdir(parents=True, exist_ok=True)
    ensure_analysis(incident_dir)

    required_source = ["input.yaml", "structured_record.yaml", "signal_bundle.yaml", "collection_report.yaml", "analysis.yaml"]
    for filename in required_source:
        if not (incident_dir / filename).exists():
            raise FileNotFoundError("incident missing required file: %s" % (incident_dir / filename))

    input_data = sanitize_input(load_yaml(incident_dir / "input.yaml"), case_id, scenario, customer_clue)
    write_yaml(fixture_dir / "input.yaml", input_data)
    for filename in ("structured_record.yaml", "signal_bundle.yaml", "collection_report.yaml"):
        shutil.copy2(incident_dir / filename, fixture_dir / filename)
    shutil.copy2(incident_dir / "analysis.yaml", fixture_dir / "expected_analysis.yaml")

    missing = [filename for filename in FIXTURE_FILES if not (fixture_dir / filename).exists()]
    if missing:
        raise RuntimeError("fixture freeze incomplete, missing: %s" % ", ".join(missing))


def main() -> int:
    args = parse_args()
    fixture_dir = resolve_path(args.fixture_dir)
    case_id = args.case_id or fixture_dir.name
    if args.remote_run_dir:
        incident_dir = build_incident_from_remote_run(resolve_path(args.remote_run_dir), case_id, args.scenario, args.customer_clue)
    else:
        incident_dir = resolve_path(args.incident_dir)
    freeze_fixture(incident_dir, fixture_dir, case_id, args.scenario, args.customer_clue, args.overwrite)
    print(str(fixture_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

import os
import sys
import tempfile
import unittest
import importlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.scenario_router import infer_scenario  # noqa: E402


FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "active" / "mongodb"
PULSAR_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "active" / "pulsar"


def load_fixture_signal_bundle(case_id: str) -> dict:
    path = FIXTURE_ROOT / case_id / "signal_bundle.yaml"
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_fixture_structured_record(case_id: str) -> dict:
    path = FIXTURE_ROOT / case_id / "structured_record.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class ScenarioRouterTest(unittest.TestCase):
    def test_load_routing_map_uses_runtime_root(self) -> None:
        module = importlib.import_module("shared.scenario_router")
        original_runtime_root = os.environ.get("MIDSTACK_TRIAGE_RUNTIME_ROOT")
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "runtime"
            routing_dir = runtime_root / "core" / "routing"
            routing_dir.mkdir(parents=True)
            routing_map = routing_dir / "scenario-signal-map.yaml"
            routing_map.write_text(
                yaml.safe_dump({"routing_map_id": "test.map", "routes": []}),
                encoding="utf-8",
            )
            os.environ["MIDSTACK_TRIAGE_RUNTIME_ROOT"] = str(runtime_root)
            try:
                reloaded = importlib.reload(module)
                self.assertEqual(reloaded.DEFAULT_MAP_PATH, routing_map)
                self.assertEqual(reloaded.load_routing_map()["routing_map_id"], "test.map")
            finally:
                if original_runtime_root is None:
                    os.environ.pop("MIDSTACK_TRIAGE_RUNTIME_ROOT", None)
                else:
                    os.environ["MIDSTACK_TRIAGE_RUNTIME_ROOT"] = original_runtime_root
                importlib.reload(module)

    def test_crashloop_routes_to_kubernetes_runtime(self) -> None:
        result = infer_scenario(load_fixture_signal_bundle("kubernetes-crashloop-sample"))
        self.assertEqual(result["scenario"], "kubernetes-runtime")
        self.assertIn(result["scenario_inference"]["confidence"], ("high", "medium"))

    def test_replica_inconsistency_routes(self) -> None:
        result = infer_scenario(load_fixture_signal_bundle("replica-inconsistency-sample"))
        self.assertEqual(result["scenario"], "replica-inconsistency")

    def test_connection_failure_routes(self) -> None:
        result = infer_scenario(load_fixture_signal_bundle("connection-failure-sample"))
        self.assertEqual(result["scenario"], "connection-failure")

    def test_flannel_overlay_routes_to_kubernetes_runtime(self) -> None:
        result = infer_scenario(load_fixture_signal_bundle("kubernetes-flannel-overlay-partition-root-cause"))
        self.assertEqual(result["scenario"], "kubernetes-runtime")

    def test_baseline_returns_unknown(self) -> None:
        result = infer_scenario(load_fixture_signal_bundle("baseline-sharded-cluster"))
        self.assertEqual(result["scenario"], "unknown")
        self.assertEqual(result["scenario_inference"]["confidence"], "low")

    def test_resource_insufficient_prefers_resource_exhaustion_or_k8s_runtime(self) -> None:
        result = infer_scenario(load_fixture_signal_bundle("kubernetes-resource-insufficient-sample"))
        self.assertIn(result["scenario"], ("resource-exhaustion", "kubernetes-runtime"))

    def test_overlapping_signals_mark_unresolved(self) -> None:
        signal_bundle = {
            "abnormal_signals": [
                {
                    "signal_id": "replica-member-recovering",
                    "severity": "medium",
                    "detail": "Replica member is RECOVERING.",
                },
                {
                    "signal_id": "pod-crashloop",
                    "severity": "high",
                    "detail": "Pod container is restarting.",
                },
            ]
        }
        result = infer_scenario(signal_bundle, middleware="mongodb")
        inference = result["scenario_inference"]
        self.assertTrue(inference["unresolved"])
        candidate_scenarios = {item["scenario"] for item in inference["candidates"]}
        self.assertIn("replica-inconsistency", candidate_scenarios)
        self.assertIn("kubernetes-runtime", candidate_scenarios)


class PulsarScenarioRouterTest(unittest.TestCase):
    def test_topic_backlog_routes(self) -> None:
        path = PULSAR_FIXTURE_ROOT / "topic-backlog-sample" / "signal_bundle.yaml"
        with path.open("r", encoding="utf-8") as fh:
            signal_bundle = yaml.safe_load(fh) or {}
        result = infer_scenario(signal_bundle, middleware="pulsar")
        self.assertEqual(result["scenario"], "queue-backlog")
        self.assertIn(result["scenario_inference"]["confidence"], ("high", "medium"))


if __name__ == "__main__":
    unittest.main()

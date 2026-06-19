#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RULES_PATH = ROOT / "src" / "phases" / "phase4" / "rules" / "mongodb.py"


def load_rules_module():
    spec = importlib.util.spec_from_file_location("phase4_rules_mongodb", RULES_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def replica_internal_hypothesis(hypotheses):
    for item in hypotheses:
        if "internal replica set state" in str(item.get("statement") or ""):
            return item
    raise AssertionError("missing replica internal hypothesis")


class MongoDBRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_rules_module()

    def test_h3_refuted_when_rs_status_healthy_after_eviction(self) -> None:
        input_data = {"scenario": "kubernetes-runtime"}
        signal_bundle = {"abnormal_signals": []}
        collection_report = {
            "evidence_gaps": [
                {"gap": "previous logs not collected from pod/bnmongo-shard0-data-0", "gap_type": "expected_gap"}
            ]
        }
        structured_record = {
            "details": {
                "events": [
                    {
                        "reason": "Evicted",
                        "message": "Pod ephemeral local storage usage exceeds the total limit of containers 2Gi.",
                        "involved_object": {"name": "bnmongo-shard0-data-0"},
                    }
                ],
                "replica_members": [
                    {
                        "replica_set_id": "bnmongo-shard0-data",
                        "source_pod_ref": "bnmongo-shard0-data-0",
                        "self_member": {"state_str": "PRIMARY", "health": 1},
                        "members": [
                            {"state_str": "PRIMARY", "health": 1},
                            {"state_str": "SECONDARY", "health": 1},
                        ],
                    }
                ],
            }
        }
        result = self.mod.analyse(input_data, signal_bundle, collection_report, structured_record)
        h3 = replica_internal_hypothesis(result["hypotheses"])
        self.assertEqual(result["hypotheses"][0]["status"], "supported")
        self.assertEqual(h3["status"], "refuted")
        self.assertIn("rs.status from pod/bnmongo-shard0-data-0", h3["supporting_evidence"][0]["detail"])
        self.assertEqual(result["conclusion_summary"]["primary_cause_category"], "kubernetes-runtime")

    def test_h3_insufficient_without_replica_members(self) -> None:
        input_data = {"scenario": "kubernetes-runtime"}
        signal_bundle = {"abnormal_signals": [{"signal_id": "pod-not-ready", "detail": "probe failed"}]}
        collection_report = {
            "evidence_gaps": [
                {
                    "gap": "rs.status not collected from any healthy replica set peer",
                    "gap_type": "critical_gap",
                }
            ]
        }
        result = self.mod.analyse(input_data, signal_bundle, collection_report, {})
        h3 = replica_internal_hypothesis(result["hypotheses"])
        self.assertEqual(h3["status"], "insufficient")

    def test_resource_pressure_is_medium_confidence_runtime_phenomenon(self) -> None:
        input_data = {"scenario": "kubernetes-runtime"}
        signal_bundle = {
            "abnormal_signals": [
                {
                    "signal_id": "node-resource-pressure",
                    "object_ref": "node/worker-1",
                    "detail": "Node resource metrics are high; cpu_percent=91 memory_percent=70",
                },
                {
                    "signal_id": "pod-resource-pressure",
                    "object_ref": "pod/mongo-0",
                    "detail": "Pod resource metrics are high; cpu_millicores=1200 memory_mi=768",
                },
            ]
        }

        result = self.mod.analyse(input_data, signal_bundle, {"evidence_gaps": []}, {})

        conclusion = result["conclusion_summary"]
        self.assertEqual(conclusion["primary_cause_category"], "kubernetes-resource-pressure")
        self.assertEqual(conclusion["confidence"], "medium")
        self.assertEqual(conclusion["deepest_supported_level"], "phenomenon")
        self.assertIn("sustained resource pressure", result["hypotheses"][0]["statement"])


if __name__ == "__main__":
    unittest.main()

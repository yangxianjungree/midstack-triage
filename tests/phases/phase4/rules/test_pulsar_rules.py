#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RULES_PATH = ROOT / "src" / "phases" / "phase4" / "rules" / "pulsar.py"


def load_rules_module():
    spec = importlib.util.spec_from_file_location("phase4_rules_pulsar", RULES_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PulsarRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_rules_module()

    def test_analysis_contract_reserves_experience_retrieval_fields(self) -> None:
        input_data = {
            "scenario": "queue-backlog",
            "incident_time": {"mode": "current_active"},
        }
        signal_bundle = {
            "abnormal_signals": [
                {"signal_id": "topic-backlog-high", "object_ref": "topic/orders", "detail": "Backlog is high"},
                {"signal_id": "consumer-lag-high", "object_ref": "subscription/orders-sub", "detail": "Lag is high"},
            ]
        }
        collection_report = {
            "evidence_gaps": [
                {"gap": "broker topic stats missing", "gap_type": "critical_gap"}
            ]
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report)

        self.assertEqual(result["retrieval_context"]["time_mode"], "current_active")
        self.assertEqual(result["retrieval_context"]["signal_ids"], ["topic-backlog-high", "consumer-lag-high"])
        self.assertEqual(result["retrieval_context"]["scenario_candidates"], ["queue-backlog"])
        self.assertEqual(result["retrieval_context"]["object_refs"], ["topic/orders", "subscription/orders-sub"])
        self.assertEqual(result["retrieval_context"]["evidence_gap_categories"], ["critical_gap"])
        self.assertEqual(result["experience_matches"], [])
        self.assertIn("historical_experience", result["source_boundaries"]["hypothesis_sources_only"])

    def test_reasoning_timeline_is_generated_from_backlog_signals(self) -> None:
        input_data = {"scenario": "queue-backlog"}
        signal_bundle = {
            "timeline_summary": ["backlog growth overlaps with payment topic alert"],
            "abnormal_signals": [
                {"signal_id": "topic-backlog-high", "object_ref": "topic/orders", "detail": "Backlog is high"},
            ],
        }
        collection_report = {"evidence_gaps": []}

        result = self.mod.analyse(input_data, signal_bundle, collection_report)

        summaries = [item["summary"] for item in result["reasoning_timeline"]["events"]]
        self.assertIn("backlog growth overlaps with payment topic alert", summaries)
        self.assertIn("topic-backlog-high: Backlog is high", summaries)

    def test_verification_requests_include_topic_stats_when_backlog_evidence_is_incomplete(self) -> None:
        input_data = {"scenario": "queue-backlog"}
        signal_bundle = {
            "abnormal_signals": [
                {"signal_id": "topic-backlog-high", "object_ref": "topic/orders", "detail": "Backlog is high"},
            ]
        }
        collection_report = {
            "evidence_gaps": [
                {"gap": "broker topic stats missing", "gap_type": "critical_gap"}
            ]
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report)

        self.assertEqual(len(result["verification_requests"]), 1)
        request = result["verification_requests"][0]
        self.assertEqual(request["asset"]["id"], "pulsar.collect.broker.topic_stats")
        self.assertEqual(request["asset"]["type"], "script")
        self.assertEqual(request["asset_tier"], "first_class")
        self.assertEqual(request["risk_level"], "read-only")
        self.assertEqual(request["execution_policy"], "auto_allowed")
        self.assertEqual(request["status"], "planned")


if __name__ == "__main__":
    unittest.main()

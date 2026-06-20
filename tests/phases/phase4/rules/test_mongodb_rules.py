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

    def test_analysis_contract_reserves_experience_retrieval_fields(self) -> None:
        input_data = {
            "scenario": "kubernetes-runtime",
            "scenario_candidates": "kubernetes-runtime",
            "incident_time": {"mode": "historical_resolved"},
        }
        signal_bundle = {
            "abnormal_signals": [
                {"signal_id": "pod-crashloop", "object_ref": "pod/mongo-0", "detail": "Pod is restarting"},
                {"signal_id": "pod-resource-pressure", "object_ref": "pod/mongo-0", "detail": "CPU high"},
            ]
        }
        collection_report = {
            "evidence_gaps": [
                {"gap": "kubectl logs are too short", "gap_category": "log_sample_quality"}
            ]
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report, {})

        self.assertEqual(result["retrieval_context"]["time_mode"], "historical_resolved")
        self.assertEqual(result["retrieval_context"]["signal_ids"], ["pod-crashloop", "pod-resource-pressure"])
        self.assertEqual(result["retrieval_context"]["scenario_candidates"], ["kubernetes-runtime"])
        self.assertEqual(result["retrieval_context"]["object_refs"], ["pod/mongo-0"])
        self.assertEqual(result["retrieval_context"]["evidence_gap_categories"], ["log_sample_quality"])
        self.assertEqual(result["experience_matches"], [])
        self.assertIn("historical_experience", result["source_boundaries"]["hypothesis_sources_only"])
        self.assertIn("must not be used as direct supporting evidence", result["source_boundaries"]["rule"])

    def test_verification_requests_include_readonly_first_class_assets_for_evidence_gaps(self) -> None:
        input_data = {"scenario": "kubernetes-runtime"}
        signal_bundle = {
            "abnormal_signals": [
                {"signal_id": "pod-crashloop", "object_ref": "pod/mongo-0", "detail": "Pod is restarting"},
            ]
        }
        collection_report = {
            "evidence_gaps": [
                {
                    "gap": "rs.status not collected from any healthy replica set peer",
                    "gap_type": "critical_gap",
                },
                {
                    "gap": "kubectl logs are too short to show MongoDB fatal startup logs",
                    "gap_category": "log_sample_quality",
                },
            ]
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report, {})

        hypothesis_ids = {item["hypothesis_id"] for item in result["hypotheses"]}
        requests = {item["asset"]["id"]: item for item in result["verification_requests"]}
        self.assertIn("mongodb.collect.replicaset.rs_status", requests)
        self.assertIn("kubernetes.collect.logs.previous", requests)
        for request in requests.values():
            self.assertIn(request["hypothesis_id"], hypothesis_ids)
            self.assertEqual(request["asset_tier"], "first_class")
            self.assertEqual(request["risk_level"], "read-only")
            self.assertEqual(request["execution_policy"], "auto_allowed")
            self.assertEqual(request["status"], "planned")
            self.assertEqual(request["asset"]["type"], "script")

    def test_reasoning_timeline_aggregates_signal_timeline_events_and_collection_actions(self) -> None:
        input_data = {"scenario": "kubernetes-runtime"}
        signal_bundle = {
            "timeline_summary": ["pod scheduling failed before rs.status collection"],
            "abnormal_signals": [
                {
                    "signal_id": "pod-node-selector-mismatch",
                    "object_ref": "pod/mongo-0",
                    "detail": "Scheduler reports node selector mismatch",
                }
            ],
        }
        collection_report = {
            "collection_actions": [
                {
                    "action_id": "mongodb-collect-pods-state",
                    "target": "mongo",
                    "status": "success",
                    "performed_at": "2026-06-07T00:00:00+08:00",
                }
            ],
            "evidence_gaps": [],
        }
        structured_record = {
            "details": {
                "events": [
                    {
                        "last_timestamp": "2026-06-07T00:01:00+08:00",
                        "reason": "FailedScheduling",
                        "message": "node selector mismatch",
                        "involved_object": {"name": "mongo-0"},
                    }
                ]
            }
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report, structured_record)

        timeline = result["reasoning_timeline"]
        summaries = [item["summary"] for item in timeline["events"]]
        self.assertIn("pod scheduling failed before rs.status collection", summaries)
        self.assertIn("pod-node-selector-mismatch: Scheduler reports node selector mismatch", summaries)
        self.assertIn("FailedScheduling on mongo-0: node selector mismatch", summaries)
        self.assertIn("collection mongodb-collect-pods-state status=success target=mongo", summaries)
        self.assertIn(
            "Timeline order is available for correlating symptoms, collection actions, and hypotheses.",
            timeline["findings"][0]["statement"],
        )

    def test_reasoning_timeline_prioritizes_split_brain_diagnostic_events(self) -> None:
        input_data = {"scenario": "replica-inconsistency"}
        signal_bundle = {
            "abnormal_signals": [{"signal_id": "replica-member-recovering", "detail": "member state differs"}],
            "log_highlights": [
                {
                    "pod_ref": "pod/bnmongo-mongos-0",
                    "log_type": "current",
                    "category": "connection",
                    "message": "lookup kube-dns 10.96.0.10:53 connection refused",
                }
            ],
        }
        collection_report = {
            "collection_actions": [
                {"action_id": "mongodb-collect-pods-state", "target": "psmdb-test", "status": "success"},
            ],
            "evidence_gaps": [],
        }
        structured_record = {
            "details": {
                "replica_members": [
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-0",
                        "voting_members_count": 1,
                        "self_member": {"state_str": "PRIMARY", "config_version": 2, "config_term": 73},
                        "members": [{"name": "mongo-0:27017", "state_str": "PRIMARY"}],
                    },
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-1",
                        "voting_members_count": 3,
                        "self_member": {"state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "(not reachable/healthy)"},
                            {"name": "mongo-1:27017", "state_str": "PRIMARY"},
                            {"name": "mongo-2:27017", "state_str": "SECONDARY"},
                        ],
                    },
                ],
                "network_overlay": {
                    "pod_connectivity_checks": [
                        {
                            "source_pod_ref": "mongo-0",
                            "target_ref": "pod/mongo-1",
                            "target_port": 27017,
                            "status": "success",
                        }
                    ]
                },
            }
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report, structured_record)

        events = result["reasoning_timeline"]["events"]
        summaries = [item["summary"] for item in events]
        self.assertIn("Replica set rs0 split-brain observed: 2 PRIMARY views and divergent voting quorum counts.", summaries)
        self.assertIn("Current TCP/27017 reachability succeeded after divergent replica-set views were observed.", summaries)
        self.assertTrue(any("DNS" in summary and "connection refused" in summary for summary in summaries))
        self.assertEqual(events[0]["layer"], "diagnostic")

    def test_reasoning_timeline_preserves_log_local_time_without_exact_timestamp(self) -> None:
        input_data = {"scenario": "replica-inconsistency"}
        signal_bundle = {
            "log_highlights": [
                {
                    "pod_ref": "bnmongo-shard0-data-0",
                    "log_type": "current",
                    "category": "election",
                    "message": " 01:32:32.22 INFO  ==> Setting node as primary",
                },
                {
                    "pod_ref": "bnmongo-mongos-0",
                    "log_type": "current",
                    "category": "connection",
                    "message": "mongodb 13:15:40.16 INFO  ==> cannot resolve host on 10.96.0.10:53: connection refused",
                },
            ]
        }
        collection_report = {"collection_actions": [], "evidence_gaps": []}

        result = self.mod.analyse(input_data, signal_bundle, collection_report, {})

        events = result["reasoning_timeline"]["events"]
        election_event = next(item for item in events if item["event_type"] == "log-highlight-election")
        dns_event = next(item for item in events if item["event_type"] == "dns-log-highlight")
        self.assertEqual(election_event["time"], "01:32:32.22")
        self.assertEqual(election_event["time_precision"], "log_local_time")
        self.assertEqual(dns_event["time"], "13:15:40.16")
        self.assertEqual(dns_event["time_precision"], "log_local_time")

    def test_deepening_findings_detect_replica_set_config_divergence_and_network_counter_evidence(self) -> None:
        input_data = {"scenario": "replica-inconsistency"}
        signal_bundle = {"abnormal_signals": [{"signal_id": "replica-member-recovering", "detail": "member state differs"}]}
        collection_report = {"evidence_gaps": []}
        structured_record = {
            "details": {
                "replica_members": [
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-0",
                        "voting_members_count": 1,
                        "self_member": {"state_str": "PRIMARY", "config_version": 2, "config_term": 73},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "PRIMARY", "config_version": 2, "config_term": 73}
                        ],
                    },
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-1",
                        "voting_members_count": 3,
                        "self_member": {"state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "(not reachable/healthy)"},
                            {"name": "mongo-1:27017", "state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                            {"name": "mongo-2:27017", "state_str": "SECONDARY", "config_version": 8, "config_term": 72},
                        ],
                    },
                ],
                "network_overlay": {
                    "pod_connectivity_checks": [
                        {
                            "source_pod_ref": "mongo-0",
                            "target_ref": "pod/mongo-1",
                            "target_port": 27017,
                            "status": "success",
                        }
                    ]
                },
            }
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report, structured_record)

        findings = {item["finding_id"]: item for item in result["deepening_findings"]}
        self.assertEqual(findings["mongodb.replica_set.config_divergence"]["severity"], "high")
        self.assertIn("config_version", findings["mongodb.replica_set.config_divergence"]["statement"])
        self.assertEqual(findings["mongodb.replica_set.membership_divergence"]["severity"], "high")
        self.assertEqual(findings["mongodb.replica_set.quorum_divergence"]["severity"], "high")
        self.assertEqual(findings["mongodb.network.current_tcp_reachability"]["supports"], [])
        self.assertEqual(findings["mongodb.network.current_tcp_reachability"]["refutes"], ["sustained_network_partition"])

    def test_replica_inconsistency_next_actions_use_deepening_findings(self) -> None:
        input_data = {"scenario": "replica-inconsistency"}
        signal_bundle = {"abnormal_signals": [{"signal_id": "replica-member-recovering", "detail": "member state differs"}]}
        collection_report = {"evidence_gaps": []}
        structured_record = {
            "details": {
                "replica_members": [
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-0",
                        "voting_members_count": 1,
                        "self_member": {"state_str": "PRIMARY", "config_version": 2, "config_term": 73},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "PRIMARY", "config_version": 2, "config_term": 73}
                        ],
                    },
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-1",
                        "voting_members_count": 3,
                        "self_member": {"state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "(not reachable/healthy)"},
                            {"name": "mongo-1:27017", "state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                            {"name": "mongo-2:27017", "state_str": "SECONDARY", "config_version": 8, "config_term": 72},
                        ],
                    },
                ],
                "network_overlay": {
                    "pod_connectivity_checks": [
                        {
                            "source_pod_ref": "mongo-0",
                            "target_ref": "pod/mongo-1",
                            "target_port": 27017,
                            "status": "success",
                        }
                    ]
                },
            }
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report, structured_record)

        actions = [item["action"] for item in result["next_actions"]]
        joined = "\n".join(actions)
        self.assertIn("rs.conf()", joined)
        self.assertIn("heartbeat/election", joined)
        self.assertIn("current TCP/27017 reachability has succeeded", joined)
        self.assertNotIn("run the scenario-specific runbook", joined)
        for item in result["next_actions"]:
            self.assertEqual(item["risk_level"], "read-only")

    def test_split_brain_deepening_adds_enabling_cause_hypotheses_and_verification_requests(self) -> None:
        input_data = {"scenario": "replica-inconsistency"}
        signal_bundle = {"abnormal_signals": [{"signal_id": "replica-member-recovering", "detail": "member state differs"}]}
        collection_report = {"evidence_gaps": []}
        structured_record = {
            "details": {
                "replica_members": [
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-0",
                        "voting_members_count": 1,
                        "self_member": {"state_str": "PRIMARY", "config_version": 2, "config_term": 73},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "PRIMARY", "config_version": 2, "config_term": 73}
                        ],
                    },
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-1",
                        "voting_members_count": 3,
                        "self_member": {"state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "(not reachable/healthy)"},
                            {"name": "mongo-1:27017", "state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                            {"name": "mongo-2:27017", "state_str": "SECONDARY", "config_version": 8, "config_term": 72},
                        ],
                    },
                ],
                "network_overlay": {
                    "pod_connectivity_checks": [
                        {
                            "source_pod_ref": "mongo-0",
                            "target_ref": "pod/mongo-1",
                            "target_port": 27017,
                            "status": "success",
                        }
                    ]
                },
            }
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report, structured_record)

        findings = {item["finding_id"]: item for item in result["deepening_findings"]}
        self.assertIn("mongodb.replica_set.enabling_cause_candidates", findings)
        self.assertIn("historical network or heartbeat partition", findings["mongodb.replica_set.enabling_cause_candidates"]["statement"])
        self.assertIn("historical_network_or_heartbeat_partition", findings["mongodb.replica_set.enabling_cause_candidates"]["supports"])
        self.assertIn("reconfig_or_member_config_drift", findings["mongodb.replica_set.enabling_cause_candidates"]["supports"])
        hypothesis_text = "\n".join(item["statement"] for item in result["hypotheses"])
        self.assertIn("historical network or MongoDB heartbeat partition", hypothesis_text)
        self.assertIn("Replica set configuration or member metadata drift", hypothesis_text)

        requests = {item["request_id"]: item for item in result["verification_requests"]}
        self.assertEqual(requests["vr-mongodb-rs-conf-compare"]["asset_tier"], "first_class")
        self.assertEqual(requests["vr-mongodb-rs-conf-compare"]["asset"]["type"], "script")
        self.assertEqual(requests["vr-mongodb-rs-conf-compare"]["asset"]["id"], "mongodb.collect.replicaset.rs_conf")
        self.assertEqual(requests["vr-mongodb-rs-conf-compare"]["execution_policy"], "auto_allowed")
        self.assertEqual(requests["vr-mongodb-rs-conf-compare"]["risk_level"], "read-only")
        self.assertEqual(requests["vr-mongodb-rs-conf-compare"]["hypothesis_id"], "H3")
        self.assertEqual(requests["vr-mongodb-election-logs"]["asset"]["id"], "kubernetes.collect.logs.previous")
        self.assertEqual(requests["vr-mongodb-election-logs"]["execution_policy"], "auto_allowed")
        self.assertEqual(requests["vr-mongodb-election-logs"]["hypothesis_id"], "H4")

    def test_split_brain_history_logs_support_enabling_cause_hypothesis(self) -> None:
        input_data = {"scenario": "replica-inconsistency"}
        signal_bundle = {
            "abnormal_signals": [{"signal_id": "replica-member-recovering", "detail": "member state differs"}],
            "log_highlights": [
                {
                    "pod_ref": "mongo-0",
                    "log_type": "file_tail",
                    "category": "connection",
                    "message": 'heartbeat failed with HostUnreachable: {"host":"mongo-1:27017"} connection refused',
                },
                {
                    "pod_ref": "mongo-0",
                    "log_type": "file_tail",
                    "category": "election",
                    "message": "transition to PRIMARY in term 73 after election timeout",
                },
            ],
        }
        collection_report = {"evidence_gaps": []}
        structured_record = {
            "details": {
                "replica_members": [
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-0",
                        "voting_members_count": 1,
                        "self_member": {"state_str": "PRIMARY", "config_version": 2, "config_term": 73},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "PRIMARY", "config_version": 2, "config_term": 73}
                        ],
                    },
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-1",
                        "voting_members_count": 3,
                        "self_member": {"state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "(not reachable/healthy)"},
                            {"name": "mongo-1:27017", "state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                            {"name": "mongo-2:27017", "state_str": "SECONDARY", "config_version": 8, "config_term": 72},
                        ],
                    },
                ]
            }
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report, structured_record)

        findings = {item["finding_id"]: item for item in result["deepening_findings"]}
        self.assertIn("mongodb.replica_set.history_election_heartbeat_logs", findings)
        history_hypothesis = next(
            item for item in result["hypotheses"] if "historical network or MongoDB heartbeat partition" in item["statement"]
        )
        self.assertEqual(history_hypothesis["status"], "supported")
        self.assertIn("heartbeat failed", history_hypothesis["supporting_evidence"][0]["detail"])
        self.assertFalse(
            any(item.get("gap_type") == "critical_gap" for item in history_hypothesis["evidence_gaps"])
        )

    def test_split_brain_deepening_adds_deep_analysis_requests(self) -> None:
        input_data = {"scenario": "replica-inconsistency"}
        signal_bundle = {"abnormal_signals": [{"signal_id": "replica-member-recovering", "detail": "member state differs"}]}
        collection_report = {"evidence_gaps": []}
        structured_record = {
            "details": {
                "replica_members": [
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-0",
                        "voting_members_count": 1,
                        "self_member": {"state_str": "PRIMARY", "config_version": 2, "config_term": 73},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "PRIMARY", "config_version": 2, "config_term": 73}
                        ],
                    },
                    {
                        "replica_set_id": "rs0",
                        "source_pod_ref": "mongo-1",
                        "voting_members_count": 3,
                        "self_member": {"state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                        "members": [
                            {"name": "mongo-0:27017", "state_str": "(not reachable/healthy)"},
                            {"name": "mongo-1:27017", "state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                            {"name": "mongo-2:27017", "state_str": "SECONDARY", "config_version": 8, "config_term": 72},
                        ],
                    },
                ],
                "network_overlay": {
                    "pod_connectivity_checks": [
                        {
                            "source_pod_ref": "mongo-0",
                            "target_ref": "pod/mongo-1",
                            "target_port": 27017,
                            "status": "success",
                        }
                    ]
                },
            }
        }

        result = self.mod.analyse(input_data, signal_bundle, collection_report, structured_record)

        requests = {item["request_id"]: item for item in result["deep_analysis_requests"]}
        self.assertEqual(set(requests), {"dar-mongodb-rs-baseline-scan", "dar-mongodb-rs-code-logic", "dar-mongodb-rs-code-path", "dar-mongodb-rs-repro-script"})
        self.assertEqual(requests["dar-mongodb-rs-baseline-scan"]["capability"], "baseline_scan")
        self.assertEqual(requests["dar-mongodb-rs-code-logic"]["capability"], "code_logic_analysis")
        self.assertEqual(requests["dar-mongodb-rs-code-path"]["capability"], "code_path_tracing")
        self.assertEqual(requests["dar-mongodb-rs-repro-script"]["capability"], "repro_script_generation")
        for item in requests.values():
            self.assertEqual(item["scope"], "current_incident")
            self.assertEqual(item["risk_level"], "read-only")
            self.assertEqual(item["status"], "planned")
            self.assertEqual(item["execution_boundary"], "plan_only")
            self.assertTrue(item["inputs"])
            self.assertTrue(item["expected_output"])


if __name__ == "__main__":
    unittest.main()

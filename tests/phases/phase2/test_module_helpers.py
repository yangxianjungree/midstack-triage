import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase2 import auth as phase2_auth
from phases.phase2 import events as phase2_events
from phases.phase2 import targets as phase2_targets
from phases.phase2 import topology as phase2_topology


def test_auth_helpers_select_highest_scored_secret():
    pod = {
        "metadata": {"namespace": "psmdb-test", "name": "mongo-0"},
        "spec": {
            "containers": [
                {
                    "name": "mongod",
                    "env": [
                        {"name": "MONGO_ROOT_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "mongo-auth", "key": "password"}}},
                        {"name": "IGNORED", "valueFrom": {"secretKeyRef": {"name": "other", "key": "token"}}},
                    ],
                }
            ]
        },
    }

    refs = phase2_auth.mongodb_auth_secret_refs("Pod", pod, ["shard"])

    assert refs == [
        {
            "namespace": "psmdb-test",
            "name": "mongo-auth",
            "key": "password",
            "env_name": "MONGO_ROOT_PASSWORD",
            "source_kind": "Pod",
            "source_name": "mongo-0",
            "source_container": "mongod",
            "score": 60,
        },
        {
            "namespace": "psmdb-test",
            "name": "other",
            "key": "token",
            "env_name": "IGNORED",
            "source_kind": "Pod",
            "source_name": "mongo-0",
            "source_container": "mongod",
            "score": 10,
        },
    ]

    hints = phase2_auth.build_auth_hints(
        "psmdb-test",
        refs
        + [
            {
                "namespace": "other",
                "name": "cluster-auth",
                "key": "password",
                "env_name": "ROOT",
                "source_kind": "StatefulSet",
                "source_name": "mongo-1",
                "source_container": "mongod",
                "score": 95,
            }
        ],
    )

    assert hints["selected_secret_ref"] == {"namespace": "psmdb-test", "name": "mongo-auth", "key": "password"}
    assert [item["name"] for item in hints["secret_ref_candidates"]] == ["mongo-auth", "other"]


def test_targets_and_topology_builders():
    objects = [
        {"kind": "Pod", "name": "mongo-0", "namespace": "psmdb-test", "node_name": "node-a", "mongodb_role_hints": ["mongos"], "deployment_architecture_hints": ["operator_crd"]},
        {"kind": "Service", "name": "mongo-svc", "namespace": "psmdb-test", "deployment_architecture_hints": ["operator_crd"]},
        {"kind": "StatefulSet", "name": "mongo-rs", "namespace": "psmdb-test", "deployment_architecture_hints": ["bitnami"]},
    ]

    inventory = {"selected_namespace": "psmdb-test", "objects": objects}

    assert phase2_targets.inventory_scope_objects(inventory) == objects

    targets = phase2_targets.build_mongodb_targets("psmdb-test", objects)
    assert targets == {
        "namespace": "psmdb-test",
        "statefulset_refs": ["mongo-rs"],
        "service_refs": ["mongo-svc"],
        "pod_refs": ["mongo-0"],
        "node_refs": ["node-a"],
        "mongos_pod_ref": "mongo-0",
    }

    topology = phase2_topology.build_topology_hints(objects)
    assert topology == {
        "candidate_topology_type": "sharded_cluster",
        "role_counts": {"mongos": 1, "unknown": 2},
        "kind_counts": {"Pod": 1, "Service": 1, "StatefulSet": 1},
    }
    assert phase2_topology.deployment_architecture_candidates(objects) == ["bitnami", "operator_crd"]


def test_related_event_matches_involved_object_and_regarding():
    assert phase2_events.related_event({"involvedObject": {"name": "mongo-0"}}, ["mongo-0", "mongo-1"])
    assert phase2_events.related_event({"regarding": {"name": "mongo-1"}}, ["mongo-0", "mongo-1"])
    assert not phase2_events.related_event({"involvedObject": {"name": "other"}}, ["mongo-0"])

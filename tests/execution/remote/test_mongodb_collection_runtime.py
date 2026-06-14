#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution.remote.mongodb_collection_runtime import (  # noqa: E402
    container_names_for_pod,
    resolve_mongodb_collection_targets,
    resolve_running_mongod_pods,
    resolve_running_mongos_pods,
)


def pod(name: str, phase: str = "Running", ready: bool = True, labels=None) -> dict:
    conditions = [{"type": "Ready", "status": "True" if ready else "False"}] if ready is not None else []
    return {
        "metadata": {"name": name, "labels": labels or {}},
        "status": {"phase": phase, "conditions": conditions},
        "spec": {"containers": [{"name": "mongod"}, {"name": "sidecar"}]},
    }


class MongoDBCollectionRuntimeTest(unittest.TestCase):
    def test_resolve_running_mongos_pods(self) -> None:
        pods = [
            pod("bnmongo-mongos-a"),
            pod("bnmongo-mongos-b"),
            pod("bnmongo-configsvr-0"),
            pod("bnmongo-mongos-old", phase="Failed"),
        ]
        refs = resolve_running_mongos_pods(pods)
        self.assertEqual(refs, ["bnmongo-mongos-a", "bnmongo-mongos-b"])

    def test_resolve_running_mongod_pods(self) -> None:
        pods = [
            pod("bnmongo-shard0-data-0"),
            pod("bnmongo-configsvr-1"),
            pod("bnmongo-mongos-a"),
            pod("bnmongo-shard0-data-1", phase="Pending"),
        ]
        refs = resolve_running_mongod_pods(pods)
        self.assertEqual(refs, ["bnmongo-configsvr-1", "bnmongo-shard0-data-0"])

    def test_container_names_only_use_pod_spec(self) -> None:
        item = pod("bnmongo-shard0-data-0")
        item["spec"]["containers"] = [{"name": "mongodb"}]
        names = container_names_for_pod(item, {})
        self.assertEqual(names, ["mongodb"])

    def test_container_names_prefer_first_container(self) -> None:
        names = container_names_for_pod(pod("bnmongo-shard0-data-0"), {})
        self.assertEqual(names[0], "mongod")

    def test_resolve_mongodb_collection_targets(self) -> None:
        pods = [
            pod("bnmongo-mongos-a"),
            pod("bnmongo-shard0-data-0"),
            pod("bnmongo-configsvr-0"),
        ]
        result = resolve_mongodb_collection_targets(pods)
        self.assertEqual(result["mongos_pod_refs"], ["bnmongo-mongos-a"])
        self.assertEqual(
            result["mongod_pod_refs"],
            ["bnmongo-configsvr-0", "bnmongo-shard0-data-0"],
        )
        self.assertIn("mongo_exec", result)


if __name__ == "__main__":
    unittest.main()

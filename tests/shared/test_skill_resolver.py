#!/usr/bin/env python3

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.skill_resolver import (  # noqa: E402
    missing_required_scripts,
    script_collection_statuses,
)


class SkillResolverTest(unittest.TestCase):
    def test_resolve_skills_uses_runtime_root(self) -> None:
        module = importlib.import_module("shared.skill_resolver")
        original_runtime_root = os.environ.get("MIDSTACK_TRIAGE_RUNTIME_ROOT")
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / "runtime"
            skill_dir = runtime_root / "domains" / "mongodb" / "skills" / "replica-set" / "demo"
            skill_dir.mkdir(parents=True)
            (skill_dir / "metadata.yaml").write_text(
                yaml.safe_dump(
                    {
                        "id": "mongodb.skill.demo",
                        "title": "Demo",
                        "middleware": "mongodb",
                        "component": "replica-set",
                        "primary_scenario": "replica-inconsistency",
                        "required_assets": ["demo"],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            os.environ["MIDSTACK_TRIAGE_RUNTIME_ROOT"] = str(runtime_root)
            try:
                reloaded = importlib.reload(module)
                matches = reloaded.resolve_skills("mongodb", "replica-inconsistency")
                self.assertEqual([item["id"] for item in matches], ["mongodb.skill.demo"])
                self.assertEqual(matches[0]["skill_dir"], skill_dir)
            finally:
                if original_runtime_root is None:
                    os.environ.pop("MIDSTACK_TRIAGE_RUNTIME_ROOT", None)
                else:
                    os.environ["MIDSTACK_TRIAGE_RUNTIME_ROOT"] = original_runtime_root
                importlib.reload(module)

    def test_script_collection_statuses_reads_script_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            script_dir = output_dir / "script_outputs" / "mongodb.collect.pods.state"
            script_dir.mkdir(parents=True)
            payload = {
                "script_id": "mongodb.collect.pods.state",
                "status": "success",
            }
            with (script_dir / "output.yaml").open("w", encoding="utf-8") as fh:
                yaml.safe_dump(payload, fh, sort_keys=False)

            statuses = script_collection_statuses(output_dir, {"collection_actions": []})
            self.assertEqual(statuses["mongodb.collect.pods.state"], "success")

    def test_missing_required_scripts_ignores_domain_success_items(self) -> None:
        collection_report = {
            "successful_items": ["broker_topic_stats"],
            "collection_actions": [],
        }
        statuses = script_collection_statuses(Path("/tmp/nonexistent"), collection_report)
        required = ["pulsar.collect.broker.topic_stats"]
        self.assertEqual(missing_required_scripts(required, statuses), required)

    def test_missing_required_scripts_honors_remote_executor_items(self) -> None:
        collection_report = {
            "successful_items": [{"item": "remote-executor/pulsar.collect.pods.state"}],
            "collection_actions": [],
        }
        statuses = script_collection_statuses(Path("/tmp/nonexistent"), collection_report)
        required = ["pulsar.collect.pods.state", "pulsar.collect.broker.topic_stats"]
        self.assertEqual(missing_required_scripts(required, statuses), ["pulsar.collect.broker.topic_stats"])


if __name__ == "__main__":
    unittest.main()

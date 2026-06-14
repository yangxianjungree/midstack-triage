#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "mongodb" / "kubernetes-crashloop-sample"


class MidstackAnalyseTest(unittest.TestCase):
    def test_analyse_fails_for_unknown_middleware(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "redis-incident"
            shutil.copytree(FIXTURE_ROOT, output_dir)
            input_data = yaml.safe_load((output_dir / "input.yaml").read_text(encoding="utf-8"))
            input_data["middleware"] = "redis"
            input_data["incident_id"] = "redis-unknown-middleware"
            (output_dir / "input.yaml").write_text(yaml.safe_dump(input_data, sort_keys=False), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "plugin" / "midstack-local.py"),
                    "analyse",
                    "--input-dir",
                    str(output_dir),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("no analyse runner available for middleware redis", proc.stderr)
            adapter = yaml.safe_load((output_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
            self.assertEqual(adapter["status"], "failed")
            self.assertEqual(adapter["blocking_items"][0]["code"], "unsupported_middleware_analyse")
            self.assertFalse((output_dir / "analysis.yaml").exists())

    def test_analyse_incident_dir_missing_remote_config_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            incident_dir = workspace / ".local" / "incidents" / "mongodb-ready-incident"
            incident_dir.mkdir(parents=True, exist_ok=True)
            (incident_dir / "input.yaml").write_text(
                yaml.safe_dump(
                    {
                        "incident_id": "mongodb-ready-incident",
                        "middleware": "mongodb",
                        "namespace": "mongo",
                        "customer_clue": "MongoDB pod is not ready.",
                        "scenario": "unknown",
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )
            (incident_dir / "meta.yaml").write_text(
                yaml.safe_dump(
                    {
                        "incident_id": "mongodb-ready-incident",
                        "middleware": "mongodb",
                        "status": "ready",
                        "current_command": "start",
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["MIDSTACK_TRIAGE_WORKSPACE"] = str(workspace)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "plugin" / "midstack-local.py"),
                    "analyse",
                    "--incident-dir",
                    str(incident_dir),
                ],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self.assertEqual(proc.returncode, 0)
            adapter = yaml.safe_load((incident_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
            self.assertEqual(adapter["status"], "blocked")
            self.assertEqual(adapter["blocking_items"][0]["code"], "missing_remote_config")
            self.assertIn("rerun /midstack:start", adapter["next_actions"][0])


if __name__ == "__main__":
    unittest.main()

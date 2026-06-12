#!/usr/bin/env python3

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
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


if __name__ == "__main__":
    unittest.main()

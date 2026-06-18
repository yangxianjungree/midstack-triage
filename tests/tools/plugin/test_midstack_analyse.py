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
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "active" / "mongodb" / "kubernetes-crashloop-sample"


class MidstackAnalyseTest(unittest.TestCase):
    def test_analyse_input_dir_completed_writes_expected_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "mongodb-incident"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "plugin" / "midstack-local.py"),
                    "analyse",
                    "--input-dir",
                    str(FIXTURE_ROOT),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            adapter = yaml.safe_load((output_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
            record_ref_names = {item["name"] for item in adapter["record_refs"]}
            self.assertEqual(adapter["status"], "completed")
            self.assertIn("analysis", record_ref_names)
            self.assertIn("analysis_multitrack", record_ref_names)
            self.assertIn("analysis_rules_fallback", record_ref_names)
            self.assertIn("agent_reasoning_task", record_ref_names)
            self.assertIn("report", record_ref_names)
            self.assertTrue((output_dir / "analysis.yaml").exists())
            self.assertTrue((output_dir / "analysis.multitrack.yaml").exists())
            self.assertTrue((output_dir / "analysis.rules-fallback.yaml").exists())
            self.assertTrue((output_dir / "agent-reasoning-task.md").exists())
            self.assertTrue((output_dir / "report.md").exists())

    def test_analyse_offline_input_dir_completed_without_remote_collection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "mongodb-incident"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "plugin" / "midstack-local.py"),
                    "analyse",
                    "--execution-mode",
                    "offline",
                    "--input-dir",
                    str(FIXTURE_ROOT),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            adapter = yaml.safe_load((output_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
            self.assertEqual(adapter["status"], "completed")
            self.assertTrue((output_dir / "analysis.yaml").exists())
            self.assertFalse((output_dir / "remote-executor.stdout.txt").exists())

    def test_analyse_local_mode_is_blocked_until_executor_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "incidents"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "plugin" / "midstack-local.py"),
                    "analyse",
                    "--execution-mode",
                    "local",
                    "--output-root",
                    str(output_root),
                ],
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.assertEqual(proc.returncode, 0)
            adapter = yaml.safe_load((output_root / "adapter-output.yaml").read_text(encoding="utf-8"))
            self.assertEqual(adapter["status"], "blocked")
            self.assertEqual(adapter["blocking_items"][0]["code"], "local_execution_not_implemented")

    def test_analyse_offline_incident_without_artifacts_is_blocked(self) -> None:
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
                    "--execution-mode",
                    "offline",
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
            self.assertEqual(adapter["blocking_items"][0]["code"], "offline_artifacts_missing")

    def test_analyse_remote_run_blocked_writes_adapter_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            remote_run_dir = workspace / "remote-runs" / "mongodb-blocked-run"
            remote_run_dir.mkdir(parents=True, exist_ok=True)
            (remote_run_dir / "remote-executor-run.yaml").write_text(
                yaml.safe_dump(
                    {
                        "incident_id": "mongodb-blocked-run",
                        "middleware": "mongodb",
                        "status": "blocked",
                        "error": {
                            "code": "missing_sshpass",
                            "message": "sshpass is required for password-based SSH access",
                        },
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )
            output_dir = workspace / "incident"
            env = dict(os.environ)
            env["MIDSTACK_TRIAGE_WORKSPACE"] = str(workspace)

            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "plugin" / "midstack-local.py"),
                    "analyse",
                    "--remote-run-dir",
                    str(remote_run_dir),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.assertEqual(proc.returncode, 0)
            adapter = yaml.safe_load((output_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
            self.assertEqual(adapter["status"], "blocked")
            self.assertEqual(adapter["summary"], "remote signal collection is blocked")
            self.assertEqual(adapter["blocking_items"][0]["code"], "missing_sshpass")
            self.assertIn("install sshpass locally", adapter["blocking_items"][0]["required_user_action"])
            self.assertTrue((output_dir / "remote-executor-run.yaml").exists())
            self.assertFalse((output_dir / "analysis.yaml").exists())

    def test_analyse_remote_run_failed_writes_adapter_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            remote_run_dir = workspace / "remote-runs" / "mongodb-failed-run"
            remote_run_dir.mkdir(parents=True, exist_ok=True)
            (remote_run_dir / "remote-executor-run.yaml").write_text(
                yaml.safe_dump(
                    {
                        "incident_id": "mongodb-failed-run",
                        "middleware": "mongodb",
                        "status": "failed",
                        "error": {
                            "code": "ssh_unreachable",
                            "message": "ssh connection timed out",
                        },
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )
            output_dir = workspace / "incident"
            env = dict(os.environ)
            env["MIDSTACK_TRIAGE_WORKSPACE"] = str(workspace)

            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "plugin" / "midstack-local.py"),
                    "analyse",
                    "--remote-run-dir",
                    str(remote_run_dir),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.assertEqual(proc.returncode, 1)
            self.assertIn("ssh connection timed out", proc.stderr)
            adapter = yaml.safe_load((output_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
            self.assertEqual(adapter["status"], "failed")
            self.assertEqual(adapter["summary"], "remote signal collection failed")
            self.assertIn("ssh connection timed out", adapter["warnings"])
            self.assertIn("fix remote SSH connectivity", adapter["next_actions"][0])
            self.assertTrue((output_dir / "remote-executor-run.yaml").exists())
            self.assertFalse((output_dir / "analysis.yaml").exists())

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

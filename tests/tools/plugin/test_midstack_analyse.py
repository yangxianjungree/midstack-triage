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
            self.assertIn("| Field | Value |", adapter["user_message"])
            self.assertIn("| Status | `completed` |", adapter["user_message"])
            self.assertIn("| Report | `%s` |" % (output_dir / "report.md"), adapter["user_message"])
            self.assertNotEqual(adapter["user_message"], "local analyse completed")
            self.assertIn("analysis", record_ref_names)
            self.assertIn("analysis_multitrack", record_ref_names)
            self.assertIn("analysis_rules_fallback", record_ref_names)
            self.assertIn("agent_reasoning_task", record_ref_names)
            self.assertIn("deep_analysis", record_ref_names)
            self.assertIn("reasoning_manifest", record_ref_names)
            self.assertIn("reasoning_current_segment", record_ref_names)
            self.assertIn("report", record_ref_names)
            self.assertTrue((output_dir / "analysis.yaml").exists())
            self.assertTrue((output_dir / "analysis.multitrack.yaml").exists())
            self.assertTrue((output_dir / "analysis.rules-fallback.yaml").exists())
            self.assertTrue((output_dir / "deep-analysis.yaml").exists())
            self.assertTrue((output_dir / "agent-reasoning-task.md").exists())
            self.assertTrue((output_dir / "reasoning-manifest.yaml").exists())
            self.assertTrue((output_dir / "reasoning" / "0001-rules-fallback.yaml").exists())
            self.assertTrue((output_dir / "reasoning" / "0002-agent-multitrack.yaml").exists())
            self.assertTrue((output_dir / "report.md").exists())
            analysis = yaml.safe_load((output_dir / "analysis.yaml").read_text(encoding="utf-8"))
            deep_analysis = yaml.safe_load((output_dir / "deep-analysis.yaml").read_text(encoding="utf-8"))
            manifest = yaml.safe_load((output_dir / "reasoning-manifest.yaml").read_text(encoding="utf-8"))
            agent_segment = yaml.safe_load((output_dir / "reasoning" / "0002-agent-multitrack.yaml").read_text(encoding="utf-8"))
            self.assertEqual(analysis["agent_reasoning"]["artifact"], "analysis.multitrack.yaml")
            self.assertTrue(analysis["agent_reasoning"]["hypotheses"])
            self.assertEqual(analysis["agent_conclusion_gate"]["decision"], "blocked")
            self.assertFalse(analysis["agent_conclusion_gate"]["override_applied"])
            self.assertEqual(agent_segment["agent_conclusion_gate"]["decision"], "blocked")
            self.assertEqual(deep_analysis["summary"]["total_requests"], 0)
            self.assertNotIn("deep_analysis_results", analysis)
            self.assertEqual([item["source"] for item in manifest["segments"]], ["rules_fallback", "agent_multitrack"])
            self.assertNotIn("read agent-reasoning-task.md", "\n".join(adapter["next_actions"]))

    def test_analyse_offline_input_dir_completed_without_remote_collection(self) -> None:
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
            self.assertEqual(adapter["status"], "completed")
            self.assertTrue((output_dir / "analysis.yaml").exists())
            self.assertFalse((output_dir / "remote-executor.stdout.txt").exists())

    def test_analyse_without_current_incident_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "incidents"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "plugin" / "midstack-local.py"),
                    "analyse",
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
            self.assertEqual(adapter["blocking_items"][0]["code"], "missing_current_incident")

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
                        "environment_mode": "offline",
                        "execution_mode": "offline",
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
            self.assertEqual(adapter["blocking_items"][0]["code"], "offline_artifacts_missing")

    def test_analyse_offline_incident_uses_artifact_source_from_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            artifact_dir = workspace / "artifacts" / "mongodb-offline"
            incident_dir = workspace / ".local" / "incidents" / "mongodb-offline"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(FIXTURE_ROOT, artifact_dir, dirs_exist_ok=True)
            incident_dir.mkdir(parents=True, exist_ok=True)
            (incident_dir / "input.yaml").write_text(
                yaml.safe_dump(
                    {
                        "incident_id": "mongodb-offline",
                        "middleware": "mongodb",
                        "namespace": "",
                        "customer_clue": "offline artefacts from start",
                        "environment_mode": "offline",
                        "execution_mode": "offline",
                        "artifact_source": str(artifact_dir),
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ),
                encoding="utf-8",
            )
            (incident_dir / "meta.yaml").write_text(
                yaml.safe_dump(
                    {
                        "incident_id": "mongodb-offline",
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

            self.assertEqual(proc.returncode, 0, proc.stderr)
            adapter = yaml.safe_load((incident_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
            self.assertEqual(adapter["status"], "completed")
            self.assertTrue((incident_dir / "analysis.yaml").exists())
            self.assertTrue((incident_dir / "signal_bundle.yaml").exists())

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

    def test_phase4_rules_expose_support_state_separately_from_registration(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        from phases.phase4.rules import middleware_support_state, supported_middlewares

        self.assertEqual(supported_middlewares(), ("mongodb", "pulsar"))
        self.assertEqual(middleware_support_state("mongodb"), "active_mvp")
        self.assertEqual(middleware_support_state("pulsar"), "contract_path")
        self.assertEqual(middleware_support_state("redis"), "unsupported")

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

    def test_analyse_local_incident_missing_local_config_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            incident_dir = workspace / ".local" / "incidents" / "mongodb-local-ready"
            incident_dir.mkdir(parents=True, exist_ok=True)
            (incident_dir / "input.yaml").write_text(
                yaml.safe_dump(
                    {
                        "incident_id": "mongodb-local-ready",
                        "middleware": "mongodb",
                        "namespace": "mongo",
                        "environment_mode": "local",
                        "execution_mode": "local",
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
                        "incident_id": "mongodb-local-ready",
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
            self.assertEqual(adapter["blocking_items"][0]["code"], "missing_local_config")
            self.assertIn("rerun /midstack:start --environment-mode local", adapter["next_actions"][0])


if __name__ == "__main__":
    unittest.main()

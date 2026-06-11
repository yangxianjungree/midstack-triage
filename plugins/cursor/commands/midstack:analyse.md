# Midstack Analyse

Use the `midstack-triage` MCP tools to run MongoDB triage analysis.

If the user just ran `/midstack:start` and does not provide an incident directory, call `midstack_analyse_current`.

If the user provides an incident directory from `/midstack:start`, call `midstack_analyse_incident`.

After the analyse tool returns `completed`:

- Open the generated incident directory and read `agent-reasoning-task.md`.
- Read `input.yaml`, `structured_record.yaml`, `signal_bundle.yaml`, and `collection_report.yaml`.
- Inspect `signal_bundle.log_highlights`, `structured_record.details.dns_checks`, `structured_record.details.pod_terminations`, and any `file_tail` log evidence before writing the final conclusion.
- Treat `analysis.rule-draft.yaml` as a fallback draft only, not the final diagnosis.
- Update `analysis.yaml` so it reflects Agent-led multi-hypothesis phase-4 reasoning and phase-5 conclusion.
- Classify material evidence gaps as `expected_gap` or `critical_gap`; unresolved `critical_gap` entries should cap conclusion depth and root-cause confidence.
- Keep current incident evidence separate from customer clues, historical cases, runbooks, and experience-based hypothesis sources.
- Use `deepest_supported_level` when useful to make the supported conclusion layer explicit: `phenomenon`, `impact`, `mechanism`, or `root_cause`.
- Treat DNS lookup errors and shallow bootstrap logs as hypotheses until CoreDNS/DNS probe evidence, flannel overlay evidence, MongoDB file-log evidence, or node-side file-log evidence supports the deeper mechanism.
- Distinguish DNS probe `blocked` from DNS probe `failed`; only failed checks with DNS-layer error text can support a DNS-failure mechanism.
- Update `report.md` so it matches the final `analysis.yaml`.
- Call `midstack_finalize_analysis` for the incident so `adapter-output.yaml` and `meta.yaml` stop pointing at the draft state.
- Then summarize the final conclusion, confidence, supported level, evidence gaps, and output paths.

Default fixture smoke:

- Call `midstack_analyse_fixture` with `input_dir=tests/fixtures/mongodb/connection-failure-sample` and `output_dir=.local/incidents/cursor-connection-failure`.
- Then call `midstack_review` with `incident_dir=.local/incidents/cursor-connection-failure`.
- Summarize the generated `analysis.yaml` path; review results live in its `review` block (no separate `review.yaml`).

If the user provides a remote run directory, call `midstack_analyse_remote_run` instead.

If the user provides a local remote config path such as `.local/test-envs/mongodb-k8s.yaml`, call `midstack_analyse_remote_config`.

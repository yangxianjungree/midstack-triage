# Case Studies

This directory stores incident case studies that are useful for improving Midstack
triage behavior, evidence collection, and reasoning discipline.

## Layout

- `mongodb/`: MongoDB incident case studies.
- `kubernetes/`: Kubernetes infrastructure and networking incident case studies.

## Conventions

- Preserve the original case-study files when importing from another project.
- Keep failed investigation paths when they explain why a tempting path was not
  evidence-backed.
- Separate current-incident evidence from hindsight, injected fault details, and
  known answers.
- Prefer dated directories named `<yyyy-mm-dd>-<short-case-name>`.

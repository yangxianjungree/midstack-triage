# Support

Midstack Triage is currently maintained by one person. Support is best-effort and has no response-time guarantee.

This repository is an open-source diagnostic framework, not a production incident response service.

## What GitHub Issues Are For

Use issues for:

- Reproducible bugs in Midstack runtime, plugin adapters, validators, scripts, docs, or fixtures
- Feature requests with clear scope and validation ideas
- Documentation gaps
- Reproducible install or compatibility problems

Good issues include:

- Midstack commit or version
- Adapter used: Claude, Cursor, or local CLI
- Python version and OS
- Command or slash command that was run
- Redacted error output
- Minimal fixture or synthetic reproduction when possible

## What GitHub Issues Are Not For

Do not use public issues for:

- Live production incident response
- "Please look at my cluster" requests
- Raw production logs, screenshots, or `.local/incidents/` uploads
- Credentials, kubeconfigs, API keys, SSH details, private keys, or database passwords
- Customer-specific root cause analysis that cannot be reproduced with redacted evidence
- Requests for urgent support or guaranteed response time

Issues that contain sensitive data may be closed or edited. Rotate exposed credentials immediately if you accidentally publish them.

## Discussions and Questions

General design questions, troubleshooting ideas, and middleware-domain discussions should be kept separate from reproducible bug reports. If GitHub Discussions are enabled, use Discussions for open-ended topics. If they are not enabled, keep issues narrowly actionable.

## Security Issues

Security reports must follow [SECURITY.md](SECURITY.md). Do not disclose vulnerabilities or sensitive incident material in public issues.

## Maintainer Capacity

Because maintainer time is limited:

- Incomplete issues may be labeled `needs-info` and closed if they do not receive enough detail.
- Large feature requests may be asked to start as a proposal or design discussion.
- Middleware support requests need domain assets, fixtures, and validation paths; a request alone does not make a domain supported.
- Pull requests with tests, docs, and redacted fixtures are much easier to review than broad requests.

## Commercial or Private Support

No commercial or private support channel is guaranteed by this repository. If one is offered later, it will be documented separately and will not change the open-source best-effort policy.

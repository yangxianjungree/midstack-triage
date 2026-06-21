# Security Policy

Midstack Triage handles incident clues, credentials, remote access metadata, Kubernetes state, middleware logs, and generated diagnosis artifacts. Treat all real incident data as sensitive.

## Supported Versions

Security fixes are applied to the `master` branch unless a release branch is explicitly announced.

## Reporting a Vulnerability

Do not open a public issue that contains secrets, customer data, private infrastructure details, incident artifacts, or exploit details.

Report security issues through a private channel controlled by the project maintainer. If no private channel has been announced for this repository yet, contact the maintainer listed in `NOTICE` and provide only a minimal, redacted summary first.

Include:

- A short description of the issue and affected component
- Impact and likely attack path
- Minimal reproduction steps using redacted data
- Affected commit, version, or plugin adapter

Do not include:

- Real SSH passwords, API keys, tokens, kubeconfigs, private keys, or database credentials
- Raw production logs or `.local/incidents/` directories
- Customer names, hostnames, cluster names, Pod names, IP addresses, or screenshots unless redacted

## Sensitive Data Rules

- Never commit `.local/`, generated incident output, raw customer evidence, kubeconfig files, private keys, or remote executor artifacts.
- Use documentation IP ranges such as `192.0.2.0/24`, `198.51.100.0/24`, or `203.0.113.0/24` for public examples.
- Use placeholders such as `root/example-password`, `example-token`, and `example-cluster` in examples.
- Do not paste `/midstack:start` prompts with real credentials into public issues or pull requests.
- Run the repository hygiene checks before publishing fixtures or case studies.

## Runtime Security Boundary

Midstack is designed for diagnostic workflows. By default it should collect read-only evidence and generate reviewable conclusions; it should not perform production changes or remediation actions automatically.

The runtime has two planes:

- Control plane: local/plugin Python runtime, reasoning, reporting, and incident state management.
- Execution plane: SSH/local shell access, Kubernetes read-only collection, script staging, and artifact retrieval.

Remote execution tools such as `ssh`, `sshpass`, `scp`, `kubectl`, `mongosh`, and `mongo` are runtime implementation details. Agent command surfaces must enter the bundled Midstack runtime first and must not bypass it with ad-hoc manual triage commands.

## Dependency and Disclosure Notes

The installed local/plugin runtime currently requires Python 3.10+ and PyYAML. Remote Phase 3 collection scripts are a separate compatibility boundary and should avoid unnecessary dependencies.

If a vulnerability requires a dependency upgrade or a change in runtime permissions, document the operational impact in the fix.

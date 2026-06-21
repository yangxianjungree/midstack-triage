#!/usr/bin/env python3

import argparse
import ipaddress
import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from support.common import ROOT  # noqa: E402

GENERATED_FILENAMES = {
    "adapter-output.yaml",
    "meta.yaml",
    "remote-config.yaml",
    "remote-executor-run.yaml",
    "remote-executor.stdout.txt",
    "remote-executor.stderr.txt",
}
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?key|secret[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"),
    re.compile(r"(?i)\bpassword\s*[:=]\s*['\"]?(?!example-password\b|secret\b)[^'\"\s]{8,}"),
]
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
ALLOWED_IPS = {
    "10.0.0.1",
}
DOCUMENTATION_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "192.0.2.0/24",
        "198.51.100.0/24",
        "203.0.113.0/24",
    )
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate that repository fixtures are free of runtime-generated files and obvious secrets.")
    return parser.parse_args()


def iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("**/*")):
            if path.is_file():
                yield path


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if ip.version != 4:
        return False
    if value in ALLOWED_IPS:
        return False
    if any(ip in network for network in DOCUMENTATION_NETWORKS):
        return False
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return False
    return True


def is_private_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if value in ALLOWED_IPS:
        return False
    if any(ip in network for network in DOCUMENTATION_NETWORKS):
        return False
    return ip.version == 4 and ip.is_private


def validate_fixture_hygiene(root: Path = ROOT) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    scan_roots = [
        root / "tests" / "fixtures" / "active",
        root / "tests" / "fixtures" / "legacy",
        root / "tests" / "golden-paths" / "fixtures",
    ]
    for path in iter_files(scan_roots):
        rel = str(path.relative_to(root))
        if path.name in GENERATED_FILENAMES:
            errors.append("generated fixture artifact tracked in repository: %s" % rel)
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append("possible secret in fixture: %s" % rel)
                break
        for match in IP_PATTERN.finditer(text):
            value = match.group(0)
            if is_public_ip(value):
                errors.append("public IP address in fixture: %s (%s)" % (rel, value))
            elif is_private_ip(value):
                warnings.append("private IP address in fixture: %s (%s)" % (rel, value))
    return errors, warnings


def main() -> int:
    parse_args()
    errors, warnings = validate_fixture_hygiene(ROOT)
    if errors:
        print("Fixture hygiene validation failed:", file=sys.stderr)
        for item in errors:
            print("- %s" % item, file=sys.stderr)
        for item in warnings:
            print("WARNING: %s" % item, file=sys.stderr)
        return 1

    for item in warnings:
        print("WARNING: %s" % item, file=sys.stderr)
    print("Fixture hygiene validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

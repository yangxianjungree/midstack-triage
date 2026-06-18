#!/usr/bin/env python3

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from support.common import ROOT, run_command  # noqa: E402
from scenario_routing_validator import validate_contract  # noqa: E402

TEST_FILES = [
    ROOT / "tests" / "shared" / "test_scenario_router.py",
    ROOT / "tests" / "shared" / "test_skill_resolver.py",
    ROOT / "tests" / "tools" / "plugin" / "test_midstack_analyse.py",
]


def main() -> int:
    errors = validate_contract(ROOT)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    for test_file in TEST_FILES:
        if not test_file.exists():
            print("missing unit test: %s" % test_file, file=sys.stderr)
            return 1
        proc = run_command([sys.executable, str(test_file)])
        if proc.returncode != 0:
            print("unit test validation failed: %s" % test_file, file=sys.stderr)
            return proc.returncode
    print("scenario routing and analyse unit tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

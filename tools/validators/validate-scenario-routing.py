#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_FILES = [
    ROOT / "tests" / "unit" / "test_scenario_router.py",
    ROOT / "tests" / "unit" / "test_skill_resolver.py",
    ROOT / "tests" / "unit" / "test_midstack_analyse.py",
]


def main() -> int:
    for test_file in TEST_FILES:
        if not test_file.exists():
            print("missing unit test: %s" % test_file, file=sys.stderr)
            return 1
        proc = subprocess.run(
            [sys.executable, str(test_file)],
            cwd=str(ROOT),
        )
        if proc.returncode != 0:
            print("unit test validation failed: %s" % test_file, file=sys.stderr)
            return proc.returncode
    print("scenario routing and analyse unit tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

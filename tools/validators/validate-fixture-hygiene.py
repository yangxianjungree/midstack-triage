#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
from typing import List


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "fixtures"
GENERATED_FILENAMES = {
    "adapter-output.yaml",
    "meta.yaml",
    "remote-config.yaml",
    "remote-executor-run.yaml",
    "remote-executor.stdout.txt",
    "remote-executor.stderr.txt",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate that repository fixtures are free of runtime-generated files.")
    return parser.parse_args()


def main() -> int:
    parse_args()
    errors: List[str] = []
    for path in sorted(FIXTURE_ROOT.glob("**/*")):
        if not path.is_file():
            continue
        if path.name in GENERATED_FILENAMES:
            errors.append(str(path.relative_to(ROOT)))

    if errors:
        print("Fixture hygiene validation failed:", file=sys.stderr)
        for item in errors:
            print("- generated fixture artifact tracked in repository: %s" % item, file=sys.stderr)
        return 1

    print("Fixture hygiene validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

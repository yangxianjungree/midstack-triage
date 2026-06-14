#!/usr/bin/env python3

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution.remote.executor import main as executor_main


def main() -> int:
    return executor_main()


if __name__ == "__main__":
    raise SystemExit(main())

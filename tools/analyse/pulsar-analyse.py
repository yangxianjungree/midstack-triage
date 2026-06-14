#!/usr/bin/env python3

import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase4.rules.pulsar import *  # noqa: F401,F403


if __name__ == "__main__":
    raise SystemExit(main())

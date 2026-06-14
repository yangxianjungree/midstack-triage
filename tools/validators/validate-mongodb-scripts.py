#!/usr/bin/env python3

import sys
from pathlib import Path


VALIDATORS_DIR = Path(__file__).resolve().parent
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))

from mongodb_assets.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

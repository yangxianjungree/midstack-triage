#!/usr/bin/env python3

import os
import runpy
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PLUGIN_ROOT / "runtime"

os.environ.setdefault("MIDSTACK_TRIAGE_RUNTIME_ROOT", str(RUNTIME_ROOT))
sys.path.insert(0, str(RUNTIME_ROOT / "tools" / "lib"))
sys.path.insert(0, str(RUNTIME_ROOT / "src"))

runpy.run_path(str(RUNTIME_ROOT / "tools" / "validators" / "validate-repo.py"), run_name="__main__")

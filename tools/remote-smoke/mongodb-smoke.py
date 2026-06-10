#!/usr/bin/env python3

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    module_path = ROOT / "tools" / "remote-executor" / "mongodb-executor.py"
    globals_dict = runpy.run_path(str(module_path), run_name="__main__")
    return int(globals_dict.get("__return_code__", 0))


if __name__ == "__main__":
    main()

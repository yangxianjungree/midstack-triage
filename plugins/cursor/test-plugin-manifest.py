#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli_smoke import assert_command_contracts, check_manifest


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    check_manifest()
    assert_command_contracts()
    print("ok: plugin manifest and agent-cli contracts valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

import sys
import tempfile
import unittest
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.io import load_yaml_object, write_json_object, write_yaml_object  # noqa: E402


class SharedIoTest(unittest.TestCase):
    def test_load_yaml_object_requires_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "payload.yaml"
            path.write_text(yaml.safe_dump(["not", "an", "object"]), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must contain a YAML object"):
                load_yaml_object(path)

    def test_write_yaml_object_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "payload.yaml"
            write_yaml_object(path, {"status": "ok"})

            self.assertEqual(load_yaml_object(path), {"status": "ok"})

    def test_write_json_object_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "payload.json"
            write_json_object(path, {"status": "ok"})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()

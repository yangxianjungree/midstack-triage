import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.support.install_common import (
    RuntimeBundleLayout,
    ensure_local_outputs_gitignore,
    load_json,
    missing_markers,
    write_json,
)


def test_runtime_bundle_layout_projects_common_dirs_with_optional_prefix():
    assert RuntimeBundleLayout().copy_dirs()[0] == ("tools/plugin", "tools/plugin")
    assert RuntimeBundleLayout("runtime").copy_dirs()[0] == ("tools/plugin", "runtime/tools/plugin")
    assert ("src", "runtime/src") in RuntimeBundleLayout("runtime").copy_dirs()


def test_json_helpers_require_object(tmp_path):
    path = tmp_path / "state.json"
    write_json(path, {"plugin_name": "midstack"})
    assert load_json(path) == {"plugin_name": "midstack"}

    path.write_text(json.dumps(["not", "object"]), encoding="utf-8")
    try:
        load_json(path)
    except ValueError as exc:
        assert "must contain a JSON object" in str(exc)
    else:
        raise AssertionError("load_json should reject non-object JSON")


def test_ensure_local_outputs_gitignore_is_idempotent(tmp_path):
    ensure_local_outputs_gitignore(tmp_path)
    ensure_local_outputs_gitignore(tmp_path)

    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert content.count(".local/") == 1
    assert "Midstack Triage local runtime outputs" in content


def test_missing_markers_reports_relative_markers(tmp_path):
    (tmp_path / "runtime" / "src").mkdir(parents=True)
    (tmp_path / "runtime" / "src" / "commands.py").write_text("", encoding="utf-8")

    assert missing_markers(tmp_path, ["runtime/src/commands.py", "runtime/domains/manifest.yaml"]) == [
        "runtime/domains/manifest.yaml"
    ]

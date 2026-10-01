import json
from pathlib import Path

import pytest
import yaml


def test_codec_rejects_implicit_yaml_and_preserves_unknown(tmp_path: Path):
    from qiming_core.codec import load_record

    path = tmp_path / "record.yaml"
    path.write_text('name: "One"\ncustom: {x: 7}\n', encoding="utf-8")
    data, raw = load_record(path, "yaml")
    assert data == {"name": "One", "custom": {"x": 7}}
    assert raw == path.read_bytes()

    for invalid in (
        "enabled: on\n",
        "date: 2026-09-27\n",
        "a: 1\na: 2\n",
        "a: &x hello\nb: *x\n",
        "a: !!python/object/apply:os.system ['true']\n",
        "a: .inf\n",
        "a: 1\n---\nb: 2\n",
    ):
        path.write_text(invalid, encoding="utf-8")
        with pytest.raises(ValueError):
            load_record(path, "yaml")


def test_mapping_handles_escaped_pointer_and_missing_value():
    from qiming_core.profile import normalize_fields

    source = {"a/b": {"~name": "draft"}, "untouched": [1, 2]}
    mapping = {
        "state": {"source": "/a~1b/~0name", "values": {"draft": "candidate"}, "writable": False},
        "owner": {"source": "/missing", "default": None, "writable": True},
        "absent": {"source": "/missing2"},
    }
    assert normalize_fields(source, mapping) == {"state": "candidate", "owner": None}
    assert source["untouched"] == [1, 2]


def test_existing_commented_yaml_is_read_only_without_preserving_codec(tmp_path: Path):
    from qiming_core.codec import can_round_trip, load_record

    path = tmp_path / "record.yaml"
    original = b"# keep my note\nname: value\n"
    path.write_bytes(original)
    assert load_record(path, "yaml")[0] == {"name": "value"}
    assert can_round_trip(path, "yaml") is False
    assert path.read_bytes() == original
    json_path = tmp_path / "record.json"
    json_path.write_text('{"name":"value","custom":3}', encoding="utf-8")
    assert can_round_trip(json_path, "json") is True


def test_runtime_yaml_dependency_is_pinned():
    lock = Path(__file__).parents[2] / "skills" / "qiming" / "scripts" / "requirements.lock"
    assert lock.read_text(encoding="utf-8").strip() == f"PyYAML=={yaml.__version__}"


def test_load_profile_resolves_manifest_and_preserves_extensions(tmp_path: Path):
    from qiming_core.profile import load_profile

    control = tmp_path / ".qiming"
    control.mkdir()
    manifest = control / "workspace.json"
    manifest.write_text(json.dumps({"protocol": "qiming.workspace/1", "profile": "profile.json"}), encoding="utf-8")
    (control / "profile.json").write_text(json.dumps({"protocol": "qiming.profile/1", "collections": {}, "mappings": {}, "extensions": {"mine": 1}}), encoding="utf-8")
    assert load_profile(manifest)["extensions"] == {"mine": 1}

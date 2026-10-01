import json
import shutil
import subprocess
import sys
from pathlib import Path


def _boot(tmp_path: Path, domain: str | None = None) -> Path:
    from qiming_core.bootstrap import bootstrap

    root = tmp_path / "work"
    root.mkdir()
    control = root / ".qiming"
    manifest = {"protocol": "qiming.workspace/1", "workspace_id": "ws_test", "state": "initializing", "profile": "profile.json", "init_journal": "init.json", "roots": {"work": {"location": "..", "access": "read-write"}}}
    profile = {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}, "retrieval": {"index_path": "index.sqlite"}}
    if domain:
        profile["collections"][domain] = {"purpose": "custom", "root": "work", "directory": domain, "pattern": "*.json", "codec": "json", "mapping": domain}
        profile["mappings"][domain] = {"id": {"source": "/id"}}
    assert bootstrap(root, control, manifest, profile, "init_1")["status"] == "ok"
    return control / "workspace.json"


def test_seed_deleted_instance_can_adapt_new_workspace(tmp_path: Path):
    from qiming_core.materialize import materialize

    manifest = _boot(tmp_path)
    seed = tmp_path / "seed"
    product_seed = Path(__file__).parents[2] / "skills" / "qiming"
    shutil.copytree(product_seed, seed, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    result = materialize(manifest, [], {"instance_id": "ins_user", "instance_version": "1.0.0"}, "init_1", _seed_dir=seed)
    assert result["status"] == "ok", result
    instance = manifest.parent / "qiming-user"
    assert (instance / "SKILL.md").exists()
    assert (instance / "references" / "recover.md").exists()
    assert (instance / "scripts" / "qiming.py").exists()
    assert json.loads(manifest.read_text())["state"] == "ready"
    shutil.rmtree(seed)
    fresh = tmp_path / "next project"
    fresh.mkdir()
    request = {"protocol": "qiming.tool/1", "request_id": "fresh", "op": "bootstrap", "args": {"root": str(fresh), "control_dir": str(fresh / ".qiming"), "manifest": {"protocol": "qiming.workspace/1", "workspace_id": "ws_next", "state": "initializing", "profile": "profile.json", "init_journal": "init.json", "roots": {"work": {"location": "..", "access": "read-write"}}}, "profile": {"protocol": "qiming.profile/1", "collections": {}, "mappings": {}}, "initialization_id": "init_next"}}
    completed = subprocess.run([sys.executable, str(instance / "scripts" / "qiming.py"), "--stdin"], input=json.dumps(request), text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert json.loads(completed.stdout)["status"] == "ok"
    assert (fresh / ".qiming" / "workspace.json").exists()


def test_materialize_retries_same_initialization_without_duplicate(tmp_path: Path):
    from qiming_core.materialize import materialize

    manifest = _boot(tmp_path)
    options = {"instance_id": "ins_user", "instance_version": "1.0.0"}
    first = materialize(manifest, [], options, "init_1")
    assert first["status"] == "ok"
    before = (manifest.parent / "qiming-user" / "SKILL.md").read_bytes()
    second = materialize(manifest, [], options, "init_1")
    assert second["status"] == "ok"
    assert second["changed"] == []
    assert (manifest.parent / "qiming-user" / "SKILL.md").read_bytes() == before


def test_materialize_retry_after_activation_interruption_keeps_instance_id(tmp_path: Path, monkeypatch):
    import qiming_core.materialize as module

    manifest = _boot(tmp_path)
    real_apply = module.apply_plan
    calls = 0

    def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            return {"status": "partial", "result": None, "diagnostics": [], "changed": []}
        return real_apply(*args, **kwargs)

    monkeypatch.setattr(module, "apply_plan", interrupted)
    first = module.materialize(manifest, [], {}, "init_1")
    assert first["status"] == "partial"
    prior_id = json.loads((manifest.parent / "qiming-user/instance.json").read_text())["instance_id"]
    monkeypatch.setattr(module, "apply_plan", real_apply)
    second = module.materialize(manifest, [], {}, "init_1")
    assert second["status"] == "ok", second
    assert json.loads(manifest.read_text())["instance"]["id"] == prior_id


def test_materialize_rejects_resource_with_changed_hash(tmp_path: Path):
    from qiming_core.materialize import materialize

    manifest = _boot(tmp_path)
    result = materialize(manifest, [{"source": "references/adapt.md", "path": "references/adapt.md", "sha256": "0" * 64, "required": True}], {"instance_id": "ins_user"}, "init_1")
    assert result["status"] == "conflict"
    assert not (manifest.parent / "qiming-user").exists()


def test_new_domain_uses_profile_without_domain_template(tmp_path: Path):
    from qiming_core.materialize import materialize

    manifest = _boot(tmp_path, "aquarium")
    result = materialize(manifest, [], {"instance_id": "ins_user"}, "init_1")
    assert result["status"] == "ok"
    assert not (manifest.parent.parent / "aquarium").exists()
    profile = json.loads((manifest.parent / "profile.json").read_text())
    assert "aquarium" in profile["collections"]


def test_materialized_entry_has_local_references_and_workspace_start(tmp_path: Path):
    import re
    from qiming_core.materialize import materialize

    manifest = _boot(tmp_path)
    result = materialize(manifest, [], {"instance_id": "ins_user"}, "init_1")
    assert result["status"] == "ok"
    instance = manifest.parent / "qiming-user"
    entry = (instance / "SKILL.md").read_text(encoding="utf-8")
    for relative in re.findall(r"\]\((references/[^)]+)\)", entry):
        assert (instance / relative).is_file(), relative
    workspace = json.loads(manifest.read_text())
    assert (manifest.parent / workspace["workspace_entry"]).is_file()
    assert (manifest.parent / workspace["conventions"]).is_file()

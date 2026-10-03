"""Preview and inspect discoverability bindings; authority stays user-owned."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .codec import load_record
from .discovery import project_root
from .startup import ensure_startup, startup_status
from .validate import _control_path, validate

_HOST_DIRS = {"codex": ".agents", "claude": ".claude", "gemini": ".gemini", "cursor": ".cursor", "opencode": ".opencode"}
_INSTRUCTION_FILES = {"codex": "AGENTS.md", "claude": "CLAUDE.md", "gemini": "GEMINI.md", "cursor": "AGENTS.md", "opencode": "AGENTS.md"}


def ensure_project_entrypoints(manifest_path: Path) -> dict[str, object]:
    """Create or safely refresh the owning project's startup instructions."""
    return ensure_startup(manifest_path)


def binding_preview(manifest_path: Path, host: str, host_root: Path) -> dict[str, object]:
    if host not in _HOST_DIRS:
        raise ValueError("unsupported host name")
    manifest_path = manifest_path.resolve()
    manifest, _ = load_record(manifest_path, "json")
    if host_root.resolve() != project_root(manifest_path, manifest):
        return {"status": "conflict", "reason": "outside-project", "source_path": None, "binding_path": None}
    if manifest.get("state") != "ready" or not isinstance(manifest.get("instance"), dict):
        return {"status": "partial", "source_path": None, "binding_path": None, "reason": "user-instance-not-ready"}
    check = validate(manifest_path, [], False)
    if check["status"] not in {"ok", "ok_with_warnings"}:
        return {"status": "conflict", "source_path": None, "binding_path": None, "reason": "instance-validation-failed", "diagnostics": check["diagnostics"]}
    source = (manifest_path.parent / str(manifest["instance"]["entry"])).resolve()
    instance_manifest = (manifest_path.parent / str(manifest["instance"]["manifest"])).resolve()
    binding = host_root.resolve() / _HOST_DIRS[host] / "skills" / source.parent.name
    return {"status": "ok", "host": host, "workspace_manifest": str(manifest_path), "instance_id": manifest["instance"]["id"], "source_path": str(source), "source_directory": str(source.parent), "binding_path": str(binding), "instruction_path": str(host_root.resolve() / _INSTRUCTION_FILES[host]), "source_fingerprint": hashlib.sha256(instance_manifest.read_bytes()).hexdigest(), "validation_diagnostics": check["diagnostics"], "method": "symlink-or-copy", "note": "Binding contains only discoverability; keep authority in the user instance"}


def binding_status(manifest_path: Path, host: str) -> dict[str, object]:
    manifest_path = manifest_path.resolve()
    workspace_root = project_root(manifest_path)
    preview = binding_preview(manifest_path, host, workspace_root)
    instruction = workspace_root / "AGENTS.md"
    preview["instruction_bytes"] = instruction.stat().st_size if instruction.is_file() else 0
    if preview["status"] != "ok":
        return preview
    binding = Path(preview["binding_path"])
    startup = startup_status(manifest_path, host, _INSTRUCTION_FILES[host])
    if startup['status']=='manual-entry':
        return {**startup,'binding_path':str(binding),'instance_id':preview['instance_id']}
    if not binding.exists():
        return {"status": "not-bound", "binding_path": str(binding), "instance_id": preview["instance_id"]}
    check = startup_status(manifest_path.resolve(), host, _INSTRUCTION_FILES[host])
    if check["status"] not in {"ok", "ok_with_warnings"}:
        return {**check, "binding_path": str(binding), "instruction_path": preview["instruction_path"], "instance_id": preview["instance_id"]}
    if binding.resolve() == Path(preview["source_directory"]):
        return {"status": "bound", "instruction_bytes": preview["instruction_bytes"], "method": "symlink", "binding_path": str(binding), "instance_id": preview["instance_id"], "source_fingerprint": preview["source_fingerprint"], "validation_diagnostics": preview["validation_diagnostics"]}
    copy_manifest = binding / "instance.json"
    if not copy_manifest.is_symlink() and copy_manifest.is_file() and hashlib.sha256(copy_manifest.read_bytes()).hexdigest() == preview["source_fingerprint"]:
        try:
            instance, _ = load_record(copy_manifest, "json")
            for resource in instance["resources"]:
                path = _control_path(binding, resource["path"])
                if not path.is_file() or path.read_bytes() != _control_path(Path(preview["source_directory"]), resource["path"]).read_bytes():
                    raise ValueError("Copied resource differs from its authority")
            return {"status": "bound-copy", "instruction_bytes": preview["instruction_bytes"], "method": "copy", "binding_path": str(binding), "instance_id": preview["instance_id"], "source_fingerprint": preview["source_fingerprint"], "validation_diagnostics": preview["validation_diagnostics"]}
        except (OSError, ValueError, KeyError):
            pass
    return {"status": "stale-or-conflicting", "binding_path": str(binding), "instance_id": preview["instance_id"]}


def selected_hosts(root: Path, hosts: str) -> list[str]:
    if hosts == 'auto':
        return ['codex'] + [host for host, directory in _HOST_DIRS.items() if host != 'codex' and (root / directory).is_dir()]
    selected = list(dict.fromkeys(hosts.split(',')))
    if not selected or any(host not in _HOST_DIRS for host in selected):
        raise ValueError('hosts must be auto or a comma-separated list of codex,claude,gemini,cursor,opencode')
    return selected


def bind(manifest_path: Path, host: str) -> dict:
    import os
    import shutil
    manifest_path=manifest_path.resolve()
    root=project_root(manifest_path)
    preview=binding_preview(manifest_path,host,root)
    if preview['status'] != 'ok':
        return {'status':preview['status'],'result':preview,'changed':[]}
    target=Path(preview['binding_path'])
    current=binding_status(manifest_path,host)
    if current['status']=='manual-entry':
        return {'status':'ok','result':{**current,'host':host,'method':'manual'},'changed':[]}
    if current['status'] in {'bound','bound-copy'}:
        return {'status':'ok','result':{**current,'host':host,'method':'copy' if current['status']=='bound-copy' else 'symlink'},'changed':[]}
    if target.exists() or target.is_symlink():
        return {'status':'conflict','result':current,'diagnostics':[{'code':'BINDING_CONFLICT','message':'Existing binding differs; preserve it and compare with the project instance.','hint':'Do not overwrite local changes. Remove an obsolete binding only after review.'}],'changed':[]}
    for parent in target.parents:
        if parent==root: break
        if parent.is_symlink(): raise ValueError('Binding parent is a symlink')
    target.parent.mkdir(parents=True,exist_ok=True)
    method='symlink'
    try:
        target.symlink_to(os.path.relpath(preview['source_directory'],target.parent),target_is_directory=True)
    except OSError:
        method='copy'
        shutil.copytree(preview['source_directory'],target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    return {'status':'ok','result':{**binding_status(manifest_path,host),'host':host,'method':method},'changed':[{'path':str(target),'action':'bound-'+method}]}

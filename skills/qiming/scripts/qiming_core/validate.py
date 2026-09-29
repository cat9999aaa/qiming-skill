"""Validate current bytes and structure without claiming runtime behavior."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .codec import load_record
from .profile import load_profile
from .scan import _relative_path, _root
from .members import member_view, validate_relation_graph
from .secrets import validate_account_ref


def _diag(code: str, message: str, locator: str | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "locator": locator, "retryable": False, "details": {}}


def _control_path(base: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not (base / path).resolve().is_relative_to(base.resolve()):
        raise ValueError("instance resource path escapes control directory")
    return base / path


def validate(manifest_path: Path, targets: list[dict[str, object]], include_references: bool) -> dict[str, object]:
    diagnostics: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    reference_coverage: dict[str, object] | None = None
    try:
        manifest, _ = load_record(manifest_path, "json")
        if manifest.get("protocol") != "qiming.workspace/1":
            diagnostics.append(_diag("UNSUPPORTED_PROTOCOL", "Workspace manifest protocol is unsupported", str(manifest_path)))
        load_profile(manifest_path)
        if manifest.get("state") == "ready":
            for field in ("workspace_entry", "conventions"):
                relative = manifest.get(field)
                if not isinstance(relative, str) or not _control_path(manifest_path.parent, relative).is_file():
                    diagnostics.append(_diag("BROKEN_ENTRY", f"Missing workspace {field}", str(relative)))
            instance = manifest.get("instance")
            if not isinstance(instance, dict):
                diagnostics.append(_diag("BROKEN_ENTRY", "Ready workspace lacks instance"))
            else:
                instance_path = _control_path(manifest_path.parent, str(instance.get("manifest", "")))
                entry_path = _control_path(manifest_path.parent, str(instance.get("entry", "")))
                if not entry_path.is_file():
                    diagnostics.append(_diag("BROKEN_ENTRY", f"Missing instance entry: {entry_path}", str(entry_path)))
                if not instance_path.is_file():
                    diagnostics.append(_diag("BROKEN_ENTRY", f"Missing instance manifest: {instance_path}", str(instance_path)))
                else:
                    instance_doc, _ = load_record(instance_path, "json")
                    if instance_doc.get("protocol") != "qiming.instance/1" or instance_doc.get("instance_id") != instance.get("id"):
                        diagnostics.append(_diag("BROKEN_ENTRY", "Instance identity mismatch", str(instance_path)))
                    for resource in instance_doc.get("resources", []):
                        if not isinstance(resource, dict) or not resource.get("required"):
                            continue
                        path = _control_path(instance_path.parent, str(resource.get("path", "")))
                        if not path.is_file():
                            diagnostics.append(_diag("BROKEN_ENTRY", f"Missing required resource: {resource.get('path')}", str(path)))
                        elif hashlib.sha256(path.read_bytes()).hexdigest() != resource.get("sha256"):
                            diagnostics.append(_diag("BROKEN_ENTRY", f"Resource fingerprint mismatch: {resource.get('path')}", str(path)))
    except (OSError, ValueError) as exc:
        diagnostics.append(_diag("SCHEMA_INVALID", str(exc), str(manifest_path)))
    for target in targets:
        try:
            root = _root(manifest_path, str(target["root"]))
            path = _relative_path(root, str(target["path"]))
            if path.is_symlink():
                raise ValueError("record path is a symlink")
            data, raw = load_record(path, str(target.get("codec", "json")))
            sha = hashlib.sha256(raw).hexdigest()
            verification = data.get("verification", [])
            current = isinstance(verification, list) and any(isinstance(item, dict) and item.get("result") == "pass" and item.get("subject_fingerprint") == sha for item in verification)
            records.append({"locator": {"kind": "file", "root": target["root"], "path": target["path"]}, "structural_valid": True, "record_fingerprint": sha, "current_verification": current})
            if data.get("type") == "account":
                diagnostics.extend(validate_account_ref(data))
            if target.get("collection"):
                member = member_view(manifest_path, target)
                if not isinstance(member.get("name"), str) or not member["name"]:
                    diagnostics.append(_diag("SCHEMA_INVALID", "Member name is missing", str(path)))
        except (OSError, ValueError, KeyError) as exc:
            diagnostics.append(_diag("SCHEMA_INVALID", str(exc), str(target)))
    if include_references:
        try:
            from .index import authority_records

            members, reference_coverage = authority_records(manifest_path, [], limit=None)
            seen: dict[tuple[str, str], dict[str, object]] = {}
            for member in members:
                key = (str(member["ref"]["workspace_id"]), str(member["ref"]["id"]))
                if key in seen:
                    diagnostics.append(_diag("DUPLICATE_ID", f"Member ID has more than one authority record: {key[1]}", str(member["record_locator"])))
                else:
                    seen[key] = member
            for issue in validate_relation_graph(list(seen.values())):
                diagnostics.append(_diag(str(issue["code"]), str(issue["message"]), str(issue.get("source"))))
            if reference_coverage["truncated"] or reference_coverage["errors"]:
                diagnostics.append(_diag("COVERAGE_INCOMPLETE", "Reference validation did not inspect every authority record", str(reference_coverage["errors"])))
        except (OSError, ValueError, KeyError, RecursionError) as exc:
            diagnostics.append(_diag("COVERAGE_INCOMPLETE", str(exc), str(manifest_path)))
    return {"status": "error" if diagnostics else "ok", "result": {"records": records, "include_references": include_references, "reference_coverage": reference_coverage}, "diagnostics": diagnostics, "changed": []}

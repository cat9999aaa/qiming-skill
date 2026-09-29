"""Copy selected seed resources into a verifiable, user-owned Skill."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path

from .codec import load_record
from .host_binding import ensure_project_entrypoints
from .plan import plan_changes
from .transactions import apply_plan
from .validate import validate


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: dict[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _conflict(code: str, message: str, locator: str | None = None) -> dict[str, object]:
    return {"status": "conflict", "result": None, "diagnostics": [{"code": code, "message": message, "locator": locator, "retryable": False, "details": {}}], "changed": []}


def _entry(name: str, workspace_id: str) -> bytes:
    return f"""---
name: {name}
description: Use for work and 会员 management inside the project owning this local Qiming instance ({workspace_id}), including its ordinary development, writing, operations and retained tools. Other projects use their own instance.
---

# 本项目的启明实例

本实例只服务工作区 `{workspace_id}`。从本项目启动指令确定权威清单位置（默认是项目根的 `.qiming/workspace.json`），核对工作区 ID 和当前任务的项目根，必要时用 `scope_check`。宿主中的 Skill 可以是副本，不能从副本位置推断权威清单；工具请求中的 `workspace_manifest` 始终指向项目原清单。不同项目或独立子项目不能沿用本实例。授权管理目录外的资源不改变启用范围。

“会员”是用户创建或明确接管、持续维护的独立对象，不是付费订阅。先查已有归属；独立保留复用的能力入会，内部产物归父会员，临时输出留作证据，调用第三方工具记外部依赖。会员与衍生脚本、Skill、程序、MCP 的判断见[会员](references/members.md)。

每次新会话开始实际工作前，读取清单指定的短入口、本地约定及当前任务，按本地 profile 定位记录；用户无需再次提及启明。日常工作与收尾按[管理](references/manage.md)，经验沉淀按[知识](references/knowledge.md)，规则变化按[演化](references/evolve.md)，故障与换机按[恢复](references/recover.md)。领域问题见[领域](references/domains.md)，工具接口见[工具](references/tools.md)。用户明确要求另一个项目接入时可用自带[适配](references/adapt.md)，在新项目生成独立实例后再接续。

本实例的工具入口是 `scripts/qiming.py`，使用 JSON 请求协议 `qiming.tool/1`。长期产物必须能从所属会员和工作记录找到；实际验证与未知状态分别保留。项目启动摘要变更后运行 `refresh_context`，将关键规则带入下次会话。账户卡只保存凭据 provider 引用。用户实例和权威资料属于用户；操作无需原始种子目录。
""".encode("utf-8")


def _default_resources(seed: Path) -> list[dict[str, object]]:
    included: list[Path] = []
    for pattern in ("references/*.md", "scripts/*.py", "scripts/requirements.lock", "scripts/qiming_core/*.py", "assets/contracts/*.json"):
        included.extend(seed.glob(pattern))
    result = []
    for path in sorted(set(included)):
        if path.is_file():
            relative = str(path.relative_to(seed))
            result.append({"source": relative, "path": relative, "sha256": _sha(path.read_bytes()), "required": True, "purpose": "runtime" if relative.startswith("scripts/") else "method-or-contract", "license": "source-package"})
    return result


def _root_alias(manifest_path: Path, manifest: dict[str, object]) -> tuple[str, Path] | None:
    for alias, config in manifest.get("roots", {}).items():
        if config.get("access") != "read-write":
            continue
        root = (manifest_path.parent / str(config.get("location", ""))).resolve()
        if manifest_path.parent.resolve().is_relative_to(root):
            return alias, root
    return None


def _staged_plan(manifest_path: Path, alias: str, root: Path, payloads: list[tuple[Path, bytes]], stage: Path, label: str) -> dict[str, object]:
    changes = []
    stage.mkdir(parents=True, exist_ok=True)
    for target, data in payloads:
        staging = stage / f"{label}-{_sha(str(target).encode('utf-8'))}"
        if staging.exists() and staging.read_bytes() != data:
            return _conflict("WRITE_CONFLICT", "Staged materialization bytes changed", str(staging))
        if not staging.exists():
            staging.write_bytes(data)
        current = _sha(target.read_bytes()) if target.exists() else None
        if current == _sha(data):
            continue
        if current is not None:
            return _conflict("WRITE_CONFLICT", "Existing instance resource differs", str(target))
        changes.append({"action": "create", "target": {"kind": "file", "root": alias, "path": str(target.relative_to(root))}, "expected_sha256": None, "content_ref": str(staging.relative_to(manifest_path.parent)), "desired_sha256": _sha(data)})
    if not changes:
        return {"status": "ok", "result": {"skipped": True}, "diagnostics": [], "changed": []}
    manifest, _ = load_record(manifest_path, "json")
    profile_sha = _sha((manifest_path.parent / str(manifest["profile"])).read_bytes())
    planned = plan_changes(manifest_path, changes, "materialize-user-instance", profile_sha)
    if planned["status"] != "ok":
        return planned
    return apply_plan(manifest_path, planned["result"])


def materialize(manifest_path: Path, resource_plan: list[dict[str, object]], instance_manifest: dict[str, object], initialization_id: str, *, _seed_dir: Path | None = None) -> dict[str, object]:
    manifest_path = manifest_path.resolve()
    manifest, raw = load_record(manifest_path, "json")
    if manifest.get("state") == "ready":
        if instance_manifest.get("instance_id") and instance_manifest["instance_id"] != manifest.get("instance", {}).get("id"):
            return _conflict("WRITE_CONFLICT", "Existing instance ID differs")
        check = validate(manifest_path, [], False)
        if check["status"] != "ok":
            return _conflict("BROKEN_ENTRY", "Ready instance failed validation")
        connected = ensure_project_entrypoints(manifest_path)
        if connected["status"] != "ok":
            return connected
        return {"status": "ok", "result": {"instance_entry": str(manifest_path.parent / manifest["instance"]["entry"]), "already_materialized": True, "project_entrypoints": connected["result"]["entrypoints"]}, "diagnostics": [], "changed": connected["changed"]}
    if manifest.get("state") != "initializing":
        return _conflict("RECOVERY_REQUIRED", "Workspace is not initializing")
    journal_path = manifest_path.parent / str(manifest.get("init_journal", "init.json"))
    if not journal_path.is_file():
        return _conflict("BROKEN_ENTRY", "Initialization journal missing", str(journal_path))
    journal, _ = load_record(journal_path, "json")
    if journal.get("initialization_id") != initialization_id:
        return _conflict("WRITE_CONFLICT", "Initialization ID differs from existing workspace", str(journal_path))
    root_binding = _root_alias(manifest_path, manifest)
    if root_binding is None:
        return _conflict("CAPABILITY_MISSING", "No writable root contains the control directory")
    alias, root = root_binding
    seed = (_seed_dir or Path(__file__).parents[2]).resolve()
    defaults = {item["path"]: item for item in _default_resources(seed)}
    for item in resource_plan:
        defaults[str(item.get("path", ""))] = item
    resource_plan = list(defaults.values())
    instance_id = instance_manifest.get("instance_id") or f"ins_{uuid.uuid5(uuid.NAMESPACE_URL, str(manifest['workspace_id']) + ':' + initialization_id)}"
    if not isinstance(instance_id, str) or not instance_id:
        return _conflict("INVALID_INPUT", "Instance ID is invalid")
    instance_dir = manifest_path.parent / "qiming-user"
    entry_bytes = _entry(instance_dir.name, str(manifest["workspace_id"]))
    resources: list[dict[str, object]] = [{"path": "SKILL.md", "purpose": "entry", "required": True, "sha256": _sha(entry_bytes), "origin": "generated-for-workspace"}]
    payloads: list[tuple[Path, bytes]] = [(instance_dir / "SKILL.md", entry_bytes)]
    local_policy = b"policy:\n  allow_implicit_invocation: true\n"
    payloads.append((instance_dir / "agents/openai.yaml", local_policy))
    resources.append({"path": "agents/openai.yaml", "purpose": "project-invocation", "required": True, "sha256": _sha(local_policy), "origin": "generated-for-workspace"})
    workspace_entry = str(manifest.get("workspace_entry", "START.md"))
    conventions_entry = str(manifest.get("conventions", "conventions.md"))
    for relative in (workspace_entry, conventions_entry):
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not (manifest_path.parent / path).resolve().is_relative_to(manifest_path.parent):
            return _conflict("PATH_ESCAPE", "Workspace entry path escapes control directory")
    start_path = manifest_path.parent / workspace_entry
    if not start_path.exists():
        payloads.append((start_path, f"# 当前工作区\n\n工作区 ID：{manifest['workspace_id']}。当前目标与下一步由正在执行的工作记录维护；尚未提供时保持未知。\n\n用户实例：[SKILL.md](qiming-user/SKILL.md)。本地结构：[profile.json](profile.json)。\n".encode("utf-8")))
    conventions_path = manifest_path.parent / conventions_entry
    if not conventions_path.exists():
        payloads.append((conventions_path, "# 本地约定\n\n此文件记录经用户确认或实际工作验证的稳定偏好。初始结构由 profile.json 解释；未有证据的领域词汇、分类和状态保持待定。修改范围、原因与验证应留在工作或演化记录。\n".encode("utf-8")))
    for item in resource_plan:
        relative_source = Path(str(item.get("source", "")))
        relative_target = Path(str(item.get("path", "")))
        if relative_source.is_absolute() or relative_target.is_absolute() or ".." in relative_source.parts or ".." in relative_target.parts or not relative_source.parts or not relative_target.parts or relative_target == Path("SKILL.md"):
            return _conflict("PATH_ESCAPE", "Resource source or target path is unsafe")
        source = (seed / relative_source).resolve()
        if not source.is_relative_to(seed) or not source.is_file():
            return _conflict("BROKEN_ENTRY", "Seed resource is missing", str(relative_source))
        data = source.read_bytes()
        if _sha(data) != item.get("sha256"):
            return _conflict("STALE_SOURCE", "Seed resource fingerprint changed", str(relative_source))
        path = instance_dir / relative_target
        if not path.resolve(strict=False).is_relative_to(instance_dir):
            return _conflict("PATH_ESCAPE", "Resource target escapes instance")
        payloads.append((path, data))
        resources.append({"path": str(relative_target), "purpose": item.get("purpose", "runtime"), "required": bool(item.get("required", True)), "sha256": _sha(data), "origin": {"source": str(relative_source), "license": item.get("license")}})
    if len({str(path) for path, _ in payloads}) != len(payloads):
        return _conflict("WRITE_CONFLICT", "Duplicate instance resource target")
    dependency = [{"name": "Python", "minimum": "3.11", "verification": "python3 --version"}, {"name": "PyYAML", "version": "6.0.3", "optional_for": ["yaml", "markdown-frontmatter"], "verification": "python3 -c 'import yaml; print(yaml.__version__)'"}]
    instance_doc = {"protocol": "qiming.instance/1", "instance_id": instance_id, "instance_version": instance_manifest.get("instance_version", "1.0.0"), "workspace_manifest": "../workspace.json", "resources": resources, "dependencies": instance_manifest.get("dependencies", dependency), "seed_origin": instance_manifest.get("seed_origin", {"name": "qiming", "version": "1"})}
    payloads.append((instance_dir / "instance.json", _json(instance_doc)))
    stage = manifest_path.parent / ".materialize" / re.sub(r"[^A-Za-z0-9_-]", "_", initialization_id)
    first = _staged_plan(manifest_path, alias, root, payloads, stage, "resource")
    if first["status"] != "ok":
        return first
    ready = dict(manifest)
    ready["state"] = "ready"
    ready["instance"] = {"id": instance_id, "entry": "qiming-user/SKILL.md", "manifest": "qiming-user/instance.json"}
    ready.setdefault("workspace_entry", workspace_entry)
    ready.setdefault("conventions", conventions_entry)
    prospective = _json(ready)
    ready_stage = stage / "ready-workspace.json"
    ready_stage.write_bytes(prospective)
    profile_sha = _sha((manifest_path.parent / str(manifest["profile"])).read_bytes())
    change = {"action": "replace", "target": {"kind": "file", "root": alias, "path": str(manifest_path.relative_to(root))}, "expected_sha256": _sha(manifest_path.read_bytes()), "content_ref": str(ready_stage.relative_to(manifest_path.parent)), "desired_sha256": _sha(prospective)}
    planned = plan_changes(manifest_path, [change], "activate-user-instance", profile_sha)
    if planned["status"] != "ok":
        return planned
    activated = apply_plan(manifest_path, planned["result"])
    if activated["status"] != "ok":
        return activated
    check = validate(manifest_path, [], False)
    if check["status"] != "ok":
        return {"status": "partial", "result": {"instance_entry": str(instance_dir / "SKILL.md"), "validation": check}, "diagnostics": check["diagnostics"], "changed": first["changed"] + activated["changed"]}
    journal["stage"] = "active"
    journal["completed"] = ["bootstrap", "materialize", "validate", "activate"]
    journal_path.write_bytes(_json(journal))
    shutil.rmtree(stage, ignore_errors=True)
    connected = ensure_project_entrypoints(manifest_path)
    if connected["status"] != "ok":
        return {"status": "partial", "result": {"instance_entry": str(instance_dir / "SKILL.md"), "instance_manifest": str(instance_dir / "instance.json"), "host_entry_result": connected}, "diagnostics": connected["diagnostics"], "changed": first["changed"] + activated["changed"] + connected["changed"]}
    return {"status": "ok", "result": {"instance_entry": str(instance_dir / "SKILL.md"), "instance_manifest": str(instance_dir / "instance.json"), "validation": check, "project_entrypoints": connected["result"]["entrypoints"]}, "diagnostics": [], "changed": first["changed"] + activated["changed"] + connected["changed"]}

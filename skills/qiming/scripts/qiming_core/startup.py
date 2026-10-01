"""Render project-owned startup context and refresh only known generated regions."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from .codec import load_record
from .discovery import project_root
from .plan import plan_changes
from .transactions import apply_plan
from .validate import _control_path


START = "<!-- qiming:entry:start -->"
END = "<!-- qiming:entry:end -->"
STATE = "project-entrypoints.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _regular(path: Path) -> bytes | None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"Expected a regular local file: {path}")
    return path.read_bytes() if path.exists() else None


def _region(text: str) -> tuple[int, int] | None:
    if START not in text and END not in text:
        return None
    if text.count(START) != 1 or text.count(END) != 1 or text.index(START) > text.index(END):
        raise ValueError("Project instructions have incomplete Qiming markers")
    return text.index(START), text.index(END) + len(END)


def _inputs(manifest_path: Path) -> tuple[dict, Path, bytes, dict[str, str]]:
    manifest, _ = load_record(manifest_path, "json")
    if manifest.get("state") != "ready":
        raise ValueError("User instance is not ready")
    control = manifest_path.parent
    root = project_root(manifest_path, manifest)
    source = _control_path(control, str(manifest.get("startup_context", "startup.md")))
    raw = _regular(source)
    if raw is None:
        name = root.name.replace("\n", " ").replace("\r", " ")
        raw = f"项目：{name}。职责、关键偏好和长期约束从本项目实际资料确认后写在这里；当前目标与进展见短入口。\n".encode()
    local = raw.decode("utf-8").replace("\r\n", "\n")
    if START in local or END in local:
        raise ValueError("Startup source cannot contain generated-region markers")
    # Leave space for the governing rules and other project instructions.
    if len(raw) > 12000:
        raise ValueError("Startup summary exceeds 12000 bytes; keep detail in linked local records")
    relative = lambda p: (control.relative_to(root) / str(p)).as_posix()
    short = relative(manifest.get("workspace_entry", "START.md"))
    conventions = relative(manifest.get("conventions", "conventions.md"))
    skill = relative(manifest["instance"]["entry"])
    for item in (manifest.get("workspace_entry", "START.md"), manifest.get("conventions", "conventions.md"), manifest["instance"]["entry"]):
        _control_path(control, str(item))
    block = f"""{START}
## 本项目的启明管理规则

工作区身份：`{manifest['workspace_id']}`。项目根是本文件所在目录，下列路径都从项目根解析。权威清单为 `{relative(manifest_path.name)}`；调用工具时使用这份清单，不从宿主 Skill 副本的位置推断。

- 启明只在本项目及其所属子目录内运行。独立子项目、其他项目和未接入目录有各自范围；更换工作目录先核对实例，不能沿用上一项目的身份。授权管理系统软件或外部资源不等于在那些目录启用启明。
- 每次新会话开始实际工作前，先读 `{short}`、`{conventions}` 和 `{skill}`，恢复当前任务；即使用户没有提到“启明”也如此。细节只读目标会员、父会员链、直接依赖和相关知识。普通问答无需建立任务或扫描全库。
- “会员”是用户创建或明确接管、需要持续维护的独立对象，不是付费订阅。先查已有归属。保留复用且有独立用途、入口或维护周期的脚本、Skill、程序、MCP、流程和模板登记为会员或子会员；内部辅助文件归现有会员，临时命令/缓存/输出归任务证据，单纯调用的第三方能力记外部依赖。
- 会员可以包含会员。产物记录归属和来源任务；适合独立维护时提升为子会员，跨会员复用仍只有一份权威档案。需要维护的本项目管理工具也遵守同样规则。详细判断见本实例的 `references/members.md`。
- 有持续成果的工作收尾时，检查产物归属、是否产生新会员、实际验证、值得留下的知识和下一步；更新相关档案及短入口。重复或易错方法按需要固化为可执行工具，不能仅把结果留在聊天里。按需形成目录，沿用用户已有结构。
- 登记、完成与验证分别记录；未运行的检查保持未验证。账户卡只保存凭据引用。权威管理记录使用本实例的受控写入工具，用户原件与本地规则优先。

### 本项目关键上下文

来源：`{source.relative_to(root).as_posix()}`。在来源文件维护此摘要，再运行本实例的 `refresh_context` 刷新本区块；本区块之外的项目指令原样保留。

{local.rstrip()}
{END}"""
    return manifest, source, raw, {"AGENTS.md": block, "CLAUDE.md": f"{START}\n@AGENTS.md\n{END}", "GEMINI.md": f"{START}\n@./AGENTS.md\n{END}"}


def _legacy_blocks(control: str) -> dict[str, str]:
    return {
        "AGENTS.md": f"""{START}
## 启明工作区入口

这里的“会员”指已接管并持续维护的项目、工具、账户等对象，不是付费订阅。遇到入会、项目或系统管理、工作接续、知识沉淀、恢复等请求，先读 `{control}/workspace.json` 和 `{control}/START.md`，再按任务需要读 `{control}/qiming-user/SKILL.md`、本地约定和目标记录。工作中形成并保留独立脚本、Skill、MCP 或自动化时，按本地规则登记其身份与验证状态。保留本文件原有规则；普通小任务无需加载全库。
{END}""",
        "CLAUDE.md": f"{START}\n@AGENTS.md\n{END}",
        "GEMINI.md": f"{START}\n@./AGENTS.md\n{END}",
    }


def _state(control: Path, workspace_id: str) -> dict:
    data = _regular(control / STATE)
    if data is None:
        return {}
    state = json.loads(data)
    if not isinstance(state, dict) or state.get("workspace_id") != workspace_id or not isinstance(state.get("blocks"), dict):
        raise ValueError("Project instruction ownership record is invalid")
    return state


def ensure_startup(manifest_path: Path) -> dict[str, object]:
    manifest_path = manifest_path.resolve()
    try:
        manifest, source, raw, blocks = _inputs(manifest_path)
        control, root = manifest_path.parent, project_root(manifest_path, manifest)
        old_state = _state(control, manifest["workspace_id"])
        payloads: list[tuple[Path, bytes, bytes | None]] = []
        if not source.exists():
            payloads.append((source, raw, None))
        legacy = _legacy_blocks(control.relative_to(root).as_posix())
        for name, block in blocks.items():
            path = root / name
            original = _regular(path)
            existing = (original or b"").decode("utf-8")
            region = _region(existing)
            if region:
                before = existing[region[0]:region[1]].replace("\r\n", "\n")
                saved = old_state.get("blocks", {}).get(name)
                if before != block and _sha(before.encode()) != saved and before != legacy[name]:
                    raise ValueError(f"Generated instructions were locally edited: {path}; preserve and reconcile them")
                desired = existing[:region[0]] + block + existing[region[1]:]
            else:
                desired = existing + ("\n\n" if existing else "") + block + "\n"
            if original != desired.encode():
                payloads.append((path, desired.encode(), original))
        state = {"protocol": "qiming.project-entrypoints/1", "workspace_id": manifest["workspace_id"], "source": str(source.relative_to(control)), "source_sha256": _sha(raw), "blocks": {name: _sha(block.encode()) for name, block in blocks.items()}}
        previous = _regular(control / STATE)
        if previous != _json(state):
            payloads.append((control / STATE, _json(state), previous))
        roots = []
        for alias, config in manifest.get("roots", {}).items():
            if isinstance(config, dict) and config.get("access") == "read-write":
                location = (control / str(config.get("location", ""))).resolve()
                if root.is_relative_to(location):
                    roots.append((len(location.parts), alias, location))
        if not roots:
            raise ValueError("Project instruction root is not writable")
        _, alias, registered_root = max(roots)
    except (OSError, ValueError, KeyError, UnicodeError) as error:
        return {"status": "conflict", "result": None, "diagnostics": [{"code": "WRITE_CONFLICT", "message": str(error), "locator": str(manifest_path)}], "changed": []}
    warnings = ([{'code':'STARTUP_BUDGET','message':'Startup summary exceeds the 3000-byte soft budget','hint':'Keep decisions and 3–5 current task links; move details into referenced records.'}] if len(raw)>3000 else [])
    if not payloads:
        return {"status": "ok_with_warnings" if warnings else "ok", "result": {"entrypoints": sorted(blocks)}, "diagnostics": warnings, "changed": []}
    stage = control / ".host-entry-staging" / str(uuid.uuid4())
    stage.mkdir(parents=True, exist_ok=True)
    changes = []
    for path, data, previous in payloads:
        staged = stage / (_sha(data) + ".stage")
        staged.write_bytes(data)
        changes.append({"action": "create" if previous is None else "replace", "target": {"kind": "file", "root": alias, "path": str(path.relative_to(registered_root))}, "expected_sha256": None if previous is None else _sha(previous), "content_ref": str(staged.relative_to(control)), "desired_sha256": _sha(data)})
    profile = _control_path(control, str(manifest["profile"]))
    planned = plan_changes(manifest_path, changes, "refresh-project-startup", _sha(profile.read_bytes()))
    if planned["status"] != "ok":
        return planned
    applied = apply_plan(manifest_path, planned["result"])
    if applied["status"] == "ok":
        applied["result"]["entrypoints"] = sorted(blocks)
        if warnings:
            applied["status"] = "ok_with_warnings"
            applied["diagnostics"] = warnings
    from .staging import finish_stage
    return finish_stage(stage, applied)


def startup_status(manifest_path: Path, host: str, instruction_name: str) -> dict:
    try:
        manifest, source, raw, blocks = _inputs(manifest_path)
        root = project_root(manifest_path, manifest)
        override = root / "AGENTS.override.md"
        if host == "codex" and override.exists() and override.stat().st_size:
            return {"status": "incomplete", "reason": "project-instruction-shadowed", "locator": str(override)}
        state = _state(manifest_path.parent, manifest["workspace_id"])
        for name in {"AGENTS.md", instruction_name}:
            data = _regular(root / name)
            region = _region(data.decode()) if data is not None else None
            if region is None:
                return {"status": "incomplete", "reason": "project-instruction-missing"}
            current = data.decode()[region[0]:region[1]].replace("\r\n", "\n")
            if _sha(current.encode()) != state.get("blocks", {}).get(name):
                return {"status": "incomplete", "reason": "project-instruction-edited-or-untracked"}
            if current != blocks[name]:
                return {"status": "stale-context", "reason": "startup-context-changed"}
        if not source.is_file() or state.get("source_sha256") != _sha(raw):
            return {"status": "stale-context", "reason": "startup-context-changed"}
        return {"status": "ok"}
    except (OSError, ValueError, KeyError, UnicodeError) as error:
        return {"status": "incomplete", "reason": "invalid-startup-context", "detail": str(error)}

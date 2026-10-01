#!/usr/bin/env python3
"""Read a Qiming JSON request and print exactly one JSON response."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid

from qiming_core.protocol import dispatch, response, register
from qiming_core.discovery import discover, scope_check
from qiming_core.bootstrap import bootstrap
from qiming_core.scan import scan
from qiming_core.validate import validate
from qiming_core.plan import plan_changes
from qiming_core.transactions import apply_plan, reconcile
from qiming_core.index import reindex
from qiming_core.search import search
from qiming_core.materialize import materialize
from qiming_core.evolution import plan_profile_migration
from qiming_core.bundle import bundle
from qiming_core.restore import inspect_bundle, restore_preview, apply_restore, restore_record
from qiming_core.capabilities import capability_report
from qiming_core.host_binding import binding_preview, binding_status, ensure_project_entrypoints
from qiming_core.deletion import deletion_preview, apply_deletion
from qiming_core.retirement import record_redirect
from qiming_core.quick_log import log_event


EXIT_CODES = {"ok": 0, "ok_with_warnings": 0, "error": 2, "conflict": 3, "partial": 4}


def _inspect(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    result = discover(Path(args["start_dir"]), Path(args["explicit_manifest"]) if args.get("explicit_manifest") else None, Path(args["boundary"]) if args.get("boundary") else None)
    return {"status": result["status"] if result["status"] != "none" else "ok", "result": result, "diagnostics": result["diagnostics"], "changed": []}


def _bootstrap(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return bootstrap(Path(args["root"]), Path(args["control_dir"]), args["manifest"], args["profile"], args["initialization_id"])


register("inspect", _inspect)
register("bootstrap", _bootstrap)


def _scan(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    result = scan(Path(request["workspace_manifest"]), args.get("roots", []), args.get("relative_paths", []), args.get("budget", {}))
    return {"status": result["status"], "result": result, "diagnostics": [], "changed": []}


def _validate(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return validate(Path(request["workspace_manifest"]), args.get("targets", []), bool(args.get("include_references", False)))


register("scan", _scan)
register("validate", _validate)


def _plan(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return plan_changes(Path(request["workspace_manifest"]), args["changes"], args["intent_ref"], args["expected_profile_sha256"])


register("plan", _plan)


def _apply(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return apply_plan(Path(request["workspace_manifest"]), args["plan"])


def _reconcile(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return reconcile(Path(request["workspace_manifest"]), Path(args["journal_ref"]), args["mode"])


register("apply", _apply)
register("reconcile", _reconcile)


def _reindex(request: dict[str, object]) -> dict[str, object]:
    return reindex(Path(request["workspace_manifest"]), request["args"].get("collections", []))


def _search(request: dict[str, object]) -> dict[str, object]:
    return search(Path(request["workspace_manifest"]), request["args"])


register("reindex", _reindex)
register("search", _search)


def _materialize(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return materialize(Path(request["workspace_manifest"]), args.get("resource_plan", []), args.get("instance_manifest", {}), args["initialization_id"])


register("materialize", _materialize)


def _plan_migration(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return plan_profile_migration(Path(request["workspace_manifest"]), Path(args["new_profile_ref"]), args["affected_collections"], args["intent_ref"])


register("plan_migration", _plan_migration)


def _bundle(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return bundle(Path(request["workspace_manifest"]), args["selection"], Path(args["destination"]), bool(args.get("include_history", False)))


register("bundle", _bundle)


def _inspect_bundle(request: dict[str, object]) -> dict[str, object]:
    return inspect_bundle(Path(request["args"]["bundle_root"]))


def _restore_preview(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return restore_preview(Path(args["bundle_root"]), Path(args["target_root"]), args["root_bindings"])


def _restore(request: dict[str, object]) -> dict[str, object]:
    return apply_restore(request["args"]["preview"])


def _restore_record(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return {"status": "ok", "result": restore_record(args["result"], args.get("checks", [])), "diagnostics": [], "changed": []}


register("inspect_bundle", _inspect_bundle)
register("restore_preview", _restore_preview)
register("restore", _restore)
register("restore_record", _restore_record)


def _capability_report(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return {"status": "ok", "result": capability_report(args["observations"], args["host"], args["model"], args["observed_at"]), "diagnostics": [], "changed": []}


def _binding_preview(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    result = binding_preview(Path(request["workspace_manifest"]), args["host"], Path(args["host_root"]))
    return {"status": result["status"] if result["status"] in {"ok", "partial", "conflict"} else "ok", "result": result, "diagnostics": result.get("diagnostics", []), "changed": []}


def _binding_status(request: dict[str, object]) -> dict[str, object]:
    result = binding_status(Path(request["workspace_manifest"]), request["args"]["host"])
    return {"status": "ok", "result": result, "diagnostics": [], "changed": []}


register("capability_report", _capability_report)
register("binding_preview", _binding_preview)
register("binding_status", _binding_status)


def _scope_check(request: dict[str, object]) -> dict[str, object]:
    result = scope_check(Path(request["workspace_manifest"]), Path(request["args"]["start_dir"]))
    return {"status": "ok", "result": result, "diagnostics": [], "changed": []}


def _refresh_context(request: dict[str, object]) -> dict[str, object]:
    return ensure_project_entrypoints(Path(request["workspace_manifest"]))


register("scope_check", _scope_check)
register("refresh_context", _refresh_context)


def _deletion_preview(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return deletion_preview(Path(request["workspace_manifest"]), args["member_ref"], args["requested_scope"])


def _delete_member(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return apply_deletion(args["preview"], args["plan_id"])


def _record_redirect(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return record_redirect(Path(request["workspace_manifest"]), args["old_ref"], args["new_ref"])


register("deletion_preview", _deletion_preview)
register("delete_member", _delete_member)
register("record_redirect", _record_redirect)


def _log_event(request: dict[str, object]) -> dict[str, object]:
    args = request["args"]
    return log_event(Path(request["workspace_manifest"]), args["work_ref"], args["event"], args["intent_ref"], args.get("expected_sha256"))


register("log_event", _log_event)


from qiming_core.initialize import initialize
from qiming_core.host_binding import bind

def _init(request):
    args=request['args']
    return initialize(Path(args['root']),args.get('preset','general'),args.get('name'),args.get('goal'),args.get('hosts','auto'),bool(args.get('dry_run',False)))

register('init', _init)
register('bind', lambda request: bind(Path(request['workspace_manifest']),request['args']['host']))

from qiming_core.locks import lock_status, lock_break
from qiming_core.upgrade import upgrade_preview, upgrade
register('lock_status', lambda r: lock_status(Path(r['workspace_manifest'])))
register('lock_break', lambda r: lock_break(Path(r['workspace_manifest']),r['args']['run_id'],r['args']['expected_sha256']))
register('upgrade_preview', lambda r: upgrade_preview(Path(r['workspace_manifest']),Path(r['args']['seed_dir'])))
register('upgrade', lambda r: upgrade(Path(r['workspace_manifest']),r['args']['preview'],r['args']['plan_id']))

def _short_init(argv):
    parser=argparse.ArgumentParser(description='Initialize Qiming in this project only')
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--preset',choices=['general','dev','writing'],default='general')
    parser.add_argument('--name')
    parser.add_argument('--goal')
    parser.add_argument('--hosts',default='auto')
    parser.add_argument('--dry-run',action='store_true')
    args=vars(parser.parse_args(argv)); args['root']=str(args['root'])
    result=dispatch({'protocol':'qiming.tool/1','request_id':'init','op':'init','args':args})
    print(json.dumps(result,ensure_ascii=False))
    info=result.get('result') or {}
    print('启明接入：'+result['status'],file=sys.stderr)
    print('项目目录：'+str(Path(args['root']).resolve()),file=sys.stderr)
    if info.get('dry_run'):
        print('仅预览，未写入文件。下一步：去掉 --dry-run 执行接入。',file=sys.stderr)
    elif result['status'] in {'ok','ok_with_warnings'}:
        print('已有实例已保留。' if info.get('already_initialized') else '已建立本项目的启明实例。',file=sys.stderr)
        print('宿主绑定：'+', '.join(row['host'] for row in info.get('bound_hosts',[])),file=sys.stderr)
        print('下一步：读取 .qiming/START.md，接续当前任务。',file=sys.stderr)
    else:
        for diagnostic in result.get('diagnostics',[]):
            print('需要处理：'+diagnostic.get('message',''),file=sys.stderr)
        print('下一步：核对上方诊断；保留现有目录后重试。',file=sys.stderr)
    return EXIT_CODES[result['status']]


def _short_log(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Append a Qiming work event")
    parser.add_argument("work_path", help="Existing work JSON path relative to the project root")
    parser.add_argument("summary", help="One-line event summary")
    parser.add_argument("--workspace-manifest", type=Path, required=True)
    parser.add_argument("--kind", choices=("observation", "decision", "action", "handoff"), default="observation")
    parser.add_argument("--intent-ref", default=None, help="Defaults to the target work record id")
    parser.add_argument("--event-id", default=None, help="Stable ID for safe retries")
    options = parser.parse_args(argv)
    event = {"id": options.event_id or f"evt-{uuid.uuid4()}", "kind": options.kind,
             "summary": options.summary, "observed_at": datetime.now(timezone.utc).isoformat()}
    try:
        manifest = json.loads(options.workspace_manifest.read_text(encoding="utf-8"))
        profile = json.loads((options.workspace_manifest.parent / manifest["profile"]).read_text(encoding="utf-8"))
        work_root = profile["collections"]["work"]["root"]
        output = log_event(options.workspace_manifest,
                           {"kind": "file", "root": work_root, "path": options.work_path},
                           event, options.intent_ref)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        output = {"status": "error", "result": None, "diagnostics": [
            {"code": "INVALID_INPUT", "message": str(exc), "locator": None, "retryable": False, "details": {}}], "changed": []}
    sys.stdout.write(json.dumps(response("log", output["status"], output.get("result"),
                                         output.get("diagnostics", []), output.get("changed", []),
                                         output.get("run_id")), ensure_ascii=False, separators=(",", ":")) + "\n")
    return EXIT_CODES[output["status"]]


def main() -> int:
    if sys.argv[1:2] == ["init"]:
        return _short_init(sys.argv[2:])
    if sys.argv[1:2] == ["log"]:
        return _short_log(sys.argv[2:])
    parser = argparse.ArgumentParser(description="Qiming local tool protocol")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request", type=Path)
    source.add_argument("--stdin", action="store_true")
    options = parser.parse_args()
    try:
        raw = sys.stdin.read() if options.stdin else options.request.read_text(encoding="utf-8")
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise ValueError("Request must be an object")
        output = dispatch(request)
    except (OSError, ValueError, json.JSONDecodeError):
        output = response("", "error", None, [{"code": "INVALID_INPUT", "message": "Unable to read a valid JSON request", "locator": None, "retryable": False, "details": {}}], [], None)
    sys.stdout.write(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n")
    return EXIT_CODES[output["status"]]


if __name__ == "__main__":
    raise SystemExit(main())

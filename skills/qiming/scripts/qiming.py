#!/usr/bin/env python3
"""Read a Qiming JSON request and print exactly one JSON response."""

import argparse
import json
from pathlib import Path
import sys

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


EXIT_CODES = {"ok": 0, "error": 2, "conflict": 3, "partial": 4}


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


def main() -> int:
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

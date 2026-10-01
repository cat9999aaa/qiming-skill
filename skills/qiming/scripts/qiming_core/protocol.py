"""JSON request/response contract shared by Qiming tools."""

from collections.abc import Callable


PROTOCOL = "qiming.tool/1"
Handler = Callable[[dict[str, object]], dict[str, object]]
HANDLERS: dict[str, Handler] = {}


def response(
    request_id: str,
    status: str,
    result: object,
    diagnostics: list[dict[str, object]],
    changed: list[dict[str, object]],
    run_id: str | None,
) -> dict[str, object]:
    for diagnostic in diagnostics:
        diagnostic.setdefault('hint', {
            'WRITE_CONFLICT':'Re-read the file and compare changes before preparing a new plan.',
            'INVALID_INPUT':'Check operation arguments against references/tools.md and references/quickstart.md.',
            'IO_ERROR':'Check file permissions and paths; retry only after resolving the cause.',
            'SECRET_VALUE_FORBIDDEN':'Use credential_ref with a provider and opaque ID; never paste the credential value.',
            'SCOPE_MISMATCH':'Check profile.json collection root, directory, codec and exclusions.',
        }.get(diagnostic.get('code'),'Inspect the named record and diagnostic details before retrying.'))
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "status": status,
        "result": result,
        "diagnostics": diagnostics,
        "changed": changed,
        "run_id": run_id,
    }


def register(op: str, handler: Handler) -> None:
    HANDLERS[op] = handler


def dispatch(request: dict[str, object]) -> dict[str, object]:
    request_id = request.get("request_id")
    if not isinstance(request_id, str):
        request_id = ""
    if request.get("protocol") != PROTOCOL or not isinstance(request.get("args"), dict):
        return response(request_id, "error", None, [_diag("INVALID_INPUT", "Invalid request protocol or arguments")], [], None)
    op = request.get("op")
    if not isinstance(op, str) or op not in HANDLERS:
        return response(request_id, "error", None, [_diag("INVALID_INPUT", "Unsupported operation")], [], None)
    try:
        output = HANDLERS[op](request)
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        return response(request_id, "error", None, [_diag("INVALID_INPUT", str(exc))], [], None)
    except OSError as exc:
        return response(request_id, "error", None, [_diag("IO_ERROR", str(exc))], [], None)
    return response(request_id, output.get("status", "ok"), output.get("result"), output.get("diagnostics", []), output.get("changed", []), output.get("run_id"))


def _diag(code: str, message: str) -> dict[str, object]:
    return {"code": code, "message": message, "locator": None, "retryable": False, "details": {}}

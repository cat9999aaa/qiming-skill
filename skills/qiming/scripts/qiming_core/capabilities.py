"""Report observed host abilities without inferring them from a product name."""

from __future__ import annotations

_REQUIRED = ("file_read", "file_write", "command_exec", "controlled_write", "keyword_search", "sqlite", "network", "service_connection", "credential_access", "scheduling")
_COMPAT = {"format_recognition": "format", "tool_invocation": "tool", "behavior": "behavior"}


def capability_report(observations: list[dict[str, object]], host: str, model: str, observed_at: str) -> dict[str, object]:
    by_name = {str(item.get("name")): item for item in observations if isinstance(item, dict)}
    capabilities = []
    for name in _REQUIRED:
        item = by_name.get(name, {})
        available = item.get("available") if isinstance(item.get("available"), bool) else None
        capabilities.append({"name": name, "available": available, "evidence_ref": item.get("evidence_ref"), "limitations": item.get("limitations", [])})
    compatibility = {}
    for name, label in _COMPAT.items():
        item = by_name.get(name, {})
        available = item.get("available")
        compatibility[label] = "pass" if available is True and item.get("evidence_ref") else "fail" if available is False and item.get("evidence_ref") else "not-run"
    available = {item["name"]: item["available"] for item in capabilities}
    if available["file_read"] is True and available["file_write"] is False:
        operation_level = "read-only"
    elif available["file_read"] is True and available["file_write"] is True and available["controlled_write"] is True:
        operation_level = "controlled-local"
    elif available["file_read"] is True and available["file_write"] is True:
        operation_level = "single-writer"
    else:
        operation_level = "unverified"
    limitations = [f"{item['name']} unavailable or unverified" for item in capabilities if item["available"] is not True]
    if compatibility["behavior"] == "not-run":
        limitations.append("behavior scenarios not run")
    return {"protocol": "qiming.capability/1", "host": host, "model": model, "observed_at": observed_at, "capabilities": capabilities, "compatibility": compatibility, "operation_level": operation_level, "limitations": limitations}

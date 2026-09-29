"""Record actual observations while omitting known secret-bearing fields."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_SENSITIVE_KEYS = {"password", "passwd", "secret", "token", "api_key", "access_key", "private_key", "authorization", "credential", "cookie"}


def _scrub(value: Any, omitted: list[str], prefix: str = "") -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            label = str(key)
            if any(marker in label.lower() for marker in _SENSITIVE_KEYS):
                omitted.append(f"{prefix}/{label}")
                continue
            result[key] = _scrub(item, omitted, f"{prefix}/{label}")
        return result
    if isinstance(value, list):
        return [_scrub(item, omitted, f"{prefix}/{index}") for index, item in enumerate(value)]
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        parts = urlsplit(value)
        if parts.username or parts.password:
            omitted.append(f"{prefix}/url-userinfo")
            hostname = parts.hostname or ""
            netloc = hostname + (f":{parts.port}" if parts.port else "")
            return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
        if parts.query:
            omitted.append(f"{prefix}/url-query")
            return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return value


def make_evidence(run_id: str, kind: str, subject: dict[str, object], source: dict[str, object], coverage: dict[str, object], result: dict[str, object]) -> dict[str, object]:
    if kind not in {"command", "file", "service", "web", "user-report"}:
        raise ValueError("unsupported evidence kind")
    omitted: list[str] = []
    safe_source = _scrub(source, omitted, "source")
    safe_result = _scrub(result, omitted, "result")
    safe_subject = _scrub(subject, omitted, "subject")
    safe_coverage = _scrub(coverage, omitted, "coverage")
    return {
        "id": f"rec_{uuid.uuid4()}",
        "run_id": run_id,
        "kind": kind,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "subject": safe_subject,
        "source": safe_source,
        "source_fingerprint": safe_source.get("fingerprint"),
        "coverage": safe_coverage,
        "result": safe_result,
        "limitations": [f"omitted sensitive field {path}" for path in omitted],
    }

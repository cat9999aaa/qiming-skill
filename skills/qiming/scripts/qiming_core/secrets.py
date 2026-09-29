"""Keep credential values out of ordinary Qiming authority records."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

_SECRET_KEYS = {"password", "passwd", "secret", "token", "api_key", "access_key", "private_key", "client_secret", "otp_seed", "recovery_codes"}


def _diag(message: str, locator: str) -> dict[str, object]:
    return {"code": "SECRET_VALUE_FORBIDDEN", "message": message, "locator": locator, "retryable": False, "details": {}}


def validate_account_ref(record: dict[str, object]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                name = str(key).lower().replace("-", "_")
                field = f"{path}/{key}"
                if name in _SECRET_KEYS or (path.endswith("/credential_ref") and name not in {"provider", "id", "object_id"}):
                    issues.append(_diag("Credential value must use a dedicated provider", field))
                    continue
                visit(item, field)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}/{index}")
        elif isinstance(value, str) and value.startswith(("http://", "https://")):
            parsed = urlsplit(value)
            if parsed.username or parsed.password or parsed.query:
                issues.append(_diag("Credential-bearing URL is not allowed in an ordinary record", path))

    visit(record, "")
    ref = record.get("credential_ref")
    if ref is not None and (not isinstance(ref, dict) or not isinstance(ref.get("provider"), str) or not isinstance(ref.get("id", ref.get("object_id")), str)):
        issues.append({"code": "SCHEMA_INVALID", "message": "credential_ref requires provider and opaque id", "locator": "/credential_ref", "retryable": False, "details": {}})
    return issues

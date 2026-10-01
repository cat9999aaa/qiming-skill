"""Keep credential values out of ordinary Qiming authority records."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, parse_qsl
import re

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
        elif isinstance(value, str):
            if re.search(r'(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{15,}|-----BEGIN (?:[A-Z ]*PRIVATE KEY|OPENSSH PRIVATE KEY)-----)', value):
                issues.append(_diag('Credential-like value must be replaced with a provider reference',path))
            if not value.startswith(('http://','https://')):
                return
            parsed = urlsplit(value)
            if parsed.username or parsed.password or any(key.lower().replace("-","_") in _SECRET_KEYS | {"key","sig","signature","access_token","auth","authorization"} for key, _ in parse_qsl(parsed.query)):
                issues.append(_diag("Credential-bearing URL is not allowed in an ordinary record", path))

    visit(record, "")
    ref = record.get("credential_ref")
    if ref is not None and (not isinstance(ref, dict) or not isinstance(ref.get("provider"), str) or not isinstance(ref.get("id", ref.get("object_id")), str)):
        issues.append({"code": "SCHEMA_INVALID", "message": "credential_ref requires provider and opaque id", "locator": "/credential_ref", "retryable": False, "details": {}})
    return issues



def managed_payload_issues(manifest_path, locator, data):
    from .profile import load_profile
    from .collections import contains
    from .scan import _root
    from .codec import decode_record
    target=(_root(manifest_path,locator['root'])/locator['path']).resolve()
    profile=load_profile(manifest_path)
    for collection in profile['collections'].values():
        try:
            root=_root(manifest_path,collection['root'])
        except ValueError:
            continue  # A missing unrelated root is reported by validate, not this target write.
        if target.is_relative_to(root) and contains(profile,collection,target.relative_to(root)):
            try:
                value,_=decode_record(data,collection.get('codec','json'))
            except ValueError as error:
                return [{'code':'SCHEMA_INVALID','message':'Managed payload cannot be decoded; check codec and schema.','hint':'Use valid JSON, or install PyYAML for YAML/frontmatter.'}]
            issues=validate_account_ref(value)
            if collection.get('codec')=='markdown-frontmatter':
                issues+=validate_account_ref({'body':data.decode('utf-8')})
            if issues: return issues
    return []

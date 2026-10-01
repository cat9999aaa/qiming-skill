"""Local workspace mappings, deliberately free of business-specific fields."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .codec import load_record


def _local_file(base: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("profile path must remain in the control directory")
    resolved = (base / path).resolve()
    if not resolved.is_relative_to(base.resolve()):
        raise ValueError("profile path escapes control directory")
    return resolved


def load_profile(manifest_path: Path) -> dict[str, object]:
    manifest, _ = load_record(manifest_path, "json")
    if manifest.get("protocol") != "qiming.workspace/1":
        raise ValueError("unsupported workspace protocol")
    relative = manifest.get("profile")
    if not isinstance(relative, str):
        raise ValueError("workspace profile path missing")
    profile, _ = load_record(_local_file(manifest_path.parent, relative), "json")
    if profile.get("protocol") != "qiming.profile/1":
        raise ValueError("unsupported profile protocol")
    if not isinstance(profile.get("collections"), dict) or not isinstance(profile.get("mappings"), dict):
        raise ValueError("profile collections and mappings must be objects")
    return profile


def _pointer(source: dict[str, object], pointer: str) -> tuple[bool, Any]:
    if pointer == "":
        return True, source
    if not pointer.startswith("/"):
        raise ValueError("JSON Pointer must start with /")
    current: Any = source
    for raw_part in pointer[1:].split("/"):
        if "~" in raw_part and re_invalid_escape(raw_part):
            raise ValueError("invalid JSON Pointer escape")
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdecimal() and (part == "0" or not part.startswith("0")) and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def re_invalid_escape(part: str) -> bool:
    import re

    return re.search(r"~(?![01])", part) is not None


def normalize_fields(source: dict[str, object], mapping: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for field, rule in mapping.items():
        if not isinstance(rule, dict) or not isinstance(rule.get("source"), str):
            raise ValueError(f"mapping for {field} requires source")
        found, value = _pointer(source, rule["source"])
        if not found:
            if "default" not in rule:
                continue
            value = deepcopy(rule["default"])
        values = rule.get("values", {})
        if values and not isinstance(values, dict):
            raise ValueError("mapping values must be an object")
        if isinstance(value, str) and value in values:
            value = values[value]
        result[field] = deepcopy(value)
    return result


def validate_profile(profile, manifest):
    if profile.get('protocol') != 'qiming.profile/1' or not isinstance(profile.get('collections'),dict) or not isinstance(profile.get('mappings'),dict):
        raise ValueError('profile requires protocol, collections and mappings')
    for name, collection in profile['collections'].items():
        if not isinstance(collection,dict) or collection.get('root') not in manifest.get('roots',{}):
            raise ValueError(f'collection {name}: unknown root alias')
        if collection.get('codec','json') not in {'json','yaml','markdown-frontmatter'}:
            raise ValueError(f'collection {name}: unsupported codec')
        mapping=collection.get('mapping')
        if mapping is not None and mapping not in profile['mappings']:
            raise ValueError(f'collection {name}: unknown mapping')
        for field in ('directory','pattern'):
            value=collection.get(field,'.' if field=='directory' else '**/*.json')
            if not isinstance(value,str) or not value or Path(value).is_absolute() or '..' in Path(value).parts:
                raise ValueError(f'collection {name}: unsafe {field}')
        for field in ('exclude',):
            if field in collection and (not isinstance(collection[field],list) or not all(isinstance(x,str) for x in collection[field])):
                raise ValueError(f'collection {name}: exclude must be a list of patterns')
    for mapping in profile['mappings'].values():
        if not isinstance(mapping,dict): raise ValueError('mapping must be an object')
        normalize_fields({},mapping)

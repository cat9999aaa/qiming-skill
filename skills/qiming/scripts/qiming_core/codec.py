"""Lossless reads of Qiming's three supported record containers.

Writes to existing YAML/frontmatter are intentionally disabled until a codec
that preserves comments and layout is installed. Callers keep the raw bytes.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

try:
    import yaml
    from yaml.events import AliasEvent
    from yaml.nodes import MappingNode, ScalarNode, SequenceNode
except ModuleNotFoundError:
    yaml = None
    AliasEvent = MappingNode = ScalarNode = SequenceNode = None

_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[Tt ].*)?\Z")
_NON_JSON_BOOL = {"yes", "no", "on", "off", "y", "n"}
_ALLOWED_TAGS = {None, "!", "tag:yaml.org,2002:str", "tag:yaml.org,2002:int", "tag:yaml.org,2002:float", "tag:yaml.org,2002:bool", "tag:yaml.org,2002:null"}


def _parse_scalar(node: ScalarNode, *, key: bool = False) -> Any:
    value = node.value
    if key:
        return value
    if node.style in {'"', "'", "|", ">"}:
        return value
    lower = value.lower()
    if lower in _NON_JSON_BOOL or _DATE.fullmatch(value):
        raise ValueError(f"ambiguous YAML scalar: {value!r}")
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    if _NUMBER.fullmatch(value):
        number = json.loads(value)
        if isinstance(number, float) and not math.isfinite(number):
            raise ValueError("nonfinite number")
        return number
    if lower in {".inf", "+.inf", "-.inf", ".nan", "nan", "inf"}:
        raise ValueError("nonfinite number")
    return value


def _node_to_json(node: yaml.Node) -> Any:
    if isinstance(node, ScalarNode):
        return _parse_scalar(node)
    if isinstance(node, SequenceNode):
        return [_node_to_json(item) for item in node.value]
    if isinstance(node, MappingNode):
        result: dict[str, Any] = {}
        for key_node, value_node in node.value:
            if not isinstance(key_node, ScalarNode):
                raise ValueError("YAML keys must be strings")
            key = _parse_scalar(key_node, key=True)
            if key == "<<":
                raise ValueError("YAML merge keys are unsupported")
            if key in result:
                raise ValueError(f"duplicate YAML key: {key}")
            result[key] = _node_to_json(value_node)
        return result
    raise ValueError("unsupported YAML node")


def _restricted_yaml(raw: bytes) -> dict[str, object]:
    if yaml is None:
        raise ValueError("YAML_CODEC_UNAVAILABLE: install PyYAML to read YAML or frontmatter")
    try:
        source = raw.decode("utf-8")
        events = list(yaml.parse(source, Loader=yaml.BaseLoader))
        if sum(event.__class__.__name__ == "DocumentStartEvent" for event in events) != 1:
            raise ValueError("one YAML document is required")
        for event in events:
            if isinstance(event, AliasEvent) or getattr(event, "anchor", None):
                raise ValueError("YAML anchors and aliases are unsupported")
            if getattr(event, "tag", None) not in _ALLOWED_TAGS:
                raise ValueError("custom YAML tags are unsupported")
        node = yaml.compose(source, Loader=yaml.BaseLoader)
        value = _node_to_json(node) if node else None
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("record must be an object")
    return value


def load_record(path: Path, codec: str) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    if codec == "json":
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("record must be an object")
        return value, raw
    if codec == "yaml":
        return _restricted_yaml(raw), raw
    if codec == "markdown-frontmatter":
        lines = raw.splitlines(keepends=True)
        if not lines or lines[0].strip() != b"---":
            raise ValueError("frontmatter must begin at byte zero")
        for index, line in enumerate(lines[1:], 1):
            if line.strip() == b"---":
                return _restricted_yaml(b"".join(lines[1:index])), raw
        raise ValueError("frontmatter closing delimiter missing")
    raise ValueError(f"unsupported codec: {codec}")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON number: {value}")


def can_round_trip(path: Path, codec: str) -> bool:
    try:
        load_record(path, codec)
    except (OSError, ValueError):
        return False
    return codec == "json"

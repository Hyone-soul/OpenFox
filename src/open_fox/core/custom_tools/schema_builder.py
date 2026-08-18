"""基于函数签名 + 类型注解 + docstring 自动生成 OpenAI function schema。"""
from __future__ import annotations

import inspect
import re
import types
import typing
from collections.abc import Callable
from typing import Any, get_args, get_origin


def build_schema_from_signature(func: Callable) -> dict:
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        ann = param.annotation if param.annotation is not inspect.Parameter.empty else None
        schema = _type_to_schema(ann)
        properties[name] = schema
        if param.default is inspect.Parameter.empty:
            required.append(name)
    out: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        out["required"] = required
    return out


def _type_to_schema(ann) -> dict:
    if ann is None:
        return {"type": "string"}
    origin = get_origin(ann)
    args = get_args(ann)
    if (origin is typing.Union or origin is types.UnionType) and type(None) in args:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return {"anyOf": [_type_to_schema(non_none[0]), {"type": "null"}]}
    if origin is list:
        item = args[0] if args else str
        return {"type": "array", "items": _type_to_schema(item)}
    if origin is dict:
        val = args[1] if len(args) > 1 else str
        return {"type": "object", "additionalProperties": _type_to_schema(val)}
    if origin is typing.Literal:
        return {"enum": list(args)}
    if ann is str:
        return {"type": "string"}
    if ann is int:
        return {"type": "integer"}
    if ann is float:
        return {"type": "number"}
    if ann is bool:
        return {"type": "boolean"}
    return {"type": "string"}


def parse_docstring_summary(doc: str | None) -> str:
    if not doc:
        return ""
    lines = [l.strip() for l in doc.strip().splitlines() if l.strip()]
    return lines[0] if lines else ""


def parse_docstring_args(doc: str | None) -> dict[str, str]:
    """支持 Google / NumPy / Sphinx；命中即停。"""
    if not doc:
        return {}
    google = _parse_google(doc)
    if google:
        return google
    numpy = _parse_numpy(doc)
    if numpy:
        return numpy
    return _parse_sphinx(doc)


def _parse_google(doc: str) -> dict[str, str]:
    if "Args:" not in doc and "Arguments:" not in doc:
        return {}
    out: dict[str, str] = {}
    in_args = False
    for line in doc.splitlines():
        s = line.strip()
        if s.startswith(("Args:", "Arguments:")):
            in_args = True
            continue
        if in_args:
            if not s:
                continue
            if s.endswith(":") and not re.match(r"^[\w]+\s*\(.*\):", s):
                break
            m = re.match(r"^(\w+)\s*(\(.+\))?\s*:\s*(.*)$", s)
            if m:
                out[m.group(1)] = m.group(3).strip()
            elif out:
                last = next(reversed(out))
                out[last] = (out[last] + " " + s).strip()
    return out


def _parse_numpy(doc: str) -> dict[str, str]:
    if "Parameters" not in doc and "Params" not in doc:
        return {}
    out: dict[str, str] = {}
    in_params = False
    current = None
    for line in doc.splitlines():
        s = line.strip()
        if re.match(r"^(Parameters|Params)\s*$", s) or s == "Parameters" or s == "Parameters ----------":
            in_params = True
            continue
        if in_params:
            if s.startswith("---"):
                continue
            m = re.match(r"^(\w+)\s*:.*$", s)
            if m:
                current = m.group(1)
                out[current] = ""
                continue
            if s.startswith(":"):
                continue
            if current and s:
                out[current] = (out[current] + " " + s).strip()
    return out


def _parse_sphinx(doc: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r":param\s+(\w+):\s*(.+)", doc):
        out[m.group(1)] = m.group(2).strip()
    return out

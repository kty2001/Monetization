from __future__ import annotations

from typing import Any


def _first(data: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _join_list(value: Any) -> str:
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and "title" in item:
                parts.append(str(item["title"]))
            else:
                parts.append(str(item))
        return ",".join(parts)
    if value is None:
        return ""
    return str(value)

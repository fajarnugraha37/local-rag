from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_NAMESPACE = "default"
_MAX_NAMESPACE_LENGTH = 64
_NAMESPACE_RE = re.compile(r"^[a-z0-9._-]+$")


def is_valid_namespace(value: str) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if not candidate or len(candidate) > _MAX_NAMESPACE_LENGTH:
        return False
    return _NAMESPACE_RE.fullmatch(candidate) is not None


def validate_namespace(value: Optional[str], *, default_to_default: bool = True) -> str:
    if value is None:
        if default_to_default:
            return DEFAULT_NAMESPACE
        raise ValueError("Namespace is required.")

    candidate = value.strip()
    if not candidate:
        if default_to_default:
            return DEFAULT_NAMESPACE
        raise ValueError("Namespace is required.")

    if not is_valid_namespace(candidate):
        raise ValueError(
            "Invalid namespace. Expected 1-64 chars matching [a-z0-9._-]."
        )
    return candidate


def parse_namespaces(values: Optional[Iterable[str]]) -> List[str]:
    if not values:
        return []

    parsed: List[str] = []
    seen = set()
    for raw in values:
        if raw is None:
            continue
        for part in str(raw).split(","):
            candidate = part.strip()
            if not candidate:
                continue
            namespace = validate_namespace(candidate, default_to_default=False)
            if namespace in seen:
                continue
            parsed.append(namespace)
            seen.add(namespace)
    return parsed


def merge_namespace_filters(
    filters: Optional[Dict[str, Any]],
    namespaces: Optional[Iterable[str]],
) -> Optional[Dict[str, Any]]:
    parsed = parse_namespaces(namespaces)
    base = dict(filters or {})
    if not parsed:
        return base or None

    if len(parsed) == 1:
        ns_filter: Dict[str, Any] = {"namespace": parsed[0]}
    else:
        ns_filter = {"$or": [{"namespace": ns} for ns in parsed]}

    if not base:
        return ns_filter
    return {"$and": [base, ns_filter]}

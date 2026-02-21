from __future__ import annotations

from typing import Any


def render_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "(no records)"

    widths: list[int] = []
    for key, header in columns:
        max_value = max(len(str(row.get(key, ""))) for row in rows)
        widths.append(max(len(header), max_value))

    header_line = "  ".join(header.ljust(widths[i]) for i, (_, header) in enumerate(columns))
    sep_line = "  ".join("-" * widths[i] for i in range(len(columns)))
    body_lines = []
    for row in rows:
        body_lines.append(
            "  ".join(
                str(row.get(key, "")).ljust(widths[i]) for i, (key, _) in enumerate(columns)
            )
        )
    return "\n".join([header_line, sep_line, *body_lines])


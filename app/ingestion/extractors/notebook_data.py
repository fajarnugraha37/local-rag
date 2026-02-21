from __future__ import annotations

import json
from typing import List, Optional

from .base import ExtractedDocument, ExtractedUnit, ExtractorContext, MissingDependencyError
from .utils import normalize_text, read_text, safe_decode


def extract_ipynb(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    warnings: List[str] = []
    if raw_bytes is None:
        text, _ = read_text(path, max_bytes=context.max_bytes)
    else:
        decoded, _ = safe_decode(raw_bytes)
        text = normalize_text(decoded)

    notebook = None
    try:
        import nbformat  # type: ignore

        notebook = nbformat.reads(text, as_version=4)
    except Exception:
        try:
            notebook = json.loads(text)
            warnings.append("nbformat_unavailable_or_failed_using_json_fallback")
        except Exception as exc:
            warnings.append(f"ipynb_parse_failed: {exc}")
            return ExtractedDocument(
                doc_type="ipynb", units=[ExtractedUnit(text=text)], warnings=warnings
            )

    cells = (
        notebook.get("cells", [])
        if isinstance(notebook, dict)
        else list(getattr(notebook, "cells", []))
    )
    units: List[ExtractedUnit] = []
    for idx, cell in enumerate(cells, start=1):
        if idx > context.max_objects:
            warnings.append(f"ipynb_truncated_at_max_objects={context.max_objects}")
            break
        cell_type = (
            cell.get("cell_type") if isinstance(cell, dict) else getattr(cell, "cell_type", "")
        ) or ""
        source = cell.get("source") if isinstance(cell, dict) else getattr(cell, "source", "")
        if isinstance(source, list):
            source = "\n".join(str(item) for item in source)
        source_text = normalize_text(str(source or ""))
        if not source_text:
            continue
        units.append(
            ExtractedUnit(
                text=f"[{cell_type}]\n{source_text}",
                metadata={"row_number": idx, "cell_type": cell_type},
            )
        )

    return ExtractedDocument(doc_type="ipynb", units=units, warnings=warnings)


def _table_to_units(table, context: ExtractorContext) -> List[ExtractedUnit]:
    units: List[ExtractedUnit] = []
    cols = list(table.column_names)
    rows = table.to_pylist()
    for idx, row in enumerate(rows, start=1):
        if idx > context.max_rows:
            break
        pairs = [f"{name}: {row.get(name, '')}" for name in cols]
        units.append(
            ExtractedUnit(text=normalize_text("\n".join(pairs)), metadata={"row_number": idx})
        )
    return units


def extract_parquet_like(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext, *, kind: str
) -> ExtractedDocument:
    if not context.enable_parquet:
        return ExtractedDocument(
            doc_type=kind, units=[], warnings=["parquet_like_disabled_by_config"]
        )

    try:
        import pyarrow.feather as feather  # type: ignore
        import pyarrow.ipc as ipc  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise MissingDependencyError(
            "pyarrow is required for parquet/feather/arrow ingestion"
        ) from exc

    if raw_bytes is not None:
        import io

        buffer = io.BytesIO(raw_bytes)
        if kind == "parquet":
            table = pq.read_table(buffer)
        elif kind == "feather":
            table = feather.read_table(buffer)
        else:
            table = ipc.RecordBatchFileReader(buffer).read_all()
    else:
        if kind == "parquet":
            table = pq.read_table(path)
        elif kind == "feather":
            table = feather.read_table(path)
        else:
            with ipc.RecordBatchFileReader(path) as reader:
                table = reader.read_all()

    units = _table_to_units(table, context)
    warnings = []
    if table.num_rows > context.max_rows:
        warnings.append(f"{kind}_truncated_at_max_rows={context.max_rows}")
    return ExtractedDocument(doc_type=kind, units=units, warnings=warnings)


def extract_parquet(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    return extract_parquet_like(path, raw_bytes, context, kind="parquet")


def extract_feather(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    return extract_parquet_like(path, raw_bytes, context, kind="feather")


def extract_arrow(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    return extract_parquet_like(path, raw_bytes, context, kind="arrow")

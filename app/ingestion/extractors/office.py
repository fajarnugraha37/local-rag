from __future__ import annotations

import io
import re
from typing import List, Optional

from .base import ExtractedDocument, ExtractedUnit, ExtractorContext, MissingDependencyError
from .utils import normalize_text


def _ole_extract_strings(path: str, raw_bytes: Optional[bytes], context: ExtractorContext) -> str:  # noqa: ARG001
    try:
        import olefile  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise MissingDependencyError("olefile is required for legacy OLE documents") from exc

    if raw_bytes is not None:
        ole = olefile.OleFileIO(io.BytesIO(raw_bytes))
    else:
        ole = olefile.OleFileIO(path)

    strings: List[str] = []
    try:
        for stream_name in ole.listdir(streams=True, storages=False):
            try:
                stream = ole.openstream(stream_name)
                payload = stream.read()
            except Exception:
                continue
            if not payload:
                continue
            try:
                decoded = payload.decode("utf-16-le")
            except Exception:
                decoded = payload.decode("latin-1", errors="ignore")
            for token in re.findall(r"[\w][\w\s,.;:()\-]{5,}", decoded):
                cleaned = normalize_text(token)
                if len(cleaned) >= 6:
                    strings.append(cleaned)
    finally:
        ole.close()

    return "\n".join(strings)


def extract_doc(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    if not context.enable_legacy_office:
        return ExtractedDocument(
            doc_type="doc", units=[], warnings=["legacy_office_disabled_by_config"]
        )
    try:
        text = _ole_extract_strings(path, raw_bytes, context)
    except MissingDependencyError:
        raise
    except Exception as exc:
        return ExtractedDocument(doc_type="doc", units=[], warnings=[f"doc_extract_failed: {exc}"])

    if not text.strip():
        return ExtractedDocument(doc_type="doc", units=[], warnings=["doc_no_extractable_text"])
    return ExtractedDocument(doc_type="doc", units=[ExtractedUnit(text=text)], warnings=[])


def extract_ppt(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    if not context.enable_legacy_office:
        return ExtractedDocument(
            doc_type="ppt", units=[], warnings=["legacy_office_disabled_by_config"]
        )
    try:
        text = _ole_extract_strings(path, raw_bytes, context)
    except MissingDependencyError:
        raise
    except Exception as exc:
        return ExtractedDocument(doc_type="ppt", units=[], warnings=[f"ppt_extract_failed: {exc}"])

    if not text.strip():
        return ExtractedDocument(doc_type="ppt", units=[], warnings=["ppt_no_extractable_text"])
    units = [
        ExtractedUnit(text=chunk, metadata={"slide_number": idx + 1})
        for idx, chunk in enumerate(text.split("\n\n"))
        if chunk.strip()
    ]
    return ExtractedDocument(doc_type="ppt", units=units, warnings=[])


def extract_xls(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    if not context.enable_legacy_office:
        return ExtractedDocument(
            doc_type="xls", units=[], warnings=["legacy_office_disabled_by_config"]
        )

    try:
        import xlrd  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise MissingDependencyError("xlrd is required for .xls ingestion") from exc

    try:
        if raw_bytes is not None:
            workbook = xlrd.open_workbook(file_contents=raw_bytes)
        else:
            workbook = xlrd.open_workbook(path)
    except Exception as exc:
        return ExtractedDocument(doc_type="xls", units=[], warnings=[f"xls_open_failed: {exc}"])

    units: List[ExtractedUnit] = []
    warnings: List[str] = []
    for sheet_idx, sheet in enumerate(workbook.sheets(), start=1):
        if sheet_idx > context.max_sheets:
            warnings.append(f"xls_truncated_at_max_sheets={context.max_sheets}")
            break
        for row_idx in range(sheet.nrows):
            if row_idx + 1 > context.max_rows:
                warnings.append(f"xls_sheet_{sheet.name}_truncated_at_max_rows={context.max_rows}")
                break
            values = [str(sheet.cell_value(row_idx, col_idx)) for col_idx in range(sheet.ncols)]
            if not any(v.strip() for v in values):
                continue
            units.append(
                ExtractedUnit(
                    text=normalize_text(" | ".join(values)),
                    metadata={"sheet_name": sheet.name, "row_number": row_idx + 1},
                )
            )

    return ExtractedDocument(doc_type="xls", units=units, warnings=warnings)

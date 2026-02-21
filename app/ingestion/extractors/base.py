from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ExtractedUnit:
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDocument:
    doc_type: str
    units: List[ExtractedUnit]
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ExtractorContext:
    max_bytes: int
    max_rows: int
    max_objects: int
    max_pages: int
    max_slides: int
    max_sheets: int
    max_zip_entries: int
    max_zip_uncompressed_bytes: int
    ingest_timeout_s: int
    enable_parquet: bool
    enable_legacy_office: bool
    extracted_at: str
    ingest_docling_enabled: bool = True
    ingest_docling_export_format: str = "markdown"


class ExtractorError(RuntimeError):
    pass


class UnsupportedFormatError(ExtractorError):
    pass


class MissingDependencyError(ExtractorError):
    pass


ExtractorFunc = Callable[[str, Optional[bytes], ExtractorContext], ExtractedDocument]


@dataclass(frozen=True)
class Extractor:
    name: str
    doc_type: str
    extract: ExtractorFunc

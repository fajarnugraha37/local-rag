from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from .base import ExtractedDocument, Extractor, ExtractorContext, UnsupportedFormatError
from .notebook_data import extract_arrow, extract_feather, extract_ipynb, extract_parquet
from .office import (
    extract_doc,
    extract_docx,
    extract_pdf,
    extract_ppt,
    extract_pptx,
    extract_xls,
    extract_xlsx,
)
from .structured import extract_csv_tsv, extract_har, extract_html_svg, extract_json, extract_json_lines, extract_log, extract_xml
from .textual import extract_textual


@dataclass
class ExtractorRegistry:
    by_extension: Dict[str, Extractor] = field(default_factory=dict)
    by_special_name: Dict[str, Extractor] = field(default_factory=dict)
    by_suffix: Dict[str, Extractor] = field(default_factory=dict)

    def register_extension(self, ext: str, extractor: Extractor) -> None:
        self.by_extension[ext.lower()] = extractor

    def register_special_name(self, name: str, extractor: Extractor) -> None:
        self.by_special_name[name.lower()] = extractor

    def register_suffix(self, suffix: str, extractor: Extractor) -> None:
        self.by_suffix[suffix.lower()] = extractor

    def resolve(self, path: str) -> Extractor:
        basename = os.path.basename(path).lower()

        if basename in self.by_special_name:
            return self.by_special_name[basename]

        for suffix in sorted(self.by_suffix, key=len, reverse=True):
            if basename.endswith(suffix):
                return self.by_suffix[suffix]

        ext = os.path.splitext(basename)[1].lower()
        if ext in self.by_extension:
            return self.by_extension[ext]

        raise UnsupportedFormatError(f"unsupported file extension or special name: {basename}")

    def extract_from_path(self, path: str, context: ExtractorContext) -> ExtractedDocument:
        extractor = self.resolve(path)
        return extractor.extract(path, None, context)

    def extract_from_bytes(self, file_name: str, raw_bytes: bytes, context: ExtractorContext) -> ExtractedDocument:
        extractor = self.resolve(file_name)
        return extractor.extract(file_name, raw_bytes, context)


def _extractor(name: str, doc_type: str, func):
    return Extractor(name=name, doc_type=doc_type, extract=func)


def build_default_registry() -> ExtractorRegistry:
    registry = ExtractorRegistry()

    textual = _extractor("textual", "text", extract_textual)
    json_ex = _extractor("json", "json", extract_json)
    jsonl_ex = _extractor("jsonl", "jsonl", extract_json_lines)
    csv_ex = _extractor("csv", "csv", extract_csv_tsv)
    html_ex = _extractor("html", "html", extract_html_svg)
    xml_ex = _extractor("xml", "xml", extract_xml)
    log_ex = _extractor("log", "log", extract_log)
    har_ex = _extractor("har", "har", extract_har)

    # Must-have docs/config/scripts/schema families
    for ext in [
        ".md", ".markdown", ".mdx", ".rst", ".adoc", ".asciidoc",
        ".yaml", ".yml", ".toml", ".ini", ".conf", ".env", ".properties",
        ".sql", ".proto", ".graphql", ".gql",
        ".sh", ".bash", ".ps1",
        ".txt",
        ".gitignore", ".gitattributes", ".editorconfig", ".npmrc", ".yarnrc",
    ]:
        registry.register_extension(ext, textual)

    for name in ["dockerfile", "makefile"]:
        registry.register_special_name(name, textual)

    registry.register_extension(".json", json_ex)
    registry.register_extension(".jsonc", json_ex)
    registry.register_extension(".jsonl", jsonl_ex)
    registry.register_extension(".ndjson", jsonl_ex)

    registry.register_extension(".csv", csv_ex)
    registry.register_extension(".tsv", csv_ex)

    registry.register_extension(".html", html_ex)
    registry.register_extension(".htm", html_ex)
    registry.register_extension(".svg", html_ex)

    registry.register_extension(".xml", xml_ex)
    registry.register_extension(".log", log_ex)
    registry.register_extension(".har", har_ex)

    # Office/binary
    registry.register_extension(".pdf", _extractor("pdf", "pdf", extract_pdf))
    registry.register_extension(".docx", _extractor("docx", "docx", extract_docx))
    registry.register_extension(".doc", _extractor("doc", "doc", extract_doc))
    registry.register_extension(".pptx", _extractor("pptx", "pptx", extract_pptx))
    registry.register_extension(".ppt", _extractor("ppt", "ppt", extract_ppt))
    registry.register_extension(".xlsx", _extractor("xlsx", "xlsx", extract_xlsx))
    registry.register_extension(".xls", _extractor("xls", "xls", extract_xls))

    # Data/notebook
    registry.register_extension(".ipynb", _extractor("ipynb", "ipynb", extract_ipynb))
    registry.register_extension(".parquet", _extractor("parquet", "parquet", extract_parquet))
    registry.register_extension(".feather", _extractor("feather", "feather", extract_feather))
    registry.register_extension(".arrow", _extractor("arrow", "arrow", extract_arrow))

    # OpenAPI compound suffixes
    registry.register_suffix(".openapi.yaml", textual)
    registry.register_suffix(".openapi.yml", textual)
    registry.register_suffix(".openapi.json", json_ex)

    return registry

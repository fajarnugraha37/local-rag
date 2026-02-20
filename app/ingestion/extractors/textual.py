from __future__ import annotations

import configparser
import json
import os
from typing import Dict, Optional, Tuple

import yaml

from .base import ExtractedDocument, ExtractedUnit, ExtractorContext
from .utils import json_pretty, normalize_text, read_text

try:
    import tomllib  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    tomllib = None


_DOC_TYPES = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdx": "mdx",
    ".rst": "rst",
    ".adoc": "adoc",
    ".asciidoc": "adoc",
    ".sql": "sql",
    ".proto": "proto",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".sh": "script",
    ".bash": "script",
    ".ps1": "powershell",
    ".txt": "text",
    ".log": "log",
    ".gitignore": "config",
    ".gitattributes": "config",
    ".editorconfig": "config",
    ".npmrc": "config",
    ".yarnrc": "config",
}


_SPECIAL_DOC_TYPES = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
}


def _normalize_path_info(path: str) -> Tuple[str, str]:
    name = os.path.basename(path)
    lower_name = name.lower()
    ext = os.path.splitext(lower_name)[1]
    return lower_name, ext


def _parse_properties(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            key, value = line, ""
        result[key.strip()] = value.strip()
    return result


def _parse_env(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _parse_ini_like(text: str) -> Dict[str, Dict[str, str]]:
    parser = configparser.ConfigParser()
    parser.read_string(text)
    output: Dict[str, Dict[str, str]] = {}
    for section in parser.sections():
        output[section] = {k: v for k, v in parser.items(section)}
    return output


def extract_textual(path: str, raw_bytes: Optional[bytes], context: ExtractorContext) -> ExtractedDocument:
    lower_name, ext = _normalize_path_info(path)
    warnings = []

    if raw_bytes is None:
        text, _ = read_text(path, max_bytes=context.max_bytes)
    else:
        from .utils import safe_decode

        decoded, _ = safe_decode(raw_bytes)
        text = normalize_text(decoded)

    doc_type = _SPECIAL_DOC_TYPES.get(lower_name) or _DOC_TYPES.get(ext, "text")

    if ext in {".yaml", ".yml"} or lower_name.endswith(".openapi.yaml") or lower_name.endswith(".openapi.yml"):
        try:
            data = yaml.safe_load(text)
            text = json_pretty(data)
            doc_type = "yaml"
        except Exception as exc:
            warnings.append(f"yaml_parse_failed: {exc}")
            doc_type = "yaml"
    elif ext == ".toml":
        if tomllib is None:
            warnings.append("tomllib_missing_fallback_raw_text")
            doc_type = "toml"
        else:
            try:
                data = tomllib.loads(text)
                text = json_pretty(data)
                doc_type = "toml"
            except Exception as exc:
                warnings.append(f"toml_parse_failed: {exc}")
                doc_type = "toml"
    elif ext in {".ini", ".conf"}:
        try:
            text = json_pretty(_parse_ini_like(text))
            doc_type = "ini"
        except Exception:
            doc_type = "config"
    elif ext == ".properties":
        text = json_pretty(_parse_properties(text))
        doc_type = "properties"
    elif ext == ".env":
        text = json_pretty(_parse_env(text))
        doc_type = "env"
    elif ext in {".yaml", ".yml"}:
        doc_type = "yaml"
    elif lower_name.endswith(".openapi.yaml") or lower_name.endswith(".openapi.yml"):
        doc_type = "openapi"

    return ExtractedDocument(
        doc_type=doc_type,
        units=[ExtractedUnit(text=text)],
        metadata={"detected_doc_type": doc_type},
        warnings=warnings,
    )

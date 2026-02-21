from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pathspec

from app.ingestion.extractors import ExtractorRegistry, build_default_registry
from app.ingestion.extractors.base import UnsupportedFormatError

DEFAULT_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
}


@dataclass
class ScanOptions:
    recursive: bool = True
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    respect_gitignore: bool = True
    respect_ragignore: bool = True
    extra_ignore_file: Optional[str] = None


@dataclass
class FileCandidate:
    path: str
    relative_path: str
    size_bytes: int


@dataclass
class ScanSummary:
    root_path: str
    scanned: int = 0
    selected: int = 0
    skipped: int = 0
    skipped_by_reason: Dict[str, int] = field(default_factory=dict)

    def add_skip(self, reason: str) -> None:
        self.skipped += 1
        self.skipped_by_reason[reason] = self.skipped_by_reason.get(reason, 0) + 1


def _normalize_rel_path(path: str) -> str:
    return path.replace("\\", "/")


def _load_ignore_spec(ignore_path: str) -> Optional[pathspec.PathSpec]:
    if not os.path.isfile(ignore_path):
        return None
    with open(ignore_path, "r", encoding="utf-8") as handle:
        lines = [line.rstrip("\n") for line in handle]
    if not lines:
        return None
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def _matches_default_excludes(relative_path: str) -> bool:
    normalized = _normalize_rel_path(relative_path).strip("/")
    if not normalized:
        return False
    parts = normalized.split("/")
    return any(part in DEFAULT_EXCLUDED_DIRS for part in parts)


def _matches_ignore_files(
    relative_path: str,
    root_spec: Optional[pathspec.PathSpec],
    git_specs: Sequence[Tuple[str, pathspec.PathSpec]],
) -> bool:
    normalized = _normalize_rel_path(relative_path)
    if root_spec and root_spec.match_file(normalized):
        return True

    for base_dir, spec in git_specs:
        if not base_dir:
            candidate = normalized
        elif normalized == base_dir:
            candidate = ""
        elif normalized.startswith(f"{base_dir}/"):
            candidate = normalized[len(base_dir) + 1 :]
        else:
            continue
        if candidate and spec.match_file(candidate):
            return True
    return False


def _path_allowed(relative_path: str, options: ScanOptions) -> bool:
    normalized = _normalize_rel_path(relative_path)
    if options.include_patterns and not any(fnmatch.fnmatch(normalized, pattern) for pattern in options.include_patterns):
        return False
    if options.exclude_patterns and any(fnmatch.fnmatch(normalized, pattern) for pattern in options.exclude_patterns):
        return False
    return True


def _iter_files(
    root_path: str,
    recursive: bool,
    *,
    respect_gitignore: bool,
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, pathspec.PathSpec]]]:
    root = Path(root_path)
    pairs: List[Tuple[str, str]] = []
    gitignore_specs: List[Tuple[str, pathspec.PathSpec]] = []

    if recursive:
        for walk_root, dirs, files in os.walk(root_path, topdown=True):
            dirs[:] = [item for item in dirs if item not in DEFAULT_EXCLUDED_DIRS]
            dirs.sort()
            files.sort()

            if respect_gitignore:
                ignore_path = os.path.join(walk_root, ".gitignore")
                spec = _load_ignore_spec(ignore_path)
                if spec:
                    base_dir = _normalize_rel_path(os.path.relpath(walk_root, root_path))
                    if base_dir == ".":
                        base_dir = ""
                    gitignore_specs.append((base_dir, spec))

            for file_name in files:
                abs_path = os.path.join(walk_root, file_name)
                rel_path = os.path.relpath(abs_path, root_path)
                pairs.append((os.path.abspath(abs_path), _normalize_rel_path(rel_path)))
    else:
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_file():
                abs_path = os.path.abspath(str(entry))
                rel_path = os.path.relpath(abs_path, root_path)
                pairs.append((abs_path, _normalize_rel_path(rel_path)))
    return pairs, gitignore_specs


def scan_folder(
    root_path: str,
    *,
    options: Optional[ScanOptions] = None,
    registry: Optional[ExtractorRegistry] = None,
) -> Tuple[List[FileCandidate], ScanSummary]:
    options = options or ScanOptions()
    registry = registry or build_default_registry()
    abs_root = os.path.abspath(root_path)
    summary = ScanSummary(root_path=abs_root)

    if not os.path.isdir(abs_root):
        summary.add_skip("root_not_directory")
        return [], summary

    ragignore_spec = None
    if options.respect_ragignore:
        ragignore_spec = _load_ignore_spec(os.path.join(abs_root, ".ragignore"))

    if options.extra_ignore_file:
        extra_spec = _load_ignore_spec(options.extra_ignore_file)
        if extra_spec:
            if ragignore_spec:
                combined = list(ragignore_spec.patterns) + list(extra_spec.patterns)
                ragignore_spec = pathspec.PathSpec(patterns=combined)
            else:
                ragignore_spec = extra_spec

    file_entries, gitignore_specs = _iter_files(
        abs_root,
        recursive=options.recursive,
        respect_gitignore=options.respect_gitignore,
    )

    candidates: List[FileCandidate] = []
    for abs_path, rel_path in file_entries:
        summary.scanned += 1

        if _matches_default_excludes(rel_path):
            summary.add_skip("default_excluded")
            continue

        if _matches_ignore_files(rel_path, ragignore_spec, gitignore_specs):
            summary.add_skip("ignored")
            continue

        if not _path_allowed(rel_path, options):
            summary.add_skip("pattern_filtered")
            continue

        try:
            registry.resolve(rel_path)
        except UnsupportedFormatError:
            summary.add_skip("unsupported_format")
            continue

        size_bytes = os.path.getsize(abs_path)
        candidates.append(FileCandidate(path=abs_path, relative_path=rel_path, size_bytes=size_bytes))
        summary.selected += 1

    return candidates, summary

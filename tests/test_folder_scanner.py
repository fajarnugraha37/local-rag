from pathlib import Path

from app.ingestion.folder_scanner import ScanOptions, scan_folder


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_folder_scanner_deterministic_ordering(tmp_path):
    root = tmp_path / "docs"
    _write(root / "b.md", "b")
    _write(root / "a.md", "a")
    _write(root / "nested" / "d.txt", "d")
    _write(root / "nested" / "c.txt", "c")
    _write(root / "z.bin", "binary")

    options = ScanOptions(recursive=True)
    first_candidates, first_summary = scan_folder(str(root), options=options)
    second_candidates, second_summary = scan_folder(str(root), options=options)

    first_paths = [item.relative_path for item in first_candidates]
    second_paths = [item.relative_path for item in second_candidates]

    assert first_paths == second_paths
    assert first_paths == ["a.md", "b.md", "nested/c.txt", "nested/d.txt"]
    assert first_summary.scanned == 5
    assert first_summary.selected == 4
    assert first_summary.skipped_by_reason.get("unsupported_format") == 1
    assert second_summary.scanned == 5
    assert second_summary.selected == 4


def test_folder_scanner_include_exclude_patterns(tmp_path):
    root = tmp_path / "repo"
    _write(root / "docs" / "keep.md", "keep")
    _write(root / "docs" / "drop.md", "drop")
    _write(root / "notes" / "keep.txt", "keep")
    _write(root / "notes" / "skip.txt", "skip")
    _write(root / "raw.bin", "unsupported")

    options = ScanOptions(
        recursive=True,
        include_patterns=["docs/*", "notes/*keep*"],
        exclude_patterns=["*drop*"],
    )
    candidates, summary = scan_folder(str(root), options=options)
    rel_paths = [item.relative_path for item in candidates]

    assert rel_paths == ["docs/keep.md", "notes/keep.txt"]
    assert summary.scanned == 5
    assert summary.selected == 2
    assert summary.skipped == 3
    assert summary.skipped_by_reason.get("pattern_filtered") == 3


def test_folder_scanner_respects_root_and_nested_gitignore(tmp_path):
    root = tmp_path / "fixture_gitignore"
    _write(root / ".gitignore", "*.log\nnested-ignore/\n")
    _write(root / "keep.md", "keep")
    _write(root / "drop.log", "drop")
    _write(root / "nested-ignore" / "ignored.txt", "ignore dir")
    _write(root / "nested" / ".gitignore", "*.tmp\n")
    _write(root / "nested" / "keep.txt", "keep")
    _write(root / "nested" / "skip.tmp", "skip")

    options = ScanOptions(recursive=True, respect_gitignore=True)
    candidates, summary = scan_folder(str(root), options=options)

    rel_paths = [item.relative_path for item in candidates]
    assert rel_paths == ["keep.md", "nested/keep.txt"]
    assert summary.skipped_by_reason.get("ignored") == 3


def test_folder_scanner_respects_ragignore(tmp_path):
    root = tmp_path / "fixture_ragignore"
    _write(root / ".ragignore", "private/**\n*.bak\n")
    _write(root / "public.md", "public")
    _write(root / "private" / "secret.md", "secret")
    _write(root / "notes.bak", "backup")

    options = ScanOptions(recursive=True, respect_ragignore=True, respect_gitignore=False)
    candidates, summary = scan_folder(str(root), options=options)

    rel_paths = [item.relative_path for item in candidates]
    assert rel_paths == ["public.md"]
    assert summary.skipped_by_reason.get("ignored") == 2

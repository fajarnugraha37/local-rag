from __future__ import annotations

import json
import os
import re
import sys
from typing import Sequence

from app.common.namespaces import DEFAULT_NAMESPACE, validate_namespace
from app.config import runtime_settings as settings
from app.ingestion.pipeline import build_options, ingest_paths, render_progress_line
from app.ingestion.vector_ingest_service import ingest_chunks


def chunk_sentences(text: str, max_chars: int = 1000) -> list[str]:
    max_chars = int(settings.CONFIG.get("chunk_max_chars", max_chars))
    sentences = re.split(r"(?<=[.!?]) +", text)
    chunks: list[str] = []
    current_chunk = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current_chunk} {sentence}".strip() if current_chunk else sentence
        if len(candidate) <= max_chars:
            current_chunk = candidate
            continue
        if current_chunk:
            chunks.append(current_chunk)
        current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _render_progress(prefix: str, current: int, total: int, *, width: int = 30) -> None:
    sys.stdout.write(render_progress_line(prefix, current, total, width=width))
    sys.stdout.flush()


def write_chunks_file(
    chunks_list,
    source_path,
    chunks_file=None,
    append_vault=False,
    show_progress: bool = True,
    namespace: str | None = None,
):
    total = len(chunks_list) if hasattr(chunks_list, "__len__") else 0
    progress_state = {"last_current": -1}

    def _on_progress(stage: str, current: int, progress_total: int, stats):
        if not show_progress:
            return
        if stage in {"start", "chunk"}:
            safe_total = progress_total or total or 1
            if current == progress_state["last_current"] and stage == "chunk":
                return
            progress_state["last_current"] = current
            _render_progress("Embedding + upsert", current, safe_total)
        elif stage == "done":
            safe_total = progress_total or total or max(1, current)
            _render_progress("Embedding + upsert", safe_total, safe_total)
            sys.stdout.write("\n")
            sys.stdout.flush()

    result = ingest_chunks(
        chunks_list,
        source_path=source_path,
        namespace=namespace,
        progress_callback=_on_progress if show_progress else None,
    )
    print(
        f"Wrote {result['added']} new chunks to vector DB (failed={result['failed']}, skipped={result['skipped']})"
    )
    return result


def _read_json_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    return re.sub(r"\s+", " ", json.dumps(data, ensure_ascii=False)).strip()


def _read_txt_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as txt_file:
        return re.sub(r"\s+", " ", txt_file.read()).strip()


def ingest_file_path(file_path: str, *, namespace: str | None = None):
    options = build_options()
    summary = ingest_paths([file_path], options=options, namespace=namespace)
    file_result = (
        summary["files"][0] if summary.get("files") else {"status": "skipped", "reason": "no_file"}
    )
    if file_result.get("status") == "ok":
        print(
            f"Ingested '{file_result['path']}' chunks={file_result.get('chunks_count', 0)} "
            f"warnings={len(file_result.get('warnings') or [])}"
        )
    else:
        reason = file_result.get("reason", "unknown")
        print(f"Skipped '{file_path}': {reason}")
    return file_result


def launch_gui() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        print("GUI components not available. Use --path to ingest from CLI.")
        return

    root = tk.Tk()
    root.title("Ingest files into Easy Local RAG")

    container = tk.Frame(root)
    container.pack(pady=12, padx=16, fill="x")

    namespace_label = tk.Label(container, text="Namespace")
    namespace_label.pack(anchor="w")

    namespace_var = tk.StringVar(value=DEFAULT_NAMESPACE)
    namespace_entry = tk.Entry(container, textvariable=namespace_var, width=48)
    namespace_entry.pack(anchor="w", fill="x", pady=(4, 12))

    def _get_namespace_or_show_error() -> str | None:
        raw_namespace = (namespace_var.get() or "").strip()
        try:
            # Empty input maps to default namespace.
            return validate_namespace(raw_namespace or None, default_to_default=True)
        except ValueError as exc:
            messagebox.showerror("Invalid namespace", str(exc))
            return None

    def select_and_ingest():
        namespace = _get_namespace_or_show_error()
        if namespace is None:
            return
        selected = filedialog.askopenfilenames(
            filetypes=[
                ("All Supported", "*.*"),
                ("Text", "*.txt *.md *.markdown *.mdx *.rst *.adoc *.asciidoc"),
                ("Config", "*.yaml *.yml *.toml *.ini *.conf *.env *.properties"),
                ("Data", "*.json *.jsonc *.jsonl *.ndjson *.csv *.tsv *.parquet *.ipynb"),
                ("Office", "*.pdf *.docx *.doc *.pptx *.ppt *.xlsx *.xls"),
            ]
        )
        if not selected:
            return
        run_ingestion(
            list(selected),
            recursive=False,
            include_patterns=[],
            exclude_patterns=[],
            namespace=namespace,
        )

    def select_folder_and_ingest():
        namespace = _get_namespace_or_show_error()
        if namespace is None:
            return
        selected = filedialog.askdirectory()
        if not selected:
            return
        run_ingestion(
            [selected],
            recursive=True,
            include_patterns=[],
            exclude_patterns=[],
            namespace=namespace,
        )

    upload_button = tk.Button(container, text="Select Files and Ingest", command=select_and_ingest)
    upload_button.pack(pady=(0, 12), fill="x")

    folder_button = tk.Button(
        container, text="Select Folder and Ingest (Recursive)", command=select_folder_and_ingest
    )
    folder_button.pack(pady=0, fill="x")

    root.mainloop()


def run_ingestion(
    paths: Sequence[str],
    *,
    recursive: bool,
    include_patterns: Sequence[str],
    exclude_patterns: Sequence[str],
    max_bytes: int | None = None,
    max_rows: int | None = None,
    max_pages: int | None = None,
    max_slides: int | None = None,
    max_sheets: int | None = None,
    fail_fast: bool = False,
    namespace: str | None = None,
):
    options = build_options(
        recursive=recursive,
        include_patterns=list(include_patterns),
        exclude_patterns=list(exclude_patterns),
        max_bytes=max_bytes
        if max_bytes is not None
        else settings.CONFIG.get("ingest_max_bytes", 8 * 1024 * 1024),
        max_rows=max_rows if max_rows is not None else settings.CONFIG.get("ingest_max_rows", 2000),
        max_pages=max_pages
        if max_pages is not None
        else settings.CONFIG.get("ingest_max_pages", 200),
        max_slides=max_slides
        if max_slides is not None
        else settings.CONFIG.get("ingest_max_slides", 300),
        max_sheets=max_sheets
        if max_sheets is not None
        else settings.CONFIG.get("ingest_max_sheets", 50),
    )

    progress_state = {"current_file": ""}

    def _on_progress(stage: str, current: int, total: int, stats):
        file_path = str((stats or {}).get("file_path") or "")
        if file_path and stage == "start" and file_path != progress_state["current_file"]:
            if progress_state["current_file"]:
                sys.stdout.write("\n")
            print(f"Ingesting '{file_path}'...")
            progress_state["current_file"] = file_path
        if stage in {"start", "chunk"}:
            label = "Embedding + upsert"
            if file_path:
                label = f"Embedding + upsert [{os.path.basename(file_path)}]"
            _render_progress(label, current, total)
        elif stage == "done":
            label = "Embedding + upsert"
            if file_path:
                label = f"Embedding + upsert [{os.path.basename(file_path)}]"
            _render_progress(label, total or current, total or current or 1)
            sys.stdout.write("\n")
            sys.stdout.flush()

    summary = ingest_paths(
        paths, options=options, progress_callback=_on_progress, namespace=namespace
    )
    for item in summary.get("files", []):
        status = item.get("status")
        line = (
            f"[{status}] {item.get('path')} chunks={item.get('chunks_count', 0)} "
            f"warnings={len(item.get('warnings') or [])} duration_ms={item.get('duration_ms', 0)}"
        )
        reason = item.get("reason")
        if reason:
            line += f" reason={reason}"
        print(line)
        if fail_fast and status == "failed":
            break

    print(
        "Summary: "
        f"total_files={summary.get('total_files', 0)} "
        f"extracted={summary.get('extracted', 0)} "
        f"skipped={summary.get('skipped', 0)} "
        f"failed={summary.get('failed', 0)} "
        f"total_chunks={summary.get('total_chunks', 0)}"
    )
    return summary


def main(argv: Sequence[str] | None = None):
    # Compatibility wrapper: CLI parsing now lives in app.cli.ingest_files.
    from app.cli.ingest_files import main as cli_main

    return cli_main(argv)

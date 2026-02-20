from __future__ import annotations

import argparse
import json
import os
import re
from typing import Sequence

from app.config import runtime_settings as settings
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


def write_chunks_file(chunks_list, source_path, chunks_file=None, append_vault=False):
    result = ingest_chunks(chunks_list, source_path=source_path)
    print(f"Wrote {result['added']} new chunks to vector DB (failed={result['failed']}, skipped={result['skipped']})")
    return result


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _read_pdf_text(path: str) -> str:
    try:
        import PyPDF2
    except Exception as exc:
        raise RuntimeError("PyPDF2 is required to ingest PDF files.") from exc

    with open(path, "rb") as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text_parts = []
        for page in pdf_reader.pages:
            extracted = page.extract_text() or ""
            if extracted:
                text_parts.append(extracted)
    return _normalize_text(" ".join(text_parts))


def _read_json_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    return _normalize_text(json.dumps(data, ensure_ascii=False))


def _read_txt_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as txt_file:
        return _normalize_text(txt_file.read())


def ingest_file_path(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    _, ext = os.path.splitext(file_path.lower())
    if ext == ".pdf":
        text = _read_pdf_text(file_path)
    elif ext == ".txt":
        text = _read_txt_text(file_path)
    elif ext == ".json":
        text = _read_json_text(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported: .pdf, .txt, .json")

    chunks = chunk_sentences(text, max_chars=1000)
    if not chunks:
        print(f"No content found for '{file_path}'. Nothing ingested.")
        return {"added": 0, "failed": 0, "skipped": 0}
    result = write_chunks_file(chunks, file_path)
    print(f"Processed {len(chunks)} chunks from '{file_path}'.")
    return result


def _launch_gui() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        print("GUI components not available. Use --path to ingest from CLI.")
        return

    def select_and_ingest(filetypes):
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if not file_path:
            return
        try:
            ingest_file_path(file_path)
        except Exception as exc:
            print(f"Failed to ingest '{file_path}': {exc}")

    root = tk.Tk()
    root.title("Upload .pdf, .txt, or .json")

    pdf_button = tk.Button(root, text="Upload PDF", command=lambda: select_and_ingest([("PDF Files", "*.pdf")]))
    pdf_button.pack(pady=10)

    txt_button = tk.Button(root, text="Upload Text File", command=lambda: select_and_ingest([("Text Files", "*.txt")]))
    txt_button.pack(pady=10)

    json_button = tk.Button(root, text="Upload JSON File", command=lambda: select_and_ingest([("JSON Files", "*.json")]))
    json_button.pack(pady=10)

    root.mainloop()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest PDF/TXT/JSON files into vector storage. Use --path for non-GUI mode.",
    )
    parser.add_argument(
        "--path",
        dest="paths",
        action="append",
        default=[],
        help="Path to .pdf/.txt/.json file. Repeat --path for multiple files.",
    )
    return parser


def main(argv: Sequence[str] | None = None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.paths:
        for path in args.paths:
            try:
                ingest_file_path(path)
            except Exception as exc:
                parser.error(str(exc))
        return
    _launch_gui()

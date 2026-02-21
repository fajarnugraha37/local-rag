from __future__ import annotations

from openai import OpenAI

from cmd.actions import ACTION_SPECS, run_action
from app.chat.citation_formatter import render_citation_output
from app.chat.citation_prompting import build_citation_prompt
from app.chat.streaming_llm_client import stream_chat_with_continuation
from app.common.namespaces import validate_namespace
from app.config import runtime_settings as settings
from app.http.server import create_streaming_handler, main as http_main
from app.ingestion.doc_registry_store import DocRegistryStore
from app.ingestion.folder_ingest_service import FolderIngestOptions, ingest_folder
from app.ingestion.pipeline import build_options, ingest_paths, ingest_uploaded_files
from app.ingestion.vector_ingest_service import delete_doc, ingest_chunks
from app.retrieval import hybrid_search as retrieval


def _deps_provider() -> dict:
    return {
        "ACTION_SPECS": ACTION_SPECS,
        "run_action": run_action,
        "validate_namespace": validate_namespace,
        "build_citation_prompt": build_citation_prompt,
        "render_citation_output": render_citation_output,
        "stream_chat_with_continuation": stream_chat_with_continuation,
        "settings": settings,
        "DocRegistryStore": DocRegistryStore,
        "delete_doc": delete_doc,
        "ingest_chunks": ingest_chunks,
        "FolderIngestOptions": FolderIngestOptions,
        "ingest_folder": ingest_folder,
        "build_options": build_options,
        "ingest_paths": ingest_paths,
        "ingest_uploaded_files": ingest_uploaded_files,
        "retrieval": retrieval,
        "OpenAI": OpenAI,
    }


StreamingHandler = create_streaming_handler(_deps_provider)


def main():
    http_main(StreamingHandler)

"""Shared action registry for centralized CLI/server launchers."""

from __future__ import annotations

import importlib
import sys
import threading
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence


@dataclass(frozen=True)
class ActionSpec:
    name: str
    target: str
    description: str


ACTION_SPECS: Dict[str, ActionSpec] = {
    "server": ActionSpec(
        name="server",
        target="app.chat.streaming_server:main",
        description="Start HTTP + SSE streaming server.",
    ),
    "chat": ActionSpec(
        name="chat",
        target="app.chat.document_chat_cli:main",
        description="Main document chat (rewrite + optional multi-pass).",
    ),
    "chat-baseline": ActionSpec(
        name="chat-baseline",
        target="app.chat.document_chat_baseline_cli:main",
        description="Baseline document chat (no rewrite).",
    ),
    "chat-email": ActionSpec(
        name="chat-email",
        target="app.chat.email_chat_cli:main",
        description="Email-focused chat CLI.",
    ),
    "ingest-files": ActionSpec(
        name="ingest-files",
        target="app.ingestion.file_ingest_gui:main",
        description="Ingest many document/config/data formats (--path non-GUI, no --path opens GUI).",
    ),
    "ingest-folder": ActionSpec(
        name="ingest-folder",
        target="app.ingestion.folder_ingest_cli:main",
        description="Scan and ingest an entire folder recursively with ignore rules + idempotency.",
    ),
    "list-docs": ActionSpec(
        name="list-docs",
        target="app.ingestion.list_docs_cli:main",
        description="List ingested documents from registry (optionally by namespace).",
    ),
    "delete-doc": ActionSpec(
        name="delete-doc",
        target="app.ingestion.delete_doc_cli:main",
        description="Delete ingested document by doc_id (default namespace or all namespaces).",
    ),
    "ingest-email": ActionSpec(
        name="ingest-email",
        target="app.ingestion.email_ingest_job:main",
        description="Ingest emails from IMAP sources.",
    ),
    "migrate-vault": ActionSpec(
        name="migrate-vault",
        target="app.migration.vault_migration:main",
        description="Migrate legacy vault.txt into vector DB.",
    ),
    "backfill-vectors": ActionSpec(
        name="backfill-vectors",
        target="app.migration.backfill_vector_db:main",
        description="Backfill legacy chunks/embeddings JSONL into vector DB.",
    ),
    "query": ActionSpec(
        name="query",
        target="app.retrieval.hybrid_search:main",
        description="Run hybrid retrieval query and print JSON results.",
    ),
    "validate-phase4": ActionSpec(
        name="validate-phase4",
        target="app.validation.phase4_validation_cli:main",
        description="Run phase-4 retrieval/context validation script.",
    ),
    "debug-retrieval": ActionSpec(
        name="debug-retrieval",
        target="app.tools.retrieval_debug_cli:main",
        description="Run retrieval debug harness against a test collection.",
    ),
    "eval": ActionSpec(
        name="eval",
        target="eval.run_eval:main",
        description="Run retrieval evaluation metrics suite.",
    ),
}
_RUN_ACTION_LOCK = threading.Lock()


def list_actions() -> List[ActionSpec]:
    return [ACTION_SPECS[name] for name in sorted(ACTION_SPECS)]


def _load_callable(target: str) -> Callable[[], None]:
    module_name, func_name = target.split(":", 1)
    module = importlib.import_module(module_name)
    func = getattr(module, func_name, None)
    if func is None or not callable(func):
        raise RuntimeError(f"Invalid action target: {target}")
    return func


def run_action(action_name: str, action_args: Sequence[str]) -> int:
    spec = ACTION_SPECS.get(action_name)
    if spec is None:
        valid = ", ".join(sorted(ACTION_SPECS))
        print(f"Unknown action '{action_name}'. Valid actions: {valid}", file=sys.stderr)
        return 2

    with _RUN_ACTION_LOCK:
        target_func = _load_callable(spec.target)
        old_argv = sys.argv
        sys.argv = [f"{action_name}.py", *action_args]
        try:
            target_func()
            return 0
        except SystemExit as exc:
            code = exc.code
            if code is None:
                return 0
            if isinstance(code, int):
                return code
            return 1
        finally:
            sys.argv = old_argv


def format_actions_table() -> str:
    lines = ["Available actions:"]
    for spec in list_actions():
        lines.append(f"  {spec.name:<16} {spec.description}")
    return "\n".join(lines)

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.repositories.sqlite.db import init_db


def _check_sqlite(config: dict[str, Any]) -> tuple[bool, str]:
    db_path = str(config.get("sqlite_db_path") or "data/app.db")
    try:
        init_db(db_path)
    except Exception as exc:
        return False, f"sqlite init failed: {exc}"
    return True, f"sqlite ready ({db_path})"


def _check_vector_store(config: dict[str, Any]) -> tuple[bool, str]:
    provider = str(config.get("vector_db_provider") or "chroma")
    if provider != "chroma":
        return True, f"vector provider '{provider}' not probed"

    persist_dir = Path(str(config.get("vector_db_persist_dir") or "data/chroma"))
    try:
        persist_dir.mkdir(parents=True, exist_ok=True)
        probe = persist_dir / ".readyz_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        return False, f"vector store path not writable: {exc}"
    return True, f"vector store ready ({persist_dir})"


def _check_reranker() -> tuple[bool, str]:
    try:
        from app.retrieval import heuristic_reranker as reranker  # noqa: PLC0415
    except Exception as exc:
        return False, f"reranker import failed: {exc}"
    if not hasattr(reranker, "rerank"):
        return False, "reranker missing rerank()"
    return True, "reranker ready"


def run_readiness_checks(config: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "sqlite": _check_sqlite(config),
        "vector_db": _check_vector_store(config),
        "reranker": _check_reranker(),
    }
    components = {name: {"ok": ok, "detail": detail} for name, (ok, detail) in checks.items()}
    ok = all(item["ok"] for item in components.values())
    return {"ok": ok, "components": components}

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import time
import uuid
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from openai import OpenAI

from cmd.actions import ACTION_SPECS, run_action
from app.chat.citation_formatter import render_citation_output
from app.chat.citation_prompting import build_citation_prompt
from app.chat.streaming_llm_client import stream_chat_with_continuation
from app.common.namespaces import validate_namespace
from app.config import runtime_settings as settings
from app.http.utils import parse_bool
from app.http.sse_utils import to_sse
from app.ingestion.doc_registry_store import DocRegistryStore
from app.ingestion.folder_ingest_service import FolderIngestOptions, ingest_folder
from app.ingestion.pipeline import build_options, ingest_paths, ingest_uploaded_files
from app.ingestion.vector_ingest_service import delete_doc, ingest_chunks
from app.retrieval import hybrid_search as retrieval

router = APIRouter(tags=["legacy"])
HTTP_ACTION_EXCLUDE = {"chat", "chat-baseline", "chat-email", "ingest-files", "server"}


def get_http_actions(action_specs: dict) -> list[str]:
    return sorted(name for name in action_specs if name not in HTTP_ACTION_EXCLUDE)


def _get_relevant_context(query: str, top_k: int):
    try:
        return retrieval.scored_chunks(query, top_k=top_k)
    except Exception:
        return []


def _build_messages(question: str, top_k: int):
    retrieved_chunks = _get_relevant_context(question, top_k=top_k)
    user_text, source_blocks = build_citation_prompt(
        question,
        retrieved_chunks,
        max_sources=top_k,
        max_snippet_chars=int(settings.CONFIG.get("citation_max_snippet_chars", 500)),
    )
    system_message = settings.CONFIG.get(
        "system_message",
        "You are a helpful assistant that is an expert at extracting the most useful information from a given text.",
    )
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_text},
    ], source_blocks


def _resolve_allowed_roots() -> list[str]:
    raw = settings.CONFIG.get("ingest_allowed_roots")
    if raw is None:
        return []
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = [item for item in raw if isinstance(item, str)]
    else:
        return []
    return [item for item in (value.strip() for value in values) if item]


def _is_safe_folder_path(path: str) -> tuple[bool, str]:
    raw = re.sub(r"\s+", " ", path or "").strip()
    if not raw:
        return False, "path is required"
    try:
        abs_path = os.path.abspath(raw)
    except Exception:
        return False, "invalid path"
    normalized_abs = os.path.normpath(abs_path)
    if os.path.dirname(normalized_abs) == normalized_abs:
        return False, "scanning filesystem root is not allowed"
    allowed_roots = _resolve_allowed_roots()
    if not allowed_roots:
        return True, ""
    normalized = os.path.normcase(normalized_abs)
    for root in allowed_roots:
        candidate = os.path.normcase(os.path.abspath(root))
        if normalized == candidate or normalized.startswith(candidate + os.sep):
            return True, ""
    return False, "path is outside configured allowed roots"


def _chunk_text_for_ingest(text: str, max_chars: int) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?]) +", normalized)
    chunks = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
            continue
        if current:
            chunks.append(current)
        current = sentence
    if current:
        chunks.append(current)
    return chunks


def _extract_sources(results: list[dict], max_sources: int = 8) -> list[dict]:
    sources: list[dict] = []
    seen = set()
    for row in results:
        src = row.get("source")
        if not isinstance(src, dict):
            continue
        idx = src.get("citation_index")
        key = (idx, src.get("doc_id"), src.get("path"))
        if key in seen:
            continue
        seen.add(key)
        sources.append(src)
        if len(sources) >= max_sources:
            break
    return sources


def _build_retrieval_answer(sources: list[dict]) -> str:
    if not sources:
        return "No relevant sources found."
    lines = ["Retrieved relevant sources:"]
    for src in sources:
        idx = src.get("citation_index")
        title = src.get("title") or src.get("doc_id") or "Untitled"
        snippet = str(src.get("snippet") or "").strip()
        if snippet:
            lines.append(f"- {title}: {snippet} [{idx}]")
        else:
            lines.append(f"- {title} [{idx}]")
    return "\n".join(lines)


def _ok(status: int = 200, **payload: Any) -> JSONResponse:
    body = {"ok": True}
    body.update(payload)
    return JSONResponse(status_code=status, content=body)


def _err(status: int, message: str, **payload: Any) -> JSONResponse:
    body = {"ok": False, "error": message}
    body.update(payload)
    return JSONResponse(status_code=status, content=body)


async def _read_json_object(request: Request) -> dict[str, Any]:
    raw_body = await request.body()
    if not raw_body:
        raise ValueError("empty request body")
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid JSON body: {exc}") from exc
    if not isinstance(body, dict):
        raise ValueError("JSON body must be an object")
    return body


@router.get("/actions")
@router.get("/action")
def actions_get() -> JSONResponse:
    http_actions = get_http_actions(ACTION_SPECS)
    actions = []
    for name in sorted(ACTION_SPECS):
        spec = ACTION_SPECS[name]
        actions.append(
            {
                "name": spec.name,
                "description": spec.description,
                "http_supported": spec.name in http_actions,
            }
        )
    return JSONResponse(
        status_code=200,
        content={
            "actions": actions,
            "http_supported_actions": http_actions,
            "notes": {
                "run_endpoint": "POST /actions/run",
                "interactive_actions_blocked": sorted(HTTP_ACTION_EXCLUDE),
            },
        },
    )


@router.post("/actions/run")
@router.post("/action/run")
async def actions_run(request: Request) -> JSONResponse:
    try:
        body = await _read_json_object(request)
    except ValueError as exc:
        return _err(400, str(exc))

    action = (body.get("action") or "").strip()
    action_args = body.get("args") or []
    http_actions = get_http_actions(ACTION_SPECS)
    if action not in http_actions:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": "unsupported action for HTTP execution",
                "allowed_actions": http_actions,
            },
        )
    if not isinstance(action_args, list) or any(not isinstance(v, str) for v in action_args):
        return _err(400, "'args' must be an array of strings")

    started = time.monotonic()
    out_buffer = io.StringIO()
    err_buffer = io.StringIO()
    with contextlib.redirect_stdout(out_buffer), contextlib.redirect_stderr(err_buffer):
        exit_code = run_action(action, action_args)
    result = {
        "action": action,
        "args": action_args,
        "exit_code": exit_code,
        "stdout": out_buffer.getvalue(),
        "stderr": err_buffer.getvalue(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
    return JSONResponse(status_code=200, content={"ok": result["exit_code"] == 0, "result": result})


@router.get("/docs")
def docs_get(request: Request) -> JSONResponse:
    query = request.query_params
    namespace_raw = query.get("namespace")
    cursor = query.get("cursor")
    try:
        limit = int(query.get("limit", "50"))
    except (TypeError, ValueError):
        return _err(400, "'limit' must be an integer")
    try:
        namespace = (
            validate_namespace(namespace_raw, default_to_default=True)
            if namespace_raw is not None
            else None
        )
    except ValueError as exc:
        return _err(400, str(exc))

    store = DocRegistryStore(str(settings.CONFIG.get("doc_registry_path", "data/doc_registry.json")))
    payload = store.list_docs(namespace=namespace, limit=limit, cursor=cursor)
    return JSONResponse(status_code=200, content={"ok": True, **payload})


@router.delete("/docs/{doc_id}")
def docs_delete(doc_id: str, request: Request) -> JSONResponse:
    if not doc_id:
        return _err(400, "'doc_id' is required")

    query = request.query_params
    all_namespaces = parse_bool(query.get("all_namespaces", "false"), default=False)
    namespace_raw = query.get("namespace")

    if all_namespaces:
        namespace = None
    else:
        try:
            namespace = validate_namespace(namespace_raw, default_to_default=True)
        except ValueError as exc:
            return _err(400, str(exc))

    vectors_deleted = delete_doc(doc_id, namespace=namespace, all_namespaces=all_namespaces)
    registry_store = DocRegistryStore(str(settings.CONFIG.get("doc_registry_path", "data/doc_registry.json")))
    registry_deleted = 0
    if all_namespaces:
        page = registry_store.list_docs(limit=100000)
        for row in page.get("records", []):
            if str(row.get("doc_id")) != str(doc_id):
                continue
            if registry_store.delete(str(row.get("namespace")), str(doc_id)):
                registry_deleted += 1
    else:
        registry_deleted = 1 if registry_store.delete(str(namespace), str(doc_id)) else 0
    if registry_deleted > 0:
        registry_store.save()

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "doc_id": doc_id,
            "namespace": namespace,
            "all_namespaces": all_namespaces,
            "vectors_deleted": int(vectors_deleted),
            "registry_deleted": int(registry_deleted),
            "not_found": (vectors_deleted == 0 and registry_deleted == 0),
        },
    )


@router.get("/chat/stream")
async def chat_stream(request: Request) -> Response:
    query = parse_qs(request.url.query)
    question = (query.get("question") or [""])[0].strip()
    if not question:
        return Response(content="Missing required query parameter: question", status_code=400)

    try:
        model = (query.get("model") or [settings.CONFIG.get("ollama_model", "llama3")])[0]
        top_k = int((query.get("top_k") or [settings.CONFIG.get("top_k", 3)])[0])
        max_continuations = int(
            (query.get("max_continuations") or [settings.CONFIG.get("max_continuations", 2)])[0]
        )
        per_call_max_tokens = int(
            (
                query.get("per_call_max_tokens")
                or [
                    settings.CONFIG.get(
                        "per_call_max_tokens", settings.CONFIG.get("chat_max_tokens", 4000)
                    )
                ]
            )[0]
        )
    except ValueError:
        return Response(content="Invalid numeric query parameter", status_code=400)

    enable_thinking_summary_raw = (
        (query.get("enable_thinking_summary") or ["false"])[0].strip().lower()
    )
    enable_thinking_summary = enable_thinking_summary_raw in {"1", "true", "yes", "on"}

    timeout = settings.CONFIG.get("provider_timeout_s", settings.CONFIG.get("model_timeout", 120))
    flush_interval_ms = settings.CONFIG.get("flush_interval_ms", 250)
    continuation_instruction = settings.CONFIG.get(
        "continuation_instruction",
        "Continue exactly where you left off. Do not repeat prior text.",
    )

    client = OpenAI(
        base_url=settings.CONFIG.get("ollama_api", {}).get("base_url", "http://localhost:11434/v1"),
        api_key=settings.CONFIG.get("ollama_api", {}).get("api_key"),
    )
    messages, source_blocks = _build_messages(question=question, top_k=top_k)

    def event_iter():
        try:
            for event in stream_chat_with_continuation(
                client,
                model=model,
                messages=messages,
                per_call_max_tokens=per_call_max_tokens,
                continuation_instruction=continuation_instruction,
                max_continuations=max_continuations,
                timeout=timeout,
                flush_interval_ms=flush_interval_ms,
                enable_thinking_summary=enable_thinking_summary,
            ):
                name = event.get("event", "message")
                payload = event.get("data", {})
                if name == "done":
                    yield to_sse("sources", {"sources": source_blocks})
                    if source_blocks:
                        stats_payload = render_citation_output(
                            payload.get("text", ""),
                            source_blocks,
                            mode="inline",
                            max_sources=int(settings.CONFIG.get("citation_max_sources", top_k)),
                            max_snippet_chars=int(
                                settings.CONFIG.get("citation_max_snippet_chars", 240)
                            ),
                        ).get("stats", {})
                        yield to_sse("citation_stats", {"stats": stats_payload})
                yield to_sse(name, payload)
        except Exception as exc:
            yield to_sse("error", {"message": "server_stream_error", "detail": str(exc)})
            yield to_sse("done", {"cancelled": True})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "close",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_iter(), media_type="text/event-stream; charset=utf-8", headers=headers)


@router.post("/ingest/chunks")
async def ingest_chunks_endpoint(request: Request) -> JSONResponse:
    try:
        body = await _read_json_object(request)
    except ValueError as exc:
        return _err(400, str(exc))
    chunks = body.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        return _err(400, "'chunks' must be a non-empty array")
    try:
        namespace = validate_namespace(body.get("namespace"), default_to_default=True)
    except ValueError as exc:
        return _err(400, str(exc))
    result = ingest_chunks(
        chunks,
        source_path=body.get("source_path"),
        doc_id=body.get("doc_id"),
        namespace=namespace,
        embedding_model=body.get("embedding_model"),
    )
    return _ok(result=result)


@router.post("/ingest/text")
async def ingest_text_endpoint(request: Request) -> JSONResponse:
    try:
        body = await _read_json_object(request)
    except ValueError as exc:
        return _err(400, str(exc))
    text = (body.get("text") or "").strip()
    if not text:
        return _err(400, "'text' is required")
    try:
        max_chars = int(body.get("max_chars") or settings.CONFIG.get("chunk_max_chars", 1000))
    except (TypeError, ValueError):
        return _err(400, "'max_chars' must be an integer")
    chunks = _chunk_text_for_ingest(text, max_chars=max(1, max_chars))
    try:
        namespace = validate_namespace(body.get("namespace"), default_to_default=True)
    except ValueError as exc:
        return _err(400, str(exc))
    result = ingest_chunks(
        chunks,
        source_path=body.get("source_path"),
        doc_id=body.get("doc_id"),
        namespace=namespace,
        embedding_model=body.get("embedding_model"),
    )
    return _ok(chunk_count=len(chunks), result=result)


@router.post("/ingest/files")
@router.post("/ingestion/files")
async def ingest_files_endpoint(request: Request) -> JSONResponse:
    try:
        body = await _read_json_object(request)
    except ValueError as exc:
        return _err(400, str(exc))
    paths = body.get("paths")
    if not isinstance(paths, list) or not paths or any(not isinstance(v, str) for v in paths):
        return _err(400, "'paths' must be a non-empty array of strings")
    include_patterns = body.get("include") or []
    exclude_patterns = body.get("exclude") or []
    if not isinstance(include_patterns, list) or any(not isinstance(v, str) for v in include_patterns):
        return _err(400, "'include' must be an array of strings")
    if not isinstance(exclude_patterns, list) or any(not isinstance(v, str) for v in exclude_patterns):
        return _err(400, "'exclude' must be an array of strings")
    try:
        namespace = validate_namespace(body.get("namespace"), default_to_default=True)
    except ValueError as exc:
        return _err(400, str(exc))

    options = build_options(
        recursive=parse_bool(body.get("recursive"), default=False),
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        max_bytes=body.get("max_bytes", settings.CONFIG.get("ingest_max_bytes", 8 * 1024 * 1024)),
        max_rows=body.get("max_rows", settings.CONFIG.get("ingest_max_rows", 2000)),
        max_pages=body.get("max_pages", settings.CONFIG.get("ingest_max_pages", 200)),
        max_slides=body.get("max_slides", settings.CONFIG.get("ingest_max_slides", 300)),
        max_sheets=body.get("max_sheets", settings.CONFIG.get("ingest_max_sheets", 50)),
    )
    summary = ingest_paths(
        paths,
        options=options,
        embedding_model=body.get("embedding_model"),
        namespace=namespace,
    )
    return _ok(summary=summary)


@router.post("/ingest/folder")
async def ingest_folder_endpoint(request: Request) -> Response:
    try:
        body = await _read_json_object(request)
    except ValueError as exc:
        return _err(400, str(exc))

    folder_path = str(body.get("path") or "").strip()
    is_safe, safety_reason = _is_safe_folder_path(folder_path)
    if not is_safe:
        return _err(400, safety_reason)

    include_patterns = body.get("include") or []
    exclude_patterns = body.get("exclude") or []
    if not isinstance(include_patterns, list) or any(not isinstance(v, str) for v in include_patterns):
        return _err(400, "'include' must be an array of strings")
    if not isinstance(exclude_patterns, list) or any(not isinstance(v, str) for v in exclude_patterns):
        return _err(400, "'exclude' must be an array of strings")

    request_id = str(body.get("request_id") or uuid.uuid4())
    stream = parse_bool(body.get("stream"), default=False)
    recursive = parse_bool(body.get("recursive"), default=True)
    dry_run = parse_bool(body.get("dry_run"), default=False)
    force = parse_bool(body.get("force"), default=False)
    respect_gitignore = parse_bool(body.get("respect_gitignore"), default=True)
    try:
        namespace = validate_namespace(body.get("namespace"), default_to_default=True)
    except ValueError as exc:
        return _err(400, str(exc))

    folder_opts = FolderIngestOptions(
        path=folder_path,
        recursive=recursive,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        respect_gitignore=respect_gitignore,
        dry_run=dry_run,
        force=force,
        embedding_model=body.get("embedding_model"),
        namespace=namespace,
    )

    if stream:

        def event_iter():
            def _on_progress(event_name: str, payload: dict):
                mapped_name = "file_skipped" if event_name == "file_planned" else event_name
                packet = dict(payload or {})
                packet["request_id"] = request_id
                events.append(to_sse(mapped_name, packet))

            events: list[bytes] = []
            try:
                folder_opts.progress_callback = _on_progress
                summary = ingest_folder(folder_opts)
                for event in events:
                    yield event
                yield to_sse("done", {"ok": True, "summary": summary, "request_id": request_id})
            except Exception as exc:
                for event in events:
                    yield event
                yield to_sse("error", {"message": str(exc), "request_id": request_id})
                yield to_sse("done", {"ok": False, "request_id": request_id})

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "close",
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(
            event_iter(), media_type="text/event-stream; charset=utf-8", headers=headers
        )

    try:
        summary = ingest_folder(folder_opts)
        return _ok(request_id=request_id, summary=summary)
    except Exception as exc:
        return _err(500, str(exc), request_id=request_id)


@router.post("/ingest/upload")
@router.post("/ingestion/upload")
async def ingest_upload_endpoint(request: Request) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return _err(400, "Content-Type must be multipart/form-data")

    form = await request.form()
    uploaded: list[tuple[str, bytes]] = []
    fields: dict[str, str] = {}
    for key, value in form.multi_items():
        if hasattr(value, "filename") and hasattr(value, "read"):
            if key == "file" and getattr(value, "filename", None):
                content = await value.read()
                uploaded.append((str(value.filename), content))
        else:
            fields[key] = str(value)

    if not uploaded:
        return _err(400, "No file uploads provided under form field 'file'")

    try:
        namespace = validate_namespace(fields.get("namespace"), default_to_default=True)
    except ValueError as exc:
        return _err(400, str(exc))

    options = build_options(
        max_bytes=fields.get("max_bytes", settings.CONFIG.get("ingest_max_bytes", 8 * 1024 * 1024)),
        max_rows=fields.get("max_rows", settings.CONFIG.get("ingest_max_rows", 2000)),
        max_pages=fields.get("max_pages", settings.CONFIG.get("ingest_max_pages", 200)),
        max_slides=fields.get("max_slides", settings.CONFIG.get("ingest_max_slides", 300)),
        max_sheets=fields.get("max_sheets", settings.CONFIG.get("ingest_max_sheets", 50)),
    )
    summary = ingest_uploaded_files(
        uploaded,
        options=options,
        embedding_model=fields.get("embedding_model"),
        namespace=namespace,
    )
    return _ok(summary=summary)


@router.post("/vectors/delete-doc")
async def vectors_delete_doc_endpoint(request: Request) -> JSONResponse:
    try:
        body = await _read_json_object(request)
    except ValueError as exc:
        return _err(400, str(exc))
    doc_id = (body.get("doc_id") or "").strip()
    if not doc_id:
        return _err(400, "'doc_id' is required")
    deleted = delete_doc(doc_id)
    return _ok(doc_id=doc_id, deleted=deleted)


@router.post("/retrieval/query")
async def retrieval_query_endpoint(request: Request) -> JSONResponse:
    try:
        body = await _read_json_object(request)
    except ValueError as exc:
        return _err(400, str(exc))
    query_text = (body.get("query") or "").strip()
    if not query_text:
        return _err(400, "'query' is required")
    try:
        top_k = int(body.get("top_k") or settings.CONFIG.get("top_k", 6))
    except (TypeError, ValueError):
        return _err(400, "'top_k' must be an integer")
    rerank = parse_bool(body.get("rerank"), default=True)
    filters = body.get("filters")
    if filters is not None and not isinstance(filters, dict):
        return _err(400, "'filters' must be an object")

    results = retrieval.scored_chunks(query_text, top_k=top_k, rerank=rerank, filters=filters)
    max_sources = int(settings.CONFIG.get("citation_max_sources", top_k))
    max_snippet_chars = int(settings.CONFIG.get("citation_max_snippet_chars", 240))
    sources = _extract_sources(results, max_sources=max_sources)
    answer = _build_retrieval_answer(sources)
    rendered = render_citation_output(
        answer,
        sources,
        mode="inline",
        max_sources=max_sources,
        max_snippet_chars=max_snippet_chars,
    )
    return _ok(
        count=len(results),
        results=results,
        answer=rendered.get("answer", answer),
        sources=sources,
        citation_stats=rendered.get("stats", {}),
    )


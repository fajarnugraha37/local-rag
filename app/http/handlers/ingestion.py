from __future__ import annotations

import contextlib
import io
import os
import re
import time
import uuid
from http import HTTPStatus
from urllib.parse import parse_qs

from app.http.request_parsing import parse_bool, parse_multipart_upload, read_json
from app.http.sse import to_sse


def _resolve_allowed_roots(settings) -> list[str]:
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


def _is_safe_folder_path(settings, path: str) -> tuple[bool, str]:
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
    allowed_roots = _resolve_allowed_roots(settings)
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


def handle_ingestion_post(handler, deps, parsed) -> bool:
    settings = deps["settings"]
    validate_namespace = deps["validate_namespace"]

    if parsed.path == "/ingest/chunks":
        try:
            body = read_json(handler)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        chunks = body.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'chunks' must be a non-empty array"})
            return True
        try:
            namespace = validate_namespace(body.get("namespace"), default_to_default=True)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        try:
            result = deps["ingest_chunks"](
                chunks,
                source_path=body.get("source_path"),
                doc_id=body.get("doc_id"),
                namespace=namespace,
                embedding_model=body.get("embedding_model"),
            )
            handler.send_json(HTTPStatus.OK, {"ok": True, "result": result})
        except Exception as exc:
            handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        return True

    if parsed.path == "/ingest/text":
        try:
            body = read_json(handler)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        text = (body.get("text") or "").strip()
        if not text:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'text' is required"})
            return True
        try:
            max_chars = int(body.get("max_chars") or settings.CONFIG.get("chunk_max_chars", 1000))
        except (TypeError, ValueError):
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'max_chars' must be an integer"})
            return True
        chunks = _chunk_text_for_ingest(text, max_chars=max(1, max_chars))
        try:
            namespace = validate_namespace(body.get("namespace"), default_to_default=True)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        try:
            result = deps["ingest_chunks"](
                chunks,
                source_path=body.get("source_path"),
                doc_id=body.get("doc_id"),
                namespace=namespace,
                embedding_model=body.get("embedding_model"),
            )
            handler.send_json(HTTPStatus.OK, {"ok": True, "chunk_count": len(chunks), "result": result})
        except Exception as exc:
            handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        return True

    if parsed.path in {"/ingest/files", "/ingestion/files"}:
        try:
            body = read_json(handler)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        paths = body.get("paths")
        if not isinstance(paths, list) or not paths or any(not isinstance(value, str) for value in paths):
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'paths' must be a non-empty array of strings"})
            return True
        include_patterns = body.get("include") or []
        exclude_patterns = body.get("exclude") or []
        if not isinstance(include_patterns, list) or any(not isinstance(value, str) for value in include_patterns):
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'include' must be an array of strings"})
            return True
        if not isinstance(exclude_patterns, list) or any(not isinstance(value, str) for value in exclude_patterns):
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'exclude' must be an array of strings"})
            return True
        try:
            namespace = validate_namespace(body.get("namespace"), default_to_default=True)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        options = deps["build_options"](
            recursive=parse_bool(body.get("recursive"), default=False),
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            max_bytes=body.get("max_bytes", settings.CONFIG.get("ingest_max_bytes", 8 * 1024 * 1024)),
            max_rows=body.get("max_rows", settings.CONFIG.get("ingest_max_rows", 2000)),
            max_pages=body.get("max_pages", settings.CONFIG.get("ingest_max_pages", 200)),
            max_slides=body.get("max_slides", settings.CONFIG.get("ingest_max_slides", 300)),
            max_sheets=body.get("max_sheets", settings.CONFIG.get("ingest_max_sheets", 50)),
        )
        try:
            summary = deps["ingest_paths"](
                paths,
                options=options,
                embedding_model=body.get("embedding_model"),
                namespace=namespace,
            )
            handler.send_json(HTTPStatus.OK, {"ok": True, "summary": summary})
        except Exception as exc:
            handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        return True

    if parsed.path == "/ingest/folder":
        try:
            body = read_json(handler)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        folder_path = str(body.get("path") or "").strip()
        is_safe, safety_reason = _is_safe_folder_path(settings, folder_path)
        if not is_safe:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": safety_reason})
            return True

        include_patterns = body.get("include") or []
        exclude_patterns = body.get("exclude") or []
        if not isinstance(include_patterns, list) or any(not isinstance(value, str) for value in include_patterns):
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'include' must be an array of strings"})
            return True
        if not isinstance(exclude_patterns, list) or any(not isinstance(value, str) for value in exclude_patterns):
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'exclude' must be an array of strings"})
            return True

        request_id = str(body.get("request_id") or uuid.uuid4())
        stream = parse_bool(body.get("stream"), default=False)
        recursive = parse_bool(body.get("recursive"), default=True)
        dry_run = parse_bool(body.get("dry_run"), default=False)
        force = parse_bool(body.get("force"), default=False)
        respect_gitignore = parse_bool(body.get("respect_gitignore"), default=True)
        try:
            namespace = validate_namespace(body.get("namespace"), default_to_default=True)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True

        folder_options_cls = deps["FolderIngestOptions"]

        if stream:
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
            handler.send_header("Cache-Control", "no-cache")
            handler.send_header("Connection", "close")
            handler.send_header("X-Accel-Buffering", "no")
            handler.end_headers()

            def _emit(event_name: str, payload: dict):
                packet = dict(payload or {})
                packet["request_id"] = request_id
                handler.wfile.write(to_sse(event_name, packet))
                handler.wfile.flush()

            try:
                def _on_progress(event_name: str, payload: dict):
                    mapped_name = "file_skipped" if event_name == "file_planned" else event_name
                    _emit(mapped_name, payload)

                summary = deps["ingest_folder"](
                    folder_options_cls(
                        path=folder_path,
                        recursive=recursive,
                        include_patterns=include_patterns,
                        exclude_patterns=exclude_patterns,
                        respect_gitignore=respect_gitignore,
                        dry_run=dry_run,
                        force=force,
                        embedding_model=body.get("embedding_model"),
                        namespace=namespace,
                        progress_callback=_on_progress,
                    )
                )
                _emit("done", {"ok": True, "summary": summary})
            except (BrokenPipeError, ConnectionResetError):
                return True
            except Exception as exc:
                try:
                    _emit("error", {"message": str(exc)})
                    _emit("done", {"ok": False})
                except Exception:
                    pass
            return True

        try:
            summary = deps["ingest_folder"](
                folder_options_cls(
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
            )
            handler.send_json(HTTPStatus.OK, {"ok": True, "request_id": request_id, "summary": summary})
        except Exception as exc:
            handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "request_id": request_id, "error": str(exc)})
        return True

    if parsed.path in {"/ingest/upload", "/ingestion/upload"}:
        content_type = handler.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Content-Type must be multipart/form-data"})
            return True
        raw_len = handler.headers.get("Content-Length", "0")
        try:
            content_len = int(raw_len)
        except ValueError:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid Content-Length"})
            return True
        if content_len <= 0:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "empty multipart body"})
            return True
        raw_body = handler.rfile.read(content_len)
        try:
            uploaded, fields = parse_multipart_upload(content_type, raw_body)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        if not uploaded:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "No file uploads provided under form field 'file'"})
            return True
        try:
            namespace = validate_namespace(fields.get("namespace"), default_to_default=True)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        options = deps["build_options"](
            max_bytes=fields.get("max_bytes", settings.CONFIG.get("ingest_max_bytes", 8 * 1024 * 1024)),
            max_rows=fields.get("max_rows", settings.CONFIG.get("ingest_max_rows", 2000)),
            max_pages=fields.get("max_pages", settings.CONFIG.get("ingest_max_pages", 200)),
            max_slides=fields.get("max_slides", settings.CONFIG.get("ingest_max_slides", 300)),
            max_sheets=fields.get("max_sheets", settings.CONFIG.get("ingest_max_sheets", 50)),
        )
        try:
            summary = deps["ingest_uploaded_files"](
                uploaded,
                options=options,
                embedding_model=fields.get("embedding_model"),
                namespace=namespace,
            )
            handler.send_json(HTTPStatus.OK, {"ok": True, "summary": summary})
        except Exception as exc:
            handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        return True

    if parsed.path == "/vectors/delete-doc":
        try:
            body = read_json(handler)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        doc_id = (body.get("doc_id") or "").strip()
        if not doc_id:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'doc_id' is required"})
            return True
        try:
            deleted = deps["delete_doc"](doc_id)
            handler.send_json(HTTPStatus.OK, {"ok": True, "doc_id": doc_id, "deleted": deleted})
        except Exception as exc:
            handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        return True

    if parsed.path == "/retrieval/query":
        try:
            body = read_json(handler)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True
        query_text = (body.get("query") or "").strip()
        if not query_text:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'query' is required"})
            return True
        try:
            top_k = int(body.get("top_k") or settings.CONFIG.get("top_k", 6))
        except (TypeError, ValueError):
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'top_k' must be an integer"})
            return True
        rerank = parse_bool(body.get("rerank"), default=True)
        filters = body.get("filters")
        if filters is not None and not isinstance(filters, dict):
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'filters' must be an object"})
            return True
        try:
            results = deps["retrieval"].scored_chunks(query_text, top_k=top_k, rerank=rerank, filters=filters)
            max_sources = int(settings.CONFIG.get("citation_max_sources", top_k))
            max_snippet_chars = int(settings.CONFIG.get("citation_max_snippet_chars", 240))
            sources = _extract_sources(results, max_sources=max_sources)
            answer = _build_retrieval_answer(sources)
            rendered = deps["render_citation_output"](
                answer,
                sources,
                mode="inline",
                max_sources=max_sources,
                max_snippet_chars=max_snippet_chars,
            )
            handler.send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "count": len(results),
                    "results": results,
                    "answer": rendered.get("answer", answer),
                    "sources": sources,
                    "citation_stats": rendered.get("stats", {}),
                },
            )
        except Exception as exc:
            handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        return True

    return False

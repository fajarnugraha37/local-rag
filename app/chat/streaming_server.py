import argparse
import contextlib
import io
import json
import os
import re
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from openai import OpenAI

from cmd.actions import ACTION_SPECS, run_action
from app.common.namespaces import validate_namespace
from app.chat.streaming_llm_client import stream_chat_with_continuation
from app.config import runtime_settings as settings
from app.context import token_budget_packer as context_packer
from app.ingestion.doc_registry_store import DocRegistryStore
from app.ingestion.vector_ingest_service import delete_doc, ingest_chunks
from app.ingestion.folder_ingest_service import FolderIngestOptions, ingest_folder
from app.ingestion.pipeline import build_options, ingest_paths, ingest_uploaded_files
from app.retrieval import hybrid_search as retrieval


HTTP_ACTION_EXCLUDE = {"chat", "chat-baseline", "chat-email", "ingest-files", "server"}
HTTP_ACTIONS = sorted(name for name in ACTION_SPECS if name not in HTTP_ACTION_EXCLUDE)


def _parse_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _get_relevant_context(query: str, top_k: int):
    try:
        results = retrieval.scored_chunks(query, top_k=top_k)
        return [item.get("text", "").strip() for item in results if item.get("text")]
    except Exception:
        return []


def _build_messages(question: str, system_message: str, top_k: int):
    relevant_context = _get_relevant_context(question, top_k=top_k)
    if relevant_context:
        max_tokens = settings.CONFIG.get("context_token_budget", 1500)
        overlap_tokens = settings.CONFIG.get("context_overlap", 20)
        packed = context_packer.pack_context(
            question,
            relevant_context,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
        context_str = "\n\n".join(packed)
        user_text = f"{question}\n\nRelevant Context:\n{context_str}"
    else:
        user_text = question
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_text},
    ]


def _to_sse(event_name: str, payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_name}\ndata: {body}\n\n".encode("utf-8")


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


def _parse_multipart_upload(content_type: str, raw_body: bytes) -> tuple[list[tuple[str, bytes]], dict[str, str]]:
    boundary_match = re.search(r"boundary=([^;]+)", content_type or "", flags=re.IGNORECASE)
    if not boundary_match:
        raise ValueError("missing multipart boundary")
    boundary = boundary_match.group(1).strip().strip('"')
    boundary_bytes = f"--{boundary}".encode("utf-8")

    files: list[tuple[str, bytes]] = []
    fields: dict[str, str] = {}

    for part in raw_body.split(boundary_bytes):
        if not part:
            continue
        stripped = part.strip()
        if stripped in {b"--", b""}:
            continue
        if b"\r\n\r\n" not in part:
            continue
        header_blob, body_blob = part.split(b"\r\n\r\n", 1)
        headers = header_blob.decode("utf-8", errors="ignore").split("\r\n")
        content = body_blob.rstrip(b"\r\n")

        disposition = ""
        for header in headers:
            if header.lower().startswith("content-disposition:"):
                disposition = header
                break
        if not disposition:
            continue
        name_match = re.search(r'name="([^"]+)"', disposition)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if not name_match:
            continue
        field_name = name_match.group(1)
        if filename_match and filename_match.group(1):
            files.append((filename_match.group(1), content))
            continue
        fields[field_name] = content.decode("utf-8", errors="replace")

    return files, fields


def _run_action_capture(action: str, action_args: list[str]) -> dict:
    started = time.monotonic()
    out_buffer = io.StringIO()
    err_buffer = io.StringIO()
    with contextlib.redirect_stdout(out_buffer), contextlib.redirect_stderr(err_buffer):
        exit_code = run_action(action, action_args)
    return {
        "action": action,
        "args": action_args,
        "exit_code": exit_code,
        "stdout": out_buffer.getvalue(),
        "stderr": err_buffer.getvalue(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


class StreamingHandler(BaseHTTPRequestHandler):
    server_version = "LocalRAGSSE/1.1"

    def _send_json(self, status: int, payload: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _read_json(self) -> dict:
        raw_len = self.headers.get("Content-Length", "0")
        try:
            content_len = int(raw_len)
        except ValueError:
            raise ValueError("invalid Content-Length")
        if content_len <= 0:
            raise ValueError("empty request body")
        raw_body = self.rfile.read(content_len)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        return body

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return

        if parsed.path in {"/actions", "/action"}:
            actions = []
            for name in sorted(ACTION_SPECS):
                spec = ACTION_SPECS[name]
                actions.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "http_supported": spec.name in HTTP_ACTIONS,
                    }
                )
            self._send_json(
                HTTPStatus.OK,
                {
                    "actions": actions,
                    "http_supported_actions": HTTP_ACTIONS,
                    "notes": {
                        "run_endpoint": "POST /actions/run",
                        "interactive_actions_blocked": sorted(HTTP_ACTION_EXCLUDE),
                    },
                },
            )
            return

        if parsed.path == "/docs":
            query = parse_qs(parsed.query)
            namespace_raw = (query.get("namespace") or [None])[0]
            cursor = (query.get("cursor") or [None])[0]
            try:
                limit = int((query.get("limit") or [50])[0])
            except (TypeError, ValueError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'limit' must be an integer"})
                return
            try:
                namespace = validate_namespace(namespace_raw, default_to_default=True) if namespace_raw is not None else None
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            try:
                store = DocRegistryStore(str(settings.CONFIG.get("doc_registry_path", "data/doc_registry.json")))
                payload = store.list_docs(namespace=namespace, limit=limit, cursor=cursor)
                self._send_json(HTTPStatus.OK, {"ok": True, **payload})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path != "/chat/stream":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        query = parse_qs(parsed.query)
        question = (query.get("question") or [""])[0].strip()
        if not question:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing required query parameter: question")
            return

        try:
            model = (query.get("model") or [settings.CONFIG.get("ollama_model", "llama3")])[0]
            top_k = int((query.get("top_k") or [settings.CONFIG.get("top_k", 3)])[0])
            max_continuations = int(
                (query.get("max_continuations") or [settings.CONFIG.get("max_continuations", 2)])[0]
            )
            per_call_max_tokens = int(
                (
                    query.get("per_call_max_tokens")
                    or [settings.CONFIG.get("per_call_max_tokens", settings.CONFIG.get("chat_max_tokens", 4000))]
                )[0]
            )
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid numeric query parameter")
            return

        enable_thinking_summary_raw = (query.get("enable_thinking_summary") or ["false"])[0].strip().lower()
        enable_thinking_summary = enable_thinking_summary_raw in {"1", "true", "yes", "on"}

        system_message = settings.CONFIG.get(
            "system_message",
            "You are a helpful assistant that is an expert at extracting the most useful information from a given text.",
        )
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
        messages = _build_messages(question, system_message=system_message, top_k=top_k)

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

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
                self.wfile.write(_to_sse(name, payload))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            try:
                self.wfile.write(_to_sse("error", {"message": "server_stream_error", "detail": str(exc)}))
                self.wfile.write(_to_sse("done", {"cancelled": True}))
                self.wfile.flush()
            except Exception:
                return

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/ingest/chunks":
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            chunks = body.get("chunks")
            if not isinstance(chunks, list) or not chunks:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'chunks' must be a non-empty array"})
                return
            source_path = body.get("source_path")
            doc_id = body.get("doc_id")
            embedding_model = body.get("embedding_model")
            try:
                result = ingest_chunks(chunks, source_path=source_path, doc_id=doc_id, embedding_model=embedding_model)
                self._send_json(HTTPStatus.OK, {"ok": True, "result": result})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path == "/ingest/text":
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            text = (body.get("text") or "").strip()
            if not text:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'text' is required"})
                return
            try:
                max_chars = int(body.get("max_chars") or settings.CONFIG.get("chunk_max_chars", 1000))
            except (TypeError, ValueError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'max_chars' must be an integer"})
                return
            chunks = _chunk_text_for_ingest(text, max_chars=max(1, max_chars))
            source_path = body.get("source_path")
            doc_id = body.get("doc_id")
            embedding_model = body.get("embedding_model")
            try:
                result = ingest_chunks(chunks, source_path=source_path, doc_id=doc_id, embedding_model=embedding_model)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "chunk_count": len(chunks),
                        "result": result,
                    },
                )
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path in {"/ingest/files", "/ingestion/files"}:
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            paths = body.get("paths")
            if not isinstance(paths, list) or not paths or any(not isinstance(value, str) for value in paths):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'paths' must be a non-empty array of strings"})
                return
            recursive = _parse_bool(body.get("recursive"), default=False)
            include_patterns = body.get("include") or []
            exclude_patterns = body.get("exclude") or []
            if not isinstance(include_patterns, list) or any(not isinstance(value, str) for value in include_patterns):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'include' must be an array of strings"})
                return
            if not isinstance(exclude_patterns, list) or any(not isinstance(value, str) for value in exclude_patterns):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'exclude' must be an array of strings"})
                return
            options = build_options(
                recursive=recursive,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                max_bytes=body.get("max_bytes", settings.CONFIG.get("ingest_max_bytes", 8 * 1024 * 1024)),
                max_rows=body.get("max_rows", settings.CONFIG.get("ingest_max_rows", 2000)),
                max_pages=body.get("max_pages", settings.CONFIG.get("ingest_max_pages", 200)),
                max_slides=body.get("max_slides", settings.CONFIG.get("ingest_max_slides", 300)),
                max_sheets=body.get("max_sheets", settings.CONFIG.get("ingest_max_sheets", 50)),
            )
            try:
                summary = ingest_paths(paths, options=options, embedding_model=body.get("embedding_model"))
                self._send_json(HTTPStatus.OK, {"ok": True, "summary": summary})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path == "/ingest/folder":
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return

            folder_path = str(body.get("path") or "").strip()
            is_safe, safety_reason = _is_safe_folder_path(folder_path)
            if not is_safe:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": safety_reason})
                return

            include_patterns = body.get("include") or []
            exclude_patterns = body.get("exclude") or []
            if not isinstance(include_patterns, list) or any(not isinstance(value, str) for value in include_patterns):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'include' must be an array of strings"})
                return
            if not isinstance(exclude_patterns, list) or any(not isinstance(value, str) for value in exclude_patterns):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'exclude' must be an array of strings"})
                return

            request_id = str(body.get("request_id") or uuid.uuid4())
            stream = _parse_bool(body.get("stream"), default=False)
            recursive = _parse_bool(body.get("recursive"), default=True)
            dry_run = _parse_bool(body.get("dry_run"), default=False)
            force = _parse_bool(body.get("force"), default=False)
            respect_gitignore = _parse_bool(body.get("respect_gitignore"), default=True)

            if stream:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()

                def _emit(event_name: str, payload: dict):
                    packet = dict(payload or {})
                    packet["request_id"] = request_id
                    self.wfile.write(_to_sse(event_name, packet))
                    self.wfile.flush()

                try:
                    def _on_progress(event_name: str, payload: dict):
                        # Preserve folder ingest event names; map planning to skipped for streaming contract.
                        mapped_name = "file_skipped" if event_name == "file_planned" else event_name
                        _emit(mapped_name, payload)

                    summary = ingest_folder(
                        FolderIngestOptions(
                            path=folder_path,
                            recursive=recursive,
                            include_patterns=include_patterns,
                            exclude_patterns=exclude_patterns,
                            respect_gitignore=respect_gitignore,
                            dry_run=dry_run,
                            force=force,
                            embedding_model=body.get("embedding_model"),
                            progress_callback=_on_progress,
                        )
                    )
                    _emit("done", {"ok": True, "summary": summary})
                except (BrokenPipeError, ConnectionResetError):
                    return
                except Exception as exc:
                    try:
                        _emit("error", {"message": str(exc)})
                        _emit("done", {"ok": False})
                    except Exception:
                        return
                return

            try:
                summary = ingest_folder(
                    FolderIngestOptions(
                        path=folder_path,
                        recursive=recursive,
                        include_patterns=include_patterns,
                        exclude_patterns=exclude_patterns,
                        respect_gitignore=respect_gitignore,
                        dry_run=dry_run,
                        force=force,
                        embedding_model=body.get("embedding_model"),
                    )
                )
                self._send_json(HTTPStatus.OK, {"ok": True, "request_id": request_id, "summary": summary})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "request_id": request_id, "error": str(exc)})
                return

        if parsed.path in {"/ingest/upload", "/ingestion/upload"}:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Content-Type must be multipart/form-data"})
                return
            raw_len = self.headers.get("Content-Length", "0")
            try:
                content_len = int(raw_len)
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid Content-Length"})
                return
            if content_len <= 0:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "empty multipart body"})
                return
            raw_body = self.rfile.read(content_len)
            try:
                uploaded, fields = _parse_multipart_upload(content_type, raw_body)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            if not uploaded:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "No file uploads provided under form field 'file'"})
                return
            options = build_options(
                max_bytes=fields.get("max_bytes", settings.CONFIG.get("ingest_max_bytes", 8 * 1024 * 1024)),
                max_rows=fields.get("max_rows", settings.CONFIG.get("ingest_max_rows", 2000)),
                max_pages=fields.get("max_pages", settings.CONFIG.get("ingest_max_pages", 200)),
                max_slides=fields.get("max_slides", settings.CONFIG.get("ingest_max_slides", 300)),
                max_sheets=fields.get("max_sheets", settings.CONFIG.get("ingest_max_sheets", 50)),
            )
            try:
                summary = ingest_uploaded_files(uploaded, options=options, embedding_model=fields.get("embedding_model"))
                self._send_json(HTTPStatus.OK, {"ok": True, "summary": summary})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path == "/vectors/delete-doc":
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            doc_id = (body.get("doc_id") or "").strip()
            if not doc_id:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'doc_id' is required"})
                return
            try:
                deleted = delete_doc(doc_id)
                self._send_json(HTTPStatus.OK, {"ok": True, "doc_id": doc_id, "deleted": deleted})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path == "/retrieval/query":
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            query_text = (body.get("query") or "").strip()
            if not query_text:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'query' is required"})
                return
            try:
                top_k = int(body.get("top_k") or settings.CONFIG.get("top_k", 6))
            except (TypeError, ValueError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'top_k' must be an integer"})
                return
            rerank = _parse_bool(body.get("rerank"), default=True)
            filters = body.get("filters")
            if filters is not None and not isinstance(filters, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'filters' must be an object"})
                return
            try:
                results = retrieval.scored_chunks(query_text, top_k=top_k, rerank=rerank, filters=filters)
                self._send_json(HTTPStatus.OK, {"ok": True, "count": len(results), "results": results})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path in {"/actions/run", "/action/run"}:
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            action = (body.get("action") or "").strip()
            action_args = body.get("args") or []
            if action not in HTTP_ACTIONS:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "ok": False,
                        "error": "unsupported action for HTTP execution",
                        "allowed_actions": HTTP_ACTIONS,
                    },
                )
                return
            if not isinstance(action_args, list) or any(not isinstance(v, str) for v in action_args):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'args' must be an array of strings"})
                return
            try:
                result = _run_action_capture(action, action_args)
                self._send_json(HTTPStatus.OK, {"ok": result["exit_code"] == 0, "result": result})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/docs/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return

        doc_id = parsed.path[len("/docs/"):].strip()
        if not doc_id:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'doc_id' is required"})
            return

        query = parse_qs(parsed.query)
        all_namespaces = _parse_bool((query.get("all_namespaces") or ["false"])[0], default=False)
        namespace_raw = (query.get("namespace") or [None])[0]

        if all_namespaces:
            namespace = None
        else:
            try:
                namespace = validate_namespace(namespace_raw, default_to_default=True)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return

        try:
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
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "doc_id": doc_id,
                    "namespace": namespace,
                    "all_namespaces": all_namespaces,
                    "vectors_deleted": int(vectors_deleted),
                    "registry_deleted": int(registry_deleted),
                    "not_found": (vectors_deleted == 0 and registry_deleted == 0),
                },
            )
            return
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
            return

    def log_message(self, format, *args):
        # Keep server output concise.
        return


def main():
    parser = argparse.ArgumentParser(description="Streaming SSE server for local RAG chat.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), StreamingHandler)
    print(f"SSE server listening on http://{args.host}:{args.port}")
    print("GET  /health")
    print("GET  /actions")
    print("GET  /docs")
    print("GET  /chat/stream?question=...&top_k=...&model=...")
    print("POST /ingest/chunks")
    print("POST /ingest/text")
    print("POST /ingest/files")
    print("POST /ingest/upload (multipart form-data)")
    print("POST /vectors/delete-doc")
    print("POST /retrieval/query")
    print("POST /actions/run")
    print("DELETE /docs/{doc_id}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

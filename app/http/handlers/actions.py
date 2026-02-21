from __future__ import annotations

import contextlib
import io
import time
from http import HTTPStatus

from app.http.request_parsing import read_json

HTTP_ACTION_EXCLUDE = {"chat", "chat-baseline", "chat-email", "ingest-files", "server"}


def get_http_actions(action_specs: dict) -> list[str]:
    return sorted(name for name in action_specs if name not in HTTP_ACTION_EXCLUDE)


def handle_actions_get(handler, deps, parsed) -> bool:
    if parsed.path not in {"/actions", "/action"}:
        return False

    action_specs = deps["ACTION_SPECS"]
    http_actions = get_http_actions(action_specs)
    actions = []
    for name in sorted(action_specs):
        spec = action_specs[name]
        actions.append(
            {
                "name": spec.name,
                "description": spec.description,
                "http_supported": spec.name in http_actions,
            }
        )
    handler.send_json(
        HTTPStatus.OK,
        {
            "actions": actions,
            "http_supported_actions": http_actions,
            "notes": {
                "run_endpoint": "POST /actions/run",
                "interactive_actions_blocked": sorted(HTTP_ACTION_EXCLUDE),
            },
        },
    )
    return True


def _run_action_capture(run_action, action: str, action_args: list[str]) -> dict:
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


def handle_actions_post(handler, deps, parsed) -> bool:
    if parsed.path not in {"/actions/run", "/action/run"}:
        return False

    try:
        body = read_json(handler)
    except ValueError as exc:
        handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        return True

    action = (body.get("action") or "").strip()
    action_args = body.get("args") or []
    http_actions = get_http_actions(deps["ACTION_SPECS"])
    if action not in http_actions:
        handler.send_json(
            HTTPStatus.BAD_REQUEST,
            {
                "ok": False,
                "error": "unsupported action for HTTP execution",
                "allowed_actions": http_actions,
            },
        )
        return True
    if not isinstance(action_args, list) or any(not isinstance(v, str) for v in action_args):
        handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'args' must be an array of strings"})
        return True

    try:
        result = _run_action_capture(deps["run_action"], action, action_args)
        handler.send_json(HTTPStatus.OK, {"ok": result["exit_code"] == 0, "result": result})
    except Exception as exc:
        handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
    return True

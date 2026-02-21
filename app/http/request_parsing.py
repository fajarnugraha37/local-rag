import json
import re


def parse_bool(value, default: bool) -> bool:
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


def read_json(handler) -> dict:
    raw_len = handler.headers.get("Content-Length", "0")
    try:
        content_len = int(raw_len)
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc
    if content_len <= 0:
        raise ValueError("empty request body")
    raw_body = handler.rfile.read(content_len)
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid JSON body: {exc}") from exc
    if not isinstance(body, dict):
        raise ValueError("JSON body must be an object")
    return body


def parse_multipart_upload(content_type: str, raw_body: bytes) -> tuple[list[tuple[str, bytes]], dict[str, str]]:
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

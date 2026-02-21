from __future__ import annotations

from http import HTTPStatus
from urllib.parse import parse_qs

from app.http.request_parsing import parse_bool


def handle_docs_get(handler, deps, parsed) -> bool:
    if parsed.path != "/docs":
        return False

    settings = deps["settings"]
    validate_namespace = deps["validate_namespace"]
    query = parse_qs(parsed.query)
    namespace_raw = (query.get("namespace") or [None])[0]
    cursor = (query.get("cursor") or [None])[0]
    try:
        limit = int((query.get("limit") or [50])[0])
    except (TypeError, ValueError):
        handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'limit' must be an integer"})
        return True
    try:
        namespace = validate_namespace(namespace_raw, default_to_default=True) if namespace_raw is not None else None
    except ValueError as exc:
        handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        return True
    try:
        store = deps["DocRegistryStore"](str(settings.CONFIG.get("doc_registry_path", "data/doc_registry.json")))
        payload = store.list_docs(namespace=namespace, limit=limit, cursor=cursor)
        handler.send_json(HTTPStatus.OK, {"ok": True, **payload})
    except Exception as exc:
        handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
    return True


def handle_docs_delete(handler, deps, parsed) -> bool:
    if not parsed.path.startswith("/docs/"):
        return False

    settings = deps["settings"]
    validate_namespace = deps["validate_namespace"]
    doc_id = parsed.path[len("/docs/"):].strip()
    if not doc_id:
        handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'doc_id' is required"})
        return True

    query = parse_qs(parsed.query)
    all_namespaces = parse_bool((query.get("all_namespaces") or ["false"])[0], default=False)
    namespace_raw = (query.get("namespace") or [None])[0]

    if all_namespaces:
        namespace = None
    else:
        try:
            namespace = validate_namespace(namespace_raw, default_to_default=True)
        except ValueError as exc:
            handler.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return True

    try:
        vectors_deleted = deps["delete_doc"](doc_id, namespace=namespace, all_namespaces=all_namespaces)
        registry_store = deps["DocRegistryStore"](str(settings.CONFIG.get("doc_registry_path", "data/doc_registry.json")))
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
        handler.send_json(
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
    except Exception as exc:
        handler.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
    return True

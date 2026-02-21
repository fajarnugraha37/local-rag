from __future__ import annotations

from fastapi import APIRouter
from pydantic import ValidationError

from app.config import runtime_settings as settings
from app.health.checks import run_readiness_checks
from app.http.schemas.common import CapabilityResponse, ConfigPatchRequest, ConfigResponse

router = APIRouter(tags=["system"])

_PATCHABLE_CONFIG_KEYS = {
    "top_k",
    "ollama_model",
    "enable_streaming",
    "enable_thinking_summary",
    "provider_timeout_s",
    "flush_interval_ms",
    "citations",
    "citations_mode",
    "citation_max_sources",
    "citation_max_snippet_chars",
}


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@router.get("/readyz")
def readyz() -> dict:
    payload = run_readiness_checks(settings.CONFIG)
    return payload


@router.get("/version")
def version() -> dict:
    return {
        "ok": True,
        "version": "0.1.0",
        "api": "fastapi",
    }


@router.get("/v1/capabilities", response_model=CapabilityResponse)
def capabilities() -> CapabilityResponse:
    return CapabilityResponse(
        ok=True,
        capabilities={
            "streaming": True,
            "citations": True,
            "namespaces": True,
            "docling_ingestion": bool(settings.CONFIG.get("ingest_docling_enabled", True)),
            "legacy_endpoints": True,
        },
    )


@router.get("/v1/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    return ConfigResponse(ok=True, config=dict(settings.CONFIG))


@router.patch("/v1/config", response_model=ConfigResponse)
def patch_config(body: dict) -> ConfigResponse:
    try:
        req = ConfigPatchRequest.model_validate(body)
    except ValidationError as exc:
        return ConfigResponse(ok=False, config={"error": str(exc)})

    updates = req.updates or {}
    applied: dict = {}
    rejected: dict = {}
    for key, value in updates.items():
        if key not in _PATCHABLE_CONFIG_KEYS:
            rejected[key] = "key is not patchable"
            continue
        settings.CONFIG[key] = value
        applied[key] = value

    snapshot = dict(settings.CONFIG)
    snapshot["_applied"] = applied
    snapshot["_rejected"] = rejected
    return ConfigResponse(ok=True, config=snapshot)

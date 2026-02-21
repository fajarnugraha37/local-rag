from __future__ import annotations

from typing import Any, Optional

import ollama

from app.config import runtime_settings as settings


def extract_embedding(resp: Any) -> Optional[list[float]]:
    """Extract embedding vector from Ollama/OpenAI-compatible response shapes."""
    try:
        if resp is None:
            return None
        if isinstance(resp, dict):
            if "embedding" in resp:
                return resp["embedding"]
            data = resp.get("data")
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict) and "embedding" in first:
                    return first["embedding"]
        if hasattr(resp, "embedding"):
            try:
                return resp.embedding
            except Exception:
                pass
        if hasattr(resp, "data"):
            data = getattr(resp, "data")
            if isinstance(data, (list, tuple)) and data:
                first = data[0]
                if hasattr(first, "embedding"):
                    return getattr(first, "embedding")
                if isinstance(first, dict) and "embedding" in first:
                    return first["embedding"]
        if isinstance(resp, list):
            return resp
    except Exception:
        return None
    return None


def embed_text(
    text: str,
    embedding_model: Optional[str] = None,
    *,
    allow_fallback: bool = True,
    fallback_length: Optional[int] = None,
) -> dict[str, Any]:
    """Embed text and return embedding + metadata.

    Returns:
        {"embedding": list[float] | None, "model": str, "used_fallback": bool}
    """
    model = embedding_model or settings.CONFIG.get("embedding_model", "mxbai-embed-large")
    fallback_len = fallback_length or int(settings.CONFIG.get("embedding_fallback_length", 512))

    try:
        resp = ollama.embeddings(model=model, prompt=text)
        emb = extract_embedding(resp)
        if emb is not None:
            return {"embedding": emb, "model": model, "used_fallback": False}
    except Exception:
        if not allow_fallback:
            return {"embedding": None, "model": model, "used_fallback": False}

    if allow_fallback:
        try:
            resp = ollama.embeddings(model=model, prompt=(text or "")[:fallback_len])
            emb = extract_embedding(resp)
            return {"embedding": emb, "model": model, "used_fallback": emb is not None}
        except Exception:
            return {"embedding": None, "model": model, "used_fallback": False}

    return {"embedding": None, "model": model, "used_fallback": False}


__all__ = ["extract_embedding", "embed_text"]

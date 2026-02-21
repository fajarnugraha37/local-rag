from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="FastAPI server for local RAG.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development.")
    args = parser.parse_args()

    uvicorn.run(
        "app.http.fastapi_app:create_app",
        host=args.host,
        port=args.port,
        reload=bool(args.reload),
        factory=True,
    )

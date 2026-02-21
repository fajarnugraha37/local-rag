from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class FileStateRecord:
    path: str
    size_bytes: int
    mtime_ns: int
    content_hash: str
    last_ingested_at: str


class FileStateStore:
    def __init__(self, state_path: str) -> None:
        self.state_path = os.path.abspath(state_path)
        self._records: Dict[str, FileStateRecord] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not os.path.exists(self.state_path):
            self._records = {}
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle) or {}
        except Exception:
            self._records = {}
            return
        records: Dict[str, FileStateRecord] = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            try:
                records[key] = FileStateRecord(
                    path=str(value.get("path") or key),
                    size_bytes=int(value.get("size_bytes") or 0),
                    mtime_ns=int(value.get("mtime_ns") or 0),
                    content_hash=str(value.get("content_hash") or ""),
                    last_ingested_at=str(value.get("last_ingested_at") or ""),
                )
            except Exception:
                continue
        self._records = records

    def get(self, path: str) -> Optional[FileStateRecord]:
        self._load()
        return self._records.get(os.path.abspath(path))

    def set(
        self,
        path: str,
        *,
        size_bytes: int,
        mtime_ns: int,
        content_hash: str,
        last_ingested_at: Optional[str] = None,
    ) -> None:
        self._load()
        abs_path = os.path.abspath(path)
        self._records[abs_path] = FileStateRecord(
            path=abs_path,
            size_bytes=int(size_bytes),
            mtime_ns=int(mtime_ns),
            content_hash=str(content_hash),
            last_ingested_at=last_ingested_at or datetime.now(timezone.utc).isoformat(),
        )

    def save(self) -> None:
        self._load()
        parent = os.path.dirname(self.state_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        payload = {key: asdict(record) for key, record in sorted(self._records.items())}
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)


__all__ = ["FileStateRecord", "FileStateStore"]

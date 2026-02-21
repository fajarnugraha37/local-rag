from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ConvertedBlock:
    text: str
    locator: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConvertedDocument:
    text_markdown: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    blocks: List[ConvertedBlock] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

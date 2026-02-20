from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class StreamEnvelope:
    event: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {'event': self.event, 'data': self.data}


def _build(event: str, **data: Any) -> Dict[str, Any]:
    return StreamEnvelope(event=event, data=data).to_dict()


def meta(**data: Any) -> Dict[str, Any]:
    return _build('meta', **data)


def thinking_delta(text: str, **data: Any) -> Dict[str, Any]:
    return _build('thinking_delta', text=text, **data)


def final_delta(text: str, **data: Any) -> Dict[str, Any]:
    return _build('final_delta', text=text, **data)


def part_done(part_index: int, **data: Any) -> Dict[str, Any]:
    return _build('part_done', part_index=part_index, **data)


def done(**data: Any) -> Dict[str, Any]:
    return _build('done', **data)


def error(message: str, **data: Any) -> Dict[str, Any]:
    return _build('error', message=message, **data)

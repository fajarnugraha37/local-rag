from app.chat.streaming_llm_client import stream_chat_with_continuation
from app.config import runtime_settings as settings


class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content="", finish_reason=None):
        self.delta = _Delta(content)
        self.finish_reason = finish_reason


class _Chunk:
    def __init__(self, content="", finish_reason=None):
        self.choices = [_Choice(content=content, finish_reason=finish_reason)]


class _Message:
    def __init__(self, content):
        self.content = content


class _ResponseChoice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_ResponseChoice(content)]


class _FakeCompletions:
    def __init__(self, stream_sequences, summary_text=""):
        self.stream_sequences = list(stream_sequences)
        self.summary_text = summary_text
        self.stream_calls = []
        self.summary_calls = []
        self.stream_index = 0

    def create(self, **kwargs):
        if kwargs.get("stream"):
            self.stream_calls.append(kwargs)
            seq = self.stream_sequences[self.stream_index]
            self.stream_index += 1
            return iter(seq)
        self.summary_calls.append(kwargs)
        return _Response(self.summary_text)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, completions):
        self.chat = _FakeChat(completions)


def test_stream_continues_when_finish_reason_length():
    completions = _FakeCompletions(
        stream_sequences=[
            [_Chunk("Hello "), _Chunk("world", "length")],
            [_Chunk(" and"), _Chunk(" beyond", "stop")],
        ]
    )
    client = _FakeClient(completions)

    events = list(
        stream_chat_with_continuation(
            client,
            model="fake-model",
            messages=[{"role": "user", "content": "ping"}],
            per_call_max_tokens=8,
            continuation_instruction="continue",
            max_continuations=2,
            flush_interval_ms=999999,
        )
    )

    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["data"]["text"] == "Hello world and beyond"
    assert len(completions.stream_calls) == 2
    assert completions.stream_calls[1]["messages"][-1]["content"] == "continue"


def test_stream_event_order_and_aggregation():
    completions = _FakeCompletions(
        stream_sequences=[
            [_Chunk("A"), _Chunk("B"), _Chunk("C", "stop")],
        ]
    )
    client = _FakeClient(completions)

    events = list(
        stream_chat_with_continuation(
            client,
            model="fake-model",
            messages=[{"role": "user", "content": "q"}],
            per_call_max_tokens=32,
            continuation_instruction="continue",
            max_continuations=0,
            flush_interval_ms=999999,
        )
    )
    names = [e["event"] for e in events]

    assert names[0] == "meta"
    assert names[-2] == "part_done"
    assert names[-1] == "done"
    assert [e["data"]["text"] for e in events if e["event"] == "final_delta"] == ["A", "B", "C"]
    assert events[-1]["data"]["text"] == "ABC"


def test_stream_cancellation_path():
    checks = {"count": 0}
    completions = _FakeCompletions(
        stream_sequences=[
            [_Chunk("partial "), _Chunk("rest", "stop")],
        ]
    )
    client = _FakeClient(completions)

    events = list(
        stream_chat_with_continuation(
            client,
            model="fake-model",
            messages=[{"role": "user", "content": "q"}],
            per_call_max_tokens=32,
            continuation_instruction="continue",
            max_continuations=0,
            flush_interval_ms=999999,
            cancel_check=lambda: (
                checks.__setitem__("count", checks["count"] + 1) or checks["count"] >= 3
            ),
        )
    )

    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["cancelled"] is True
    assert events[-1]["data"]["text"] == "partial "


def test_streaming_config_toggles_are_loaded(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "enable_streaming: true",
                "enable_thinking_summary: true",
                "per_call_max_tokens: 123",
                "max_continuations: 5",
                "flush_interval_ms: 77",
                "provider_timeout_s: 45",
                'continuation_instruction: "Keep going"',
            ]
        ),
        encoding="utf-8",
    )

    cfg = settings.load_settings(str(cfg_path))
    assert cfg["enable_streaming"] is True
    assert cfg["enable_thinking_summary"] is True
    assert cfg["per_call_max_tokens"] == 123
    assert cfg["max_continuations"] == 5
    assert cfg["flush_interval_ms"] == 77
    assert cfg["provider_timeout_s"] == 45
    assert cfg["continuation_instruction"] == "Keep going"

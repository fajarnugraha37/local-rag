from types import SimpleNamespace

from cmd.actions import run_action
from app.chat import document_chat_baseline_cli as baseline_cli
from app.config import runtime_settings as settings


class _DummyCompletions:
    def create(self, **kwargs):
        message = SimpleNamespace(content="Answer with citation [1].")
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _DummyClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_DummyCompletions())


def _sample_source_rows():
    return [
        {
            "text": "Evidence for answer.",
            "source": {
                "source_id": "S1",
                "citation_index": 1,
                "namespace": "default",
                "doc_id": "doc-1",
                "path": "docs/a.txt",
                "title": "Doc A",
                "locator": "page 1",
                "snippet": "Evidence for answer.",
            },
        }
    ]


def test_chat_actions_help_exposes_citation_flags(capsys):
    for action in ["chat", "chat-baseline", "chat-email"]:
        code = run_action(action, ["--help"])
        out = capsys.readouterr().out
        assert code == 0
        assert "--citations" in out
        assert "--citations-mode" in out
        assert "--max-sources" in out
        assert "--max-snippet-chars" in out


def test_baseline_cli_output_matches_citation_modes(monkeypatch, capsys):
    monkeypatch.setattr(baseline_cli, "client", _DummyClient())
    monkeypatch.setattr(
        baseline_cli, "get_relevant_context", lambda *args, **kwargs: _sample_source_rows()
    )

    settings.CONFIG["citations"] = True
    settings.CONFIG["citations_mode"] = "none"
    settings.CONFIG["citation_max_sources"] = 3
    settings.CONFIG["citation_max_snippet_chars"] = 120
    answer_none = baseline_cli.ollama_chat(
        "q",
        "sys",
        None,
        [],
        "fake-model",
        [],
        stream=False,
    )
    assert "[1]" not in answer_none

    settings.CONFIG["citations"] = True
    settings.CONFIG["citations_mode"] = "inline+sources"
    answer_full = baseline_cli.ollama_chat(
        "q",
        "sys",
        None,
        [],
        "fake-model",
        [],
        stream=False,
    )
    output = capsys.readouterr().out
    assert "[1]" in answer_full
    assert "Sources:" in output

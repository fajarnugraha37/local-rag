import argparse

from openai import OpenAI

from app.chat import chat_service
from app.chat import cli_formatting as fmt
from app.config import runtime_settings as settings
from app.retrieval import hybrid_search as retrieval

client = None

# Backward-compatible color constants.
PINK = fmt.PINK
CYAN = fmt.CYAN
YELLOW = fmt.YELLOW
NEON_GREEN = fmt.NEON_GREEN
RESET_COLOR = fmt.RESET_COLOR


def open_file(filepath):
    with open(filepath, encoding="utf-8") as infile:
        return infile.read()


def get_relevant_context(rewritten_input, vault_embeddings, vault_content, top_k=3):
    return chat_service.get_relevant_context(
        rewritten_input,
        retrieval,
        top_k,
        on_error=lambda exc: print(YELLOW + f"Retrieval failed: {exc}" + RESET_COLOR),
    )


def ollama_chat(
    user_input,
    system_message,
    vault_embeddings,
    vault_content,
    ollama_model,
    conversation_history,
    stream=False,
    max_continuations=None,
    per_call_max_tokens=None,
    enable_thinking_summary=False,
):
    top_k = int(settings.CONFIG.get("top_k", 3))
    retrieved_chunks = get_relevant_context(user_input, vault_embeddings, vault_content, top_k=top_k)
    user_input_with_context, source_blocks = chat_service.build_context_prompt(
        user_input,
        retrieved_chunks,
        top_k,
        settings,
    )
    fmt.print_context_blocks(source_blocks, chat_service.context_blocks_to_text)

    conversation_history.append({"role": "user", "content": user_input_with_context})
    messages = chat_service.build_messages(system_message, conversation_history)

    if stream:
        answer = chat_service.stream_chat_answer(
            client=client,
            ollama_model=ollama_model,
            messages=messages,
            source_blocks=source_blocks,
            settings=settings,
            top_k=top_k,
            max_continuations=max_continuations,
            per_call_max_tokens=per_call_max_tokens,
            enable_thinking_summary=enable_thinking_summary,
            formatting=fmt,
            error_message="Sorry, the chat request timed out or failed.",
        )
        conversation_history.append({"role": "assistant", "content": answer})
        return answer

    response = client.chat.completions.create(model=ollama_model, messages=messages)
    answer = chat_service.render_answer_with_citations(
        response.choices[0].message.content,
        source_blocks,
        settings=settings,
        top_k=top_k,
    )
    conversation_history.append({"role": "assistant", "content": answer})
    return answer


def main():
    global client

    parser = argparse.ArgumentParser(description="Ollama Chat")
    parser.add_argument(
        "--model",
        default=settings.CONFIG.get(
            "ollama_model",
            "hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest",
        ),
        help="Ollama model to use (default from config.yaml)",
    )
    parser.add_argument(
        "--stream",
        action=argparse.BooleanOptionalAction,
        default=settings.CONFIG.get("enable_streaming", False),
        help="Enable streaming response output.",
    )
    parser.add_argument(
        "--max-continuations",
        type=int,
        default=settings.CONFIG.get("max_continuations", 2),
        help="Maximum number of follow-up calls when output is cut by token limit.",
    )
    parser.add_argument(
        "--per-call-max-tokens",
        type=int,
        default=settings.CONFIG.get("per_call_max_tokens", settings.CONFIG.get("chat_max_tokens", 4000)),
        help="Token cap per streaming call before continuation.",
    )
    parser.add_argument(
        "--enable-thinking-summary",
        action=argparse.BooleanOptionalAction,
        default=settings.CONFIG.get("enable_thinking_summary", False),
        help="Enable optional short thinking summary emission (off by default).",
    )
    parser.add_argument(
        "--citations",
        action=argparse.BooleanOptionalAction,
        default=settings.CONFIG.get("citations", True),
        help="Enable citation rendering in final answers.",
    )
    parser.add_argument(
        "--citations-mode",
        choices=["inline", "inline+sources", "none"],
        default=settings.CONFIG.get("citations_mode", "inline"),
        help="Citation rendering mode.",
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=settings.CONFIG.get("citation_max_sources", settings.CONFIG.get("top_k", 3)),
        help="Maximum number of sources to include in rendered output.",
    )
    parser.add_argument(
        "--max-snippet-chars",
        type=int,
        default=settings.CONFIG.get("citation_max_snippet_chars", 240),
        help="Maximum snippet characters for rendered sources.",
    )
    args = parser.parse_args()

    settings.CONFIG["citations"] = bool(args.citations)
    settings.CONFIG["citations_mode"] = str(args.citations_mode)
    settings.CONFIG["citation_max_sources"] = int(max(0, args.max_sources))
    settings.CONFIG["citation_max_snippet_chars"] = int(max(0, args.max_snippet_chars))

    client = OpenAI(
        base_url=settings.CONFIG.get("ollama_api", {}).get("base_url", "http://localhost:11434/v1"),
        api_key=settings.CONFIG.get("ollama_api", {}).get("api_key"),
    )

    conversation_history = []
    system_message = settings.CONFIG.get(
        "system_message",
        "You are a helpful assistant that is an expert at extracting the most useful information from a given text",
    )

    while True:
        user_input = input(YELLOW + "Ask a question about your documents (or type 'quit' to exit): " + RESET_COLOR)
        if user_input.lower() == "quit":
            break

        response = ollama_chat(
            user_input,
            system_message,
            None,
            [],
            args.model,
            conversation_history,
            stream=args.stream,
            max_continuations=args.max_continuations,
            per_call_max_tokens=args.per_call_max_tokens,
            enable_thinking_summary=args.enable_thinking_summary,
        )
        if args.stream:
            print(NEON_GREEN + "Response complete." + RESET_COLOR)
        else:
            print(NEON_GREEN + "Response: \n\n" + response + RESET_COLOR)

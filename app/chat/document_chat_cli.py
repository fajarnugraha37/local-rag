import argparse
import concurrent.futures
import json

from openai import OpenAI

from app.chat import chat_service
from app.chat import cli_formatting as fmt
from app.config import runtime_settings as settings
from app.retrieval import hybrid_search as retrieval

client = None

PINK = fmt.PINK
CYAN = fmt.CYAN
YELLOW = fmt.YELLOW
NEON_GREEN = fmt.NEON_GREEN
RESET_COLOR = fmt.RESET_COLOR


def chunk_text(text, max_chars=1000, overlap=100):
    max_chars = settings.CONFIG.get("chunk_max_chars", max_chars)
    overlap = settings.CONFIG.get("chunk_overlap_chars", overlap)
    chunks = []
    if not text:
        return chunks
    text_len = len(text)
    start = 0
    while start < text_len:
        end = min(text_len, start + max_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start = max(0, end - overlap)
    return chunks


def _call_with_timeout(func, timeout_sec=30, *args, **kwargs):
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        print(YELLOW + f"Model request timed out after {timeout_sec} seconds." + RESET_COLOR)
        return None
    except Exception as exc:
        print(YELLOW + f"Model request failed: {exc}" + RESET_COLOR)
        return None


def split_think_and_final(text):
    if not text:
        return (None, None)
    import re

    m = re.search(r"(?i)<think\b", text)
    if m:
        tag_close = text.find(">", m.end())
        start = tag_close + 1 if tag_close != -1 else m.end()
        close = re.search(r"(?i)</think>", text[start:])
        if close:
            thinking = text[start : start + close.start()].strip()
            rest = text[start + close.end() :].strip()
            final = rest if rest else None
            return (thinking, final)
        fm = re.search(r"(?i)(\n\n|\r\n\r\n)(final answer[:\s]|final[:\s]|\*\*final\*\*)", text[start:])
        if fm:
            thinking = text[start : start + fm.start()].strip()
            final = text[start + fm.end() :].strip()
            return (thinking, final if final else None)
        return (text[start:].strip(), None)

    fm = re.search(r"(?i)(final answer[:\s]|final[:\s]|\*\*final\*\*|# final)", text)
    if fm:
        final = text[fm.end() :].strip()
        thinking = text[: fm.start()].strip() or None
        return (thinking, final)

    return (None, text.strip())


def finalize_draft(draft_text, ollama_model):
    if not draft_text:
        return None
    system_msg = (
        "You are a concise assistant. Given the draft below which may contain internal reasoning, "
        "produce a concise final answer only (no chain-of-thought), and return only the answer text."
    )
    messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": "Draft:\n\n" + draft_text}]
    timeout = settings.CONFIG.get("model_timeout", 120)
    resp = _call_with_timeout(
        client.chat.completions.create,
        timeout,
        model=ollama_model,
        messages=messages,
        max_tokens=settings.CONFIG.get("finalize_max_tokens", 400),
        temperature=settings.CONFIG.get("finalize_temperature", 0.0),
    )
    if resp is None:
        return None
    try:
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


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


def rewrite_query(user_input_json, conversation_history, ollama_model):
    user_input = json.loads(user_input_json)["Query"]
    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history[-2:]])
    prompt = f"""Rewrite the following query by incorporating relevant context from the conversation history.
    The rewritten query should:

    - Preserve the core intent and meaning of the original query
    - Expand and clarify the query to make it more specific and informative for retrieving relevant context
    - Avoid introducing new topics or queries that deviate from the original query
    - DONT EVER ANSWER the Original query, but instead focus on rephrasing and expanding it into a new query

    Return ONLY the rewritten query text, without any additional formatting or explanations.

    Conversation History:
    {context}

    Original query: [{user_input}]

    Rewritten query:
    """
    timeout = settings.CONFIG.get("model_timeout", 30)
    resp = _call_with_timeout(
        client.chat.completions.create,
        timeout,
        model=ollama_model,
        messages=[{"role": "system", "content": prompt}],
        max_tokens=settings.CONFIG.get("rewrite_max_tokens", 200),
        n=1,
        temperature=settings.CONFIG.get("rewrite_temperature", 0.1),
    )
    if resp is None:
        print(YELLOW + "Rewrite timed out or failed; using original query." + RESET_COLOR)
        return json.dumps({"Rewritten Query": user_input})
    rewritten_query = resp.choices[0].message.content.strip()
    return json.dumps({"Rewritten Query": rewritten_query})


def ollama_chat(
    user_input,
    system_message,
    vault_embeddings,
    vault_content,
    ollama_model,
    conversation_history,
    top_k=3,
    stream=False,
    max_continuations=None,
    per_call_max_tokens=None,
    enable_thinking_summary=False,
):
    conversation_history.append({"role": "user", "content": user_input})

    if len(conversation_history) > 1:
        query_json = {"Query": user_input, "Rewritten Query": ""}
        rewritten_query_json = rewrite_query(json.dumps(query_json), conversation_history, ollama_model)
        rewritten_query_data = json.loads(rewritten_query_json)
        rewritten_query = rewritten_query_data["Rewritten Query"]
        print(PINK + "Original Query: " + user_input + RESET_COLOR)
        print(PINK + "Rewritten Query: " + rewritten_query + RESET_COLOR)
    else:
        rewritten_query = user_input

    retrieved_chunks = get_relevant_context(rewritten_query, vault_embeddings, vault_content, top_k=top_k)
    user_input_with_context, source_blocks = chat_service.build_context_prompt(
        user_input,
        retrieved_chunks,
        top_k,
        settings,
    )
    fmt.print_context_blocks(source_blocks, chat_service.context_blocks_to_text)

    conversation_history[-1]["content"] = user_input_with_context
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

    timeout = settings.CONFIG.get("model_timeout", 120)
    response = _call_with_timeout(
        client.chat.completions.create,
        timeout,
        model=ollama_model,
        messages=messages,
        max_tokens=settings.CONFIG.get("chat_max_tokens", 4000),
    )
    if response is None:
        return "Sorry, the chat request timed out or failed."

    try:
        resp_text = response.choices[0].message.content
    except Exception as exc:
        print(YELLOW + f"Chat response parsing failed: {exc}" + RESET_COLOR)
        return "Sorry, the chat request failed."

    resp_text = chat_service.render_answer_with_citations(resp_text, source_blocks, settings=settings, top_k=top_k)

    thinking, final = split_think_and_final(resp_text)
    auto_finalize = settings.CONFIG.get("auto_finalize_thoughts", False)

    if thinking:
        print(PINK + "Assistant internal reasoning (thinking):" + RESET_COLOR)
        print(CYAN + thinking + RESET_COLOR)
        if final:
            print(NEON_GREEN + "Final Answer (detected):" + RESET_COLOR)
            print(final)
            conversation_history.append({"role": "assistant", "content": final})
            return final
        if auto_finalize:
            final_text = finalize_draft(thinking, ollama_model)
            if final_text:
                print(NEON_GREEN + "Final Answer (derived):" + RESET_COLOR)
                print(final_text)
                conversation_history.append({"role": "assistant", "content": final_text})
                return final_text
        conversation_history.append({"role": "assistant", "content": resp_text})
        return resp_text

    content = final if final else resp_text
    conversation_history.append({"role": "assistant", "content": content})
    return content


def main():
    global client

    print(NEON_GREEN + "Parsing command-line arguments..." + RESET_COLOR)
    parser = argparse.ArgumentParser(description="Ollama Chat")
    parser.add_argument(
        "--model",
        default=settings.CONFIG.get("ollama_model", "llama3"),
        help="Ollama model to use (default from config.yaml)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=settings.CONFIG.get("top_k", 3),
        help="Number of top relevant chunks to include (default from config.yaml)",
    )
    parser.add_argument(
        "--multi-pass",
        action="store_true",
        default=settings.CONFIG.get("multi_pass", False),
        help="Enable multi-pass A/B refinement (default from config.yaml)",
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

    print(NEON_GREEN + "Initializing Ollama API client..." + RESET_COLOR)
    client = OpenAI(
        base_url=settings.CONFIG.get("ollama_api", {}).get("base_url", "http://localhost:11434/v1"),
        api_key=settings.CONFIG.get("ollama_api", {}).get("api_key"),
    )

    print("Starting conversation loop...")
    conversation_history = []
    system_message = settings.CONFIG.get(
        "system_message",
        "You are a helpful assistant that is an expert at extracting the most useful information from a given text. Also bring in extra relevant information to the user query from outside the given context.",
    )

    while True:
        user_input = input(YELLOW + "Ask a query about your documents (or type 'quit' to exit): " + RESET_COLOR)
        if user_input.lower() == "quit":
            break

        response = ollama_chat(
            user_input,
            system_message,
            None,
            [],
            args.model,
            conversation_history,
            top_k=args.top_k,
            stream=args.stream,
            max_continuations=args.max_continuations,
            per_call_max_tokens=args.per_call_max_tokens,
            enable_thinking_summary=args.enable_thinking_summary,
        )
        if args.stream:
            print(NEON_GREEN + "First-pass (A) Response complete." + RESET_COLOR)
        else:
            print(NEON_GREEN + "First-pass (A) Response: \n\n" + response + RESET_COLOR)

        if getattr(args, "multi_pass", settings.CONFIG.get("multi_pass", False)):
            try:
                print(NEON_GREEN + "Running multi-pass refinement (B)..." + RESET_COLOR)
                extra_top_k = max(1, args.top_k * 2)
                extra_rows = get_relevant_context(user_input, None, [], top_k=extra_top_k)
                _, extra_blocks = chat_service.build_context_prompt(user_input, extra_rows, extra_top_k, settings)
                extra_context_str = chat_service.context_blocks_to_text(extra_blocks)
                refine_prompt = (
                    f"Refine the previous assistant response to the query:\n{user_input}\n\n"
                    f"Previous response:\n{response}\n\n"
                    f"Additional context (may be empty):\n{extra_context_str}\n\n"
                    "Produce a concise, corrected and improved final answer based on the additional context."
                )
                refined = ollama_chat(
                    refine_prompt,
                    system_message,
                    None,
                    [],
                    args.model,
                    conversation_history,
                    top_k=extra_top_k,
                    stream=args.stream,
                    max_continuations=args.max_continuations,
                    per_call_max_tokens=args.per_call_max_tokens,
                    enable_thinking_summary=args.enable_thinking_summary,
                )
                if args.stream:
                    print(NEON_GREEN + "Refined (B) Response complete." + RESET_COLOR)
                else:
                    print(NEON_GREEN + "Refined (B) Response: \n\n" + refined + RESET_COLOR)
                response = refined
            except Exception as exc:
                print(YELLOW + f"Multi-pass refinement failed: {exc}" + RESET_COLOR)

        if args.stream:
            print(NEON_GREEN + "Final Response complete." + RESET_COLOR)
        else:
            print(NEON_GREEN + "Final Response: \n\n" + response + RESET_COLOR)

import os
import time
from openai import OpenAI
import argparse
from app.config import runtime_settings as settings
from app.retrieval import hybrid_search as retrieval
from app.chat.citation_prompting import build_citation_prompt, format_source_blocks_text
from app.chat.streaming_llm_client import stream_chat_with_continuation

# ANSI escape codes for colors
PINK = '\033[95m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
NEON_GREEN = '\033[92m'
RESET_COLOR = '\033[0m'

# Helper to call blocking model requests with a timeout to avoid indefinite hangs.

def _call_with_timeout(func, timeout_sec=30, *args, **kwargs):
    import concurrent.futures
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        print(YELLOW + f"Model request timed out after {timeout_sec} seconds." + RESET_COLOR)
        return None
    except Exception as e:
        print(YELLOW + f"Model request failed: {e}" + RESET_COLOR)
        return None

def load_config(config_file):
    # Delegate to shared settings loader
    return settings.load_settings(config_file)

def open_file(filepath):
    print("Opening file...")
    try:
        with open(filepath, 'r', encoding='utf-8') as infile:
            return infile.read()
    except FileNotFoundError:
        print(f"File '{filepath}' not found.")
        return None

def get_relevant_context(rewritten_input, vault_embeddings, vault_content, top_k):
    try:
        return retrieval.scored_chunks(rewritten_input, top_k=top_k)
    except Exception as e:
        print(f"Retrieval failed: {e}")
        return []

def ollama_chat(
    user_input,
    system_message,
    vault_embeddings,
    vault_content,
    ollama_model,
    conversation_history,
    top_k,
    client,
    stream=False,
    max_continuations=None,
    per_call_max_tokens=None,
    enable_thinking_summary=False,
):
    retrieved_chunks = get_relevant_context(user_input, vault_embeddings, vault_content, top_k)
    user_input_with_context, source_blocks = build_citation_prompt(
        user_input,
        retrieved_chunks,
        max_sources=top_k,
        max_snippet_chars=int(settings.CONFIG.get("citation_max_snippet_chars", 500)),
    )
    if source_blocks:
        print("Context Pulled from Documents: \n\n" + CYAN + format_source_blocks_text(source_blocks) + RESET_COLOR)
    else:
        print("No relevant context found.")

    conversation_history.append({"role": "user", "content": user_input_with_context})
    messages = [{"role": "system", "content": system_message}, *conversation_history]

    if stream:
        provider_timeout = settings.CONFIG.get('provider_timeout_s', settings.CONFIG.get('model_timeout', 120))
        flush_interval_ms = settings.CONFIG.get('flush_interval_ms', 250)
        effective_per_call_tokens = per_call_max_tokens or settings.CONFIG.get(
            'per_call_max_tokens',
            settings.CONFIG.get('chat_max_tokens', 2000),
        )
        effective_max_continuations = (
            settings.CONFIG.get('max_continuations', 2)
            if max_continuations is None
            else max_continuations
        )
        continuation_instruction = settings.CONFIG.get(
            'continuation_instruction',
            'Continue exactly where you left off. Do not repeat prior text.',
        )

        done_text = ""
        saw_delta = False
        stream_failed = False
        last_token_at = time.monotonic()
        last_keepalive_notice_at = 0.0
        for event in stream_chat_with_continuation(
            client,
            model=ollama_model,
            messages=messages,
            per_call_max_tokens=effective_per_call_tokens,
            continuation_instruction=continuation_instruction,
            max_continuations=effective_max_continuations,
            timeout=provider_timeout,
            flush_interval_ms=flush_interval_ms,
            enable_thinking_summary=enable_thinking_summary,
        ):
            event_name = event.get('event')
            data = event.get('data', {})
            if event_name == 'final_delta':
                text = data.get('text', '')
                if text:
                    print(NEON_GREEN + text + RESET_COLOR, end='', flush=True)
                    saw_delta = True
                    last_token_at = time.monotonic()
            elif event_name == 'meta' and data.get('kind') == 'keepalive':
                now = time.monotonic()
                if now - last_token_at >= 3.0 and now - last_keepalive_notice_at >= 3.0:
                    print("\n" + YELLOW + "[still generating...]" + RESET_COLOR)
                    last_keepalive_notice_at = now
            elif event_name == 'thinking_delta':
                summary = data.get('text', '').strip()
                if summary:
                    print("\n" + PINK + "Thinking summary:" + RESET_COLOR + " " + CYAN + summary + RESET_COLOR)
            elif event_name == 'error':
                stream_failed = True
                detail = data.get('detail') or data.get('message') or 'unknown streaming error'
                print("\n" + YELLOW + f"Streaming error: {detail}" + RESET_COLOR)
            elif event_name == 'done':
                done_text = data.get('text', '')
                if saw_delta:
                    print()

        if stream_failed and not done_text:
            return "An error occurred while processing your request (timeout or failure)."
        if not done_text:
            done_text = "An error occurred while processing your request (timeout or failure)."
        conversation_history.append({"role": "assistant", "content": done_text})
        return done_text

    timeout = settings.CONFIG.get('model_timeout', 30)
    resp = _call_with_timeout(client.chat.completions.create, timeout, model=ollama_model, messages=messages, max_tokens=settings.CONFIG.get('chat_max_tokens', 2000))
    if resp is None:
        return "An error occurred while processing your request (timeout or failure)."
    try:
        conversation_history.append({"role": "assistant", "content": resp.choices[0].message.content})
        return resp.choices[0].message.content
    except Exception as e:
        print(f"Error in Ollama chat: {e}")
        return "An error occurred while processing your request."

def main():
    parser = argparse.ArgumentParser(description="Ollama Chat")
    parser.add_argument("--config", default="config.yaml", help="Path to the configuration file")
    parser.add_argument("--model", help="Model to use for embeddings and responses")
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
        default=settings.CONFIG.get("per_call_max_tokens", settings.CONFIG.get("chat_max_tokens", 2000)),
        help="Token cap per streaming call before continuation.",
    )
    parser.add_argument(
        "--enable-thinking-summary",
        action=argparse.BooleanOptionalAction,
        default=settings.CONFIG.get("enable_thinking_summary", False),
        help="Enable optional short thinking summary emission (off by default).",
    )

    args = parser.parse_args()

    config = load_config(args.config)

    if args.model:
        config["ollama_model"] = args.model

    # Use data/* storage via retrieval; no vault.txt or in-memory torch embeddings
    vault_content = []
    vault_embeddings_tensor = None

    client = OpenAI(
        base_url=config["ollama_api"]["base_url"],
        api_key=config["ollama_api"]["api_key"]
    )

    conversation_history = []
    system_message = config["system_message"]

    while True:
        user_input = input(YELLOW + "Ask a question about your documents (or type 'quit' to exit): " + RESET_COLOR)
        if user_input.lower() == 'quit':
            break
        response = ollama_chat(
            user_input,
            system_message,
            vault_embeddings_tensor,
            vault_content,
            config["ollama_model"],
            conversation_history,
            config["top_k"],
            client,
            stream=args.stream,
            max_continuations=args.max_continuations,
            per_call_max_tokens=args.per_call_max_tokens,
            enable_thinking_summary=args.enable_thinking_summary,
        )
        if args.stream:
            print(NEON_GREEN + "Response complete." + RESET_COLOR)
        else:
            print(NEON_GREEN + "Response: \n\n" + response + RESET_COLOR)


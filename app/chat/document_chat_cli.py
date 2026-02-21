import os
import time
from openai import OpenAI
import argparse
import json
from app.config import runtime_settings as settings
from app.retrieval import hybrid_search as retrieval
from app.chat.citation_prompting import build_citation_prompt, format_source_blocks_text
from app.chat.citation_formatter import render_citation_output
from app.chat.streaming_llm_client import stream_chat_with_continuation

client = None

# Embedding chunking to avoid model context length limits
def chunk_text(text, max_chars=1000, overlap=100):
    # Allow overriding from config.yaml
    max_chars = settings.CONFIG.get('chunk_max_chars', max_chars)
    overlap = settings.CONFIG.get('chunk_overlap_chars', overlap)
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


# Split model reply into internal 'thinking' and final answer when markers are present.
# Returns (thinking:str|None, final:str|None)
def split_think_and_final(text):
    if not text:
        return (None, None)
    import re
    # look for explicit <think> tag
    m = re.search(r'(?i)<think\b', text)
    if m:
        # find end of opening tag
        tag_close = text.find('>', m.end())
        start = tag_close + 1 if tag_close != -1 else m.end()
        # look for closing tag
        close = re.search(r'(?i)</think>', text[start:])
        if close:
            thinking = text[start:start+close.start()].strip()
            rest = text[start+close.end():].strip()
            final = rest if rest else None
            return (thinking, final)
        # no closing tag; attempt to find a final marker after start
        fm = re.search(r'(?i)(\n\n|\r\n\r\n)(final answer[:\s]|final[:\s]|\*\*final\*\*)', text[start:])
        if fm:
            thinking = text[start:start+fm.start()].strip()
            final = text[start+fm.end():].strip()
            return (thinking, final if final else None)
        # fallback: whole remainder is thinking
        return (text[start:].strip(), None)

    # no <think> tag: look for explicit final markers
    fm = re.search(r'(?i)(final answer[:\s]|final[:\s]|\*\*final\*\*|# final)', text)
    if fm:
        final = text[fm.end():].strip()
        thinking = text[:fm.start()].strip() or None
        return (thinking, final)

    # nothing to split: treat whole as final
    return (None, text.strip())


# Given a draft that contains internal thinking, ask the model to produce a concise final answer only.
def finalize_draft(draft_text, ollama_model):
    if not draft_text:
        return None
    system_msg = (
        "You are a concise assistant. Given the draft below which may contain internal reasoning, "
        "produce a concise final answer only (no chain-of-thought), and return only the answer text."
    )
    messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": "Draft:\n\n" + draft_text}]
    timeout = settings.CONFIG.get('model_timeout', 120)
    resp = _call_with_timeout(
        client.chat.completions.create,
        timeout,
        model=ollama_model,
        messages=messages,
        max_tokens=settings.CONFIG.get('finalize_max_tokens', 400),
        temperature=settings.CONFIG.get('finalize_temperature', 0.0),
    )
    if resp is None:
        return None
    try:
        return resp.choices[0].message.content.strip()
    except Exception:
        return None

# Function to open a file and return its contents as a string
def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

# Function to get relevant context using the new data/* storage via retrieval
def get_relevant_context(rewritten_input, vault_embeddings, vault_content, top_k=3):
    try:
        return retrieval.scored_chunks(rewritten_input, top_k=top_k)
    except Exception as e:
        print(YELLOW + f"Retrieval failed: {e}" + RESET_COLOR)
        return []

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
    timeout = settings.CONFIG.get('model_timeout', 30)
    resp = _call_with_timeout(
        client.chat.completions.create,
        timeout,
        model=ollama_model,
        messages=[{"role": "system", "content": prompt}],
        max_tokens=settings.CONFIG.get('rewrite_max_tokens', 200),
        n=1,
        temperature=settings.CONFIG.get('rewrite_temperature', 0.1),
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
    citations_mode = settings.CONFIG.get("citations_mode", "inline")
    citations_enabled = bool(settings.CONFIG.get("citations", True))
    effective_mode = citations_mode if citations_enabled else "none"
    max_sources = int(settings.CONFIG.get("citation_max_sources", top_k))
    max_snippet_chars = int(settings.CONFIG.get("citation_max_snippet_chars", 240))

    conversation_history.append({"role": "user", "content": user_input})
    
    if len(conversation_history) > 1:
        query_json = {
            "Query": user_input,
            "Rewritten Query": ""
        }
        rewritten_query_json = rewrite_query(json.dumps(query_json), conversation_history, ollama_model)
        rewritten_query_data = json.loads(rewritten_query_json)
        rewritten_query = rewritten_query_data["Rewritten Query"]
        print(PINK + "Original Query: " + user_input + RESET_COLOR)
        print(PINK + "Rewritten Query: " + rewritten_query + RESET_COLOR)
    else:
        rewritten_query = user_input
    
    retrieved_chunks = get_relevant_context(rewritten_query, vault_embeddings, vault_content, top_k=top_k)
    user_input_with_context, source_blocks = build_citation_prompt(
        user_input,
        retrieved_chunks,
        max_sources=top_k,
        max_snippet_chars=int(settings.CONFIG.get("citation_max_snippet_chars", 500)),
    )
    if source_blocks:
        print("Context Pulled from Documents: \n\n" + CYAN + format_source_blocks_text(source_blocks) + RESET_COLOR)
    else:
        print(CYAN + "No relevant context found." + RESET_COLOR)
    
    conversation_history[-1]["content"] = user_input_with_context
    
    messages = [
        {"role": "system", "content": system_message},
        *conversation_history
    ]
    
    if stream:
        provider_timeout = settings.CONFIG.get('provider_timeout_s', settings.CONFIG.get('model_timeout', 120))
        flush_interval_ms = settings.CONFIG.get('flush_interval_ms', 250)
        effective_per_call_tokens = per_call_max_tokens or settings.CONFIG.get(
            'per_call_max_tokens',
            settings.CONFIG.get('chat_max_tokens', 4000),
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
            return "Sorry, the chat request timed out or failed."

        if not done_text:
            done_text = "Sorry, the chat request timed out or failed."

        rendered = render_citation_output(
            done_text,
            source_blocks,
            mode=effective_mode,
            max_sources=max_sources,
            max_snippet_chars=max_snippet_chars,
        )
        if rendered["sources_text"]:
            print(rendered["sources_text"])
        conversation_history.append({"role": "assistant", "content": rendered["answer"]})
        return rendered["answer"]

    timeout = settings.CONFIG.get('model_timeout', 120)
    response = _call_with_timeout(
        client.chat.completions.create,
        timeout,
        model=ollama_model,
        messages=messages,
        max_tokens=settings.CONFIG.get('chat_max_tokens', 4000),
    )
    if response is None:
        return "Sorry, the chat request timed out or failed."
    try:
        resp_text = response.choices[0].message.content
    except Exception as e:
        print(YELLOW + f"Chat response parsing failed: {e}" + RESET_COLOR)
        return "Sorry, the chat request failed."

    rendered = render_citation_output(
        resp_text,
        source_blocks,
        mode=effective_mode,
        max_sources=max_sources,
        max_snippet_chars=max_snippet_chars,
    )
    if rendered["sources_text"]:
        print(rendered["sources_text"])
    resp_text = rendered["answer"]

    thinking, final = split_think_and_final(resp_text)
    auto_finalize = settings.CONFIG.get('auto_finalize_thoughts', False)

    if thinking:
        print(PINK + "Assistant internal reasoning (thinking):" + RESET_COLOR)
        print(CYAN + thinking + RESET_COLOR)
        if final:
            print(NEON_GREEN + "Final Answer (detected):" + RESET_COLOR)
            print(final)
            conversation_history.append({"role": "assistant", "content": final})
            return final
        elif auto_finalize:
            final_text = finalize_draft(thinking, ollama_model)
            if final_text:
                print(NEON_GREEN + "Final Answer (derived):" + RESET_COLOR)
                print(final_text)
                conversation_history.append({"role": "assistant", "content": final_text})
                return final_text
            else:
                conversation_history.append({"role": "assistant", "content": resp_text})
                return resp_text
        else:
            conversation_history.append({"role": "assistant", "content": resp_text})
            return resp_text
    else:
        # treat as final answer
        content = final if final else resp_text
        conversation_history.append({"role": "assistant", "content": content})
        return content

def main():
    global client

    # Parse command-line arguments
    print(NEON_GREEN + "Parsing command-line arguments..." + RESET_COLOR)
    parser = argparse.ArgumentParser(description="Ollama Chat")
    parser.add_argument("--model", default=settings.CONFIG.get("ollama_model", "llama3"), help="Ollama model to use (default from config.yaml)")
    parser.add_argument("--top-k", type=int, default=settings.CONFIG.get("top_k", 3), help="Number of top relevant chunks to include (default from config.yaml)")
    parser.add_argument("--multi-pass", action='store_true', default=settings.CONFIG.get('multi_pass', False), help="Enable multi-pass A/B refinement (default from config.yaml)")
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

    # Configuration for the Ollama API client
    print(NEON_GREEN + "Initializing Ollama API client..." + RESET_COLOR)
    client = OpenAI(
        base_url=settings.CONFIG.get("ollama_api", {}).get("base_url", "http://localhost:11434/v1"),
        api_key=settings.CONFIG.get("ollama_api", {}).get("api_key")
    )

    # Using data/* storage via retrieval; no vault.txt or in-memory torch embeddings
    vault_content = []
    vault_embeddings_tensor = None

    # Conversation loop
    print("Starting conversation loop...")
    conversation_history = []
    system_message = settings.CONFIG.get("system_message", "You are a helpful assistant that is an expert at extracting the most useful information from a given text. Also bring in extra relevant information to the user query from outside the given context.")

    while True:
        user_input = input(YELLOW + "Ask a query about your documents (or type 'quit' to exit): " + RESET_COLOR)
        if user_input.lower() == 'quit':
            break

        response = ollama_chat(
            user_input,
            system_message,
            vault_embeddings_tensor,
            vault_content,
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

        # Multi-pass A/B refinement: run a second pass with wider retrieval and ask model to refine
        if getattr(args, 'multi_pass', settings.CONFIG.get('multi_pass', False)):
            try:
                print(NEON_GREEN + "Running multi-pass refinement (B)..." + RESET_COLOR)
                extra_top_k = max(1, args.top_k * 2)
                extra_rows = get_relevant_context(user_input, vault_embeddings_tensor, vault_content, top_k=extra_top_k)
                _, extra_blocks = build_citation_prompt(
                    user_input,
                    extra_rows,
                    max_sources=extra_top_k,
                    max_snippet_chars=int(settings.CONFIG.get("citation_max_snippet_chars", 500)),
                )
                extra_context_str = format_source_blocks_text(extra_blocks)
                refine_prompt = f"Refine the previous assistant response to the query:\n{user_input}\n\nPrevious response:\n{response}\n\nAdditional context (may be empty):\n{extra_context_str}\n\nProduce a concise, corrected and improved final answer based on the additional context."
                refined = ollama_chat(
                    refine_prompt,
                    system_message,
                    vault_embeddings_tensor,
                    vault_content,
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
            except Exception as e:
                print(YELLOW + f"Multi-pass refinement failed: {e}" + RESET_COLOR)

        if args.stream:
            print(NEON_GREEN + "Final Response complete." + RESET_COLOR)
        else:
            print(NEON_GREEN + "Final Response: \n\n" + response + RESET_COLOR)

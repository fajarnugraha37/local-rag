import os
import time
from openai import OpenAI
import argparse
from app.config import runtime_settings as settings
from app.retrieval import hybrid_search as retrieval
from app.chat.citation_prompting import build_citation_prompt, format_source_blocks_text
from app.chat.streaming_llm_client import stream_chat_with_continuation

client = None

# ANSI escape codes for colors
PINK = '\033[95m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
NEON_GREEN = '\033[92m'
RESET_COLOR = '\033[0m'

# Function to open a file and return its contents as a string
def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

# Function to get relevant context using retrieval from data/* storage
def get_relevant_context(rewritten_input, vault_embeddings, vault_content, top_k=3):
    try:
        return retrieval.scored_chunks(rewritten_input, top_k=top_k)
    except Exception as e:
        print(YELLOW + f"Retrieval failed: {e}" + RESET_COLOR)
        return []

# Function to interact with the Ollama model
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
    # Get relevant context from the vault
    retrieved_chunks = get_relevant_context(user_input, vault_embeddings, vault_content, top_k=settings.CONFIG.get("top_k", 3))
    user_input_with_context, source_blocks = build_citation_prompt(
        user_input,
        retrieved_chunks,
        max_sources=settings.CONFIG.get("top_k", 3),
        max_snippet_chars=int(settings.CONFIG.get("citation_max_snippet_chars", 500)),
    )
    if source_blocks:
        print("Context Pulled from Documents: \n\n" + CYAN + format_source_blocks_text(source_blocks) + RESET_COLOR)
    else:
        print(CYAN + "No relevant context found." + RESET_COLOR)
    
    # Append the user's input to the conversation history
    conversation_history.append({"role": "user", "content": user_input_with_context})
    
    # Create a message history including the system message and the conversation history
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

        conversation_history.append({"role": "assistant", "content": done_text})
        return done_text

    # Send the completion request to the Ollama model
    response = client.chat.completions.create(
        model=ollama_model,
        messages=messages
    )

    # Append the model's response to the conversation history
    conversation_history.append({"role": "assistant", "content": response.choices[0].message.content})

    # Return the content of the response from the model
    return response.choices[0].message.content

def main():
    global client

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Ollama Chat")
    parser.add_argument("--model", default=settings.CONFIG.get("ollama_model", "hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest"), help="Ollama model to use (default from config.yaml)")
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
    args = parser.parse_args()

    # Configuration for the Ollama API client
    client = OpenAI(
        base_url=settings.CONFIG.get("ollama_api", {}).get("base_url", "http://localhost:11434/v1"),
        api_key=settings.CONFIG.get("ollama_api", {}).get("api_key")
    )

    # Using data/* storage via retrieval; no vault.txt or in-memory torch embeddings
    vault_content = []
    vault_embeddings_tensor = None

    # Conversation loop
    conversation_history = []
    system_message = settings.CONFIG.get("system_message", "You are a helpful assistant that is an expert at extracting the most useful information from a given text")

    while True:
        user_input = input(YELLOW + "Ask a question about your documents (or type 'quit' to exit): " + RESET_COLOR)
        if user_input.lower() == 'quit':
            break

        response = ollama_chat(
            user_input,
            system_message,
            vault_embeddings_tensor,
            vault_content,
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


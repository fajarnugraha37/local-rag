"""Shared CLI formatting helpers for chat entrypoints."""

PINK = "\033[95m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
NEON_GREEN = "\033[92m"
RESET_COLOR = "\033[0m"


def print_context_blocks(source_blocks, format_source_blocks_text):
    if source_blocks:
        print("Context Pulled from Documents: \n\n" + CYAN + format_source_blocks_text(source_blocks) + RESET_COLOR)
    else:
        print(CYAN + "No relevant context found." + RESET_COLOR)


def print_stream_delta(text: str):
    print(NEON_GREEN + text + RESET_COLOR, end="", flush=True)


def print_stream_keepalive():
    print("\n" + YELLOW + "[still generating...]" + RESET_COLOR)


def print_thinking_summary(summary: str):
    print("\n" + PINK + "Thinking summary:" + RESET_COLOR + " " + CYAN + summary + RESET_COLOR)


def print_stream_error(detail: str):
    print("\n" + YELLOW + f"Streaming error: {detail}" + RESET_COLOR)

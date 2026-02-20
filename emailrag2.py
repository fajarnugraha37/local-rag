import os
import json
from openai import OpenAI
import argparse
import yaml
import datetime
import settings
import retrieval

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

def load_or_generate_embeddings(vault_content, embeddings_file):
    # Load existing embeddings if valid; otherwise regenerate and persist
    if os.path.exists(embeddings_file):
        print(f"Loading embeddings from '{embeddings_file}'...")
        try:
            with open(embeddings_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            # Validate structure and length when vault content is present
            if not isinstance(data, list) or (len(vault_content) > 0 and len(data) != len(vault_content)):
                print(f"Embeddings file '{embeddings_file}' is invalid or mismatched (expected {len(vault_content)} embeddings, got {len(data) if isinstance(data, list) else 'non-list'})")
                raise ValueError("Invalid embeddings data")
            return torch.tensor(data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Embeddings cache corrupted or invalid: {e}")
            # Back up corrupted file for inspection
            try:
                ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                corrupt_path = embeddings_file + f".corrupt.{ts}"
                os.rename(embeddings_file, corrupt_path)
                print(f"Backed up corrupted embeddings to '{corrupt_path}'")
            except Exception as be:
                print(f"Failed to back up corrupted embeddings file: {be}")
            # Regenerate and save
            embeddings = generate_embeddings(vault_content)
            save_embeddings(embeddings, embeddings_file)
            return torch.tensor(embeddings)
    else:
        print(f"No embeddings found. Generating new embeddings...")
        embeddings = generate_embeddings(vault_content)
        save_embeddings(embeddings, embeddings_file)
        return torch.tensor(embeddings)

def generate_embeddings(vault_content):
    print("Generating embeddings...")
    embeddings = []
    for content in vault_content:
        try:
            emb_model = settings.CONFIG.get('embedding_model', 'mxbai-embed-large')
            response = ollama.embeddings(model=emb_model, prompt=content)
            embeddings.append(response["embedding"])
        except Exception as e:
            print(f"Error generating embeddings: {str(e)}")
    return embeddings

def save_embeddings(embeddings, embeddings_file):
    print(f"Saving embeddings to '{embeddings_file}'...")
    try:
        with open(embeddings_file, "w", encoding="utf-8") as file:
            json.dump(embeddings, file)
    except Exception as e:
        print(f"Error saving embeddings: {str(e)}")

def get_relevant_context(rewritten_input, vault_embeddings, vault_content, top_k):
    try:
        results = retrieval.scored_chunks(rewritten_input, top_k=top_k)
        return [r.get('text','').strip() for r in results]
    except Exception as e:
        print(f"Retrieval failed: {e}")
        return []

def ollama_chat(user_input, system_message, vault_embeddings, vault_content, ollama_model, conversation_history, top_k, client):
    relevant_context = get_relevant_context(user_input, vault_embeddings, vault_content, top_k)
    if relevant_context:
        context_str = "\n".join(relevant_context)
        print("Context Pulled from Documents: \n\n" + CYAN + context_str + RESET_COLOR)
    else:
        print("No relevant context found.")

    user_input_with_context = user_input
    if relevant_context:
        user_input_with_context = context_str + "\n\n" + user_input

    conversation_history.append({"role": "user", "content": user_input_with_context})
    messages = [{"role": "system", "content": system_message}, *conversation_history]

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
    parser.add_argument("--clear-cache", action="store_true", help="Clear the embeddings cache")
    parser.add_argument("--model", help="Model to use for embeddings and responses")

    args = parser.parse_args()

    config = load_config(args.config)

    if args.clear_cache and os.path.exists(config["embeddings_file"]):
        print(f"Clearing embeddings cache at '{config['embeddings_file']}'...")
        os.remove(config["embeddings_file"])

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
        response = ollama_chat(user_input, system_message, vault_embeddings_tensor, vault_content, config["ollama_model"], conversation_history, config["top_k"], client)
        print(NEON_GREEN + "Response: \n\n" + response + RESET_COLOR)

if __name__ == "__main__":
    main()

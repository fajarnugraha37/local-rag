import torch
import ollama
import os
import json
from openai import OpenAI
import argparse
import yaml
import datetime
import settings

# ANSI escape codes for colors
PINK = '\033[95m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
NEON_GREEN = '\033[92m'
RESET_COLOR = '\033[0m'

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
            response = ollama.embeddings(model='mxbai-embed-large', prompt=content)
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
    print("Retrieving relevant context...")
    if vault_embeddings.nelement() == 0:
        return []
    try:
        input_embedding = ollama.embeddings(model='mxbai-embed-large', prompt=rewritten_input)["embedding"]
        cos_scores = torch.cosine_similarity(torch.tensor(input_embedding).unsqueeze(0), vault_embeddings)
        top_k = min(top_k, len(cos_scores))
        top_indices = torch.topk(cos_scores, k=top_k)[1].tolist()
        return [vault_content[idx].strip() for idx in top_indices]
    except Exception as e:
        print(f"Error getting relevant context: {str(e)}")
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

    try:
        response = client.chat.completions.create(
            model=ollama_model,
            messages=messages
        )
        conversation_history.append({"role": "assistant", "content": response.choices[0].message.content})
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in Ollama chat: {str(e)}")
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

    vault_content = []
    if os.path.exists(config["vault_file"]):
        print(f"Loading content from vault '{config['vault_file']}'...")
        with open(config["vault_file"], "r", encoding='utf-8') as vault_file:
            vault_content = vault_file.readlines()

    vault_embeddings_tensor = load_or_generate_embeddings(vault_content, config["embeddings_file"])

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

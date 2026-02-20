import os
from openai import OpenAI
import argparse
import settings
import retrieval

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
        results = retrieval.scored_chunks(rewritten_input, top_k=top_k)
        return [r.get('text','').strip() for r in results]
    except Exception as e:
        print(YELLOW + f"Retrieval failed: {e}" + RESET_COLOR)
        return []

# Function to interact with the Ollama model
def ollama_chat(user_input, system_message, vault_embeddings, vault_content, ollama_model, conversation_history):
    # Get relevant context from the vault
    relevant_context = get_relevant_context(user_input, vault_embeddings, vault_content, top_k=settings.CONFIG.get("top_k", 3))
    if relevant_context:
        # Convert list to a single string with newlines between items
        context_str = "\n".join(relevant_context)
        print("Context Pulled from Documents: \n\n" + CYAN + context_str + RESET_COLOR)
    else:
        print(CYAN + "No relevant context found." + RESET_COLOR)
    
    # Prepare the user's input by concatenating it with the relevant context
    user_input_with_context = user_input
    if relevant_context:
        user_input_with_context = context_str + "\n\n" + user_input
    
    # Append the user's input to the conversation history
    conversation_history.append({"role": "user", "content": user_input_with_context})
    
    # Create a message history including the system message and the conversation history
    messages = [
        {"role": "system", "content": system_message},
        *conversation_history
    ]
    
    # Send the completion request to the Ollama model
    response = client.chat.completions.create(
        model=ollama_model,
        messages=messages
    )
    
    # Append the model's response to the conversation history
    conversation_history.append({"role": "assistant", "content": response.choices[0].message.content})
    
    # Return the content of the response from the model
    return response.choices[0].message.content

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Ollama Chat")
parser.add_argument("--model", default=settings.CONFIG.get("ollama_model", "hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest"), help="Ollama model to use (default from config.yaml)")
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

    response = ollama_chat(user_input, system_message, vault_embeddings_tensor, vault_content, args.model, conversation_history)
    print(NEON_GREEN + "Response: \n\n" + response + RESET_COLOR)

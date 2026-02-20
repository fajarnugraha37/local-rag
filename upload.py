import os
import tkinter as tk
from tkinter import filedialog
import PyPDF2
import re
import json
import settings
from hashing import sha256_hash

# Helper: sentence-aware chunking
def chunk_sentences(text, max_chars=1000):
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 < max_chars:
            current_chunk += (sentence + " ").strip()
        else:
            chunks.append(current_chunk)
            current_chunk = sentence + " "
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

# Helper: write structured chunk objects to data/chunks.jsonl (deduped)
def write_chunks_file(chunks_list, source_path, chunks_file=None, append_vault=True):
    repo_dir = os.path.dirname(__file__)
    if chunks_file is None:
        chunks_file = os.path.join(repo_dir, 'data', 'chunks.jsonl')
    os.makedirs(os.path.dirname(chunks_file), exist_ok=True)

    # load existing chunk ids
    existing = set()
    if os.path.exists(chunks_file):
        try:
            with open(chunks_file, 'r', encoding='utf-8') as cf:
                for line in cf:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict) and 'chunk_id' in obj:
                            existing.add(obj['chunk_id'])
                    except Exception:
                        continue
        except Exception:
            pass

    new_written = 0
    with open(chunks_file, 'a', encoding='utf-8') as cf:
        for chunk_text in chunks_list:
            text = chunk_text.strip()
            if not text:
                continue
            cid = sha256_hash(text)
            if cid in existing:
                continue
            obj = {
                'chunk_id': cid,
                'doc_id': os.path.basename(source_path) if source_path else os.path.basename(__file__),
                'source': source_path or '',
                'text': text,
                'token_count': len(text.split())
            }
            cf.write(json.dumps(obj, ensure_ascii=False) + '\n')
            existing.add(cid)
            new_written += 1

    # For backward compatibility, also append raw text chunks to vault.txt
    if append_vault:
        try:
            vault_path = settings.CONFIG.get('vault_file', os.path.join(repo_dir, 'vault.txt'))
            with open(vault_path, 'a', encoding='utf-8') as vf:
                for c in chunks_list:
                    vf.write(c.strip() + '\n')
        except Exception:
            pass

    print(f"Wrote {new_written} new chunks to {chunks_file} (appended to vault: {append_vault})")

# Function to convert PDF to text and write structured chunks
def convert_pdf_to_text():
    file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
    if file_path:
        with open(file_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            num_pages = len(pdf_reader.pages)
            text = ''
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                if page.extract_text():
                    text += page.extract_text() + " "

            # Normalize whitespace and clean up text
            text = re.sub(r'\s+', ' ', text).strip()

            # Chunk the text
            chunks = chunk_sentences(text, max_chars=1000)

            write_chunks_file(chunks, file_path)
            print(f"PDF content processed and appended as structured chunks.")

# Function to upload a text file and write structured chunks
def upload_txtfile():
    file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
    if file_path:
        with open(file_path, 'r', encoding="utf-8") as txt_file:
            text = txt_file.read()

            # Normalize whitespace and clean up text
            text = re.sub(r'\s+', ' ', text).strip()

            # Chunk the text
            chunks = chunk_sentences(text, max_chars=1000)

            write_chunks_file(chunks, file_path)
            print(f"Text file content processed and appended as structured chunks.")

# Function to upload a JSON file and write structured chunks
def upload_jsonfile():
    file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
    if file_path:
        with open(file_path, 'r', encoding="utf-8") as json_file:
            data = json.load(json_file)

            # Flatten the JSON data into a single string
            text = json.dumps(data, ensure_ascii=False)

            # Normalize whitespace and clean up text
            text = re.sub(r'\s+', ' ', text).strip()

            # Chunk the text
            chunks = chunk_sentences(text, max_chars=1000)

            write_chunks_file(chunks, file_path)
            print(f"JSON file content processed and appended as structured chunks.")

# Create the main window
root = tk.Tk()
root.title("Upload .pdf, .txt, or .json")

# Create a button to open the file dialog for PDF
pdf_button = tk.Button(root, text="Upload PDF", command=convert_pdf_to_text)
pdf_button.pack(pady=10)

# Create a button to open the file dialog for text file
txt_button = tk.Button(root, text="Upload Text File", command=upload_txtfile)
txt_button.pack(pady=10)

# Create a button to open the file dialog for JSON file
json_button = tk.Button(root, text="Upload JSON File", command=upload_jsonfile)
json_button.pack(pady=10)

# Run the main event loop
root.mainloop()

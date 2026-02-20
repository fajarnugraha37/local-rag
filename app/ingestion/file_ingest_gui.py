import os
import re
import json
from app.config import runtime_settings as settings
from app.ingestion.vector_ingest_service import ingest_chunks

# Helper: sentence-aware chunking
def chunk_sentences(text, max_chars=1000):
    max_chars = settings.CONFIG.get('chunk_max_chars', max_chars)
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

# Helper: write structured chunk objects to vector DB (idempotent upsert)
def write_chunks_file(chunks_list, source_path, chunks_file=None, append_vault=False):
    result = ingest_chunks(chunks_list, source_path=source_path)
    print(f"Wrote {result['added']} new chunks to vector DB (failed={result['failed']}, skipped={result['skipped']})")

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

def main():
    try:
        import tkinter as tk
        from tkinter import filedialog
        import PyPDF2
    except Exception:
        print("GUI components not available; upload utilities are importable for testing.")
    else:
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


if __name__ == "__main__":
    main()

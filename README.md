# SuperEasy 100% Local RAG with Ollama + Email RAG

### YouTube Tutorials
- https://www.youtube.com/watch?v=Oe-7dGDyzPM
- https://www.youtube.com/watch?v=vFGng_3hDRk
### Latest YouTube Updated Features
[![IMAGE ALT TEXT HERE](https://img.youtube.com/vi/0X7raD1kISQ/0.jpg)](https://www.youtube.com/watch?v=0X7raD1kISQ)
### Setup
1. git clone https://github.com/AllAboutAI-YT/easy-local-rag.git
2. cd dir
3. pip install -r requirements.txt
4. Install Ollama (https://ollama.com/download)
5. ollama pull hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest (etc)
6. ollama pull mxbai-embed-large
7. run upload.py (pdf, .txt, JSON)
8. run localrag.py (with query re-write)
9. run localrag_no_rewrite.py (no query re-write)

### Email RAG Setup
1. git clone https://github.com/AllAboutAI-YT/easy-local-rag.git
2. cd dir
3. pip install -r requirements.txt
4. Install Ollama (https://ollama.com/download)
5. ollama pull hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest (etc)
6. ollama pull mxbai-embed-large
7. set YOUR email logins in .env (for gmail create app password (video))
9. python collect_emails.py to download your emails
10. python emailrag2.py to talk to your emails

### Latest Updates
- Added Email RAG Support (v1.3)
- Upload.py (v1.2)
   - replaced /n/n with /n 
- New embeddings model mxbai-embed-large from ollama (1.2)
- Rewrite query function to improve retrival on vauge questions (1.2)
- Pick your model from the CLI (1.1)
  - python localrag.py --model mistral (hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest is default) 
- Talk in a true loop with conversation history (1.1)
   
### My YouTube Channel
https://www.youtube.com/c/AllAboutAI

### What is RAG?
RAG is a way to enhance the capabilities of LLMs by combining their powerful language understanding with targeted retrieval of relevant information from external sources often with using embeddings in vector databases, leading to more accurate, trustworthy, and versatile AI-powered applications

### What is Ollama?
Ollama is an open-source platform that simplifies the process of running powerful LLMs locally on your own machine, giving users more control and flexibility in their AI projects. https://www.ollama.com

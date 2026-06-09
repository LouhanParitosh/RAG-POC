# Complete Beginner's Guide to This RAG Project

> This guide is written for someone who is new to Python, AI, and command-line tools.
> Every concept is explained from scratch. Every command is explained before you run it.
> Read it top to bottom the first time.

---

## Table of Contents

1. [What is this project?](#1-what-is-this-project)
2. [What is RAG?](#2-what-is-rag)
3. [What tools are used and why?](#3-what-tools-are-used-and-why)
4. [How the project is organized](#4-how-the-project-is-organized)
5. [What each file does](#5-what-each-file-does)
6. [One-time setup (do this only once)](#6-one-time-setup-do-this-only-once)
7. [How to add your own documents](#7-how-to-add-your-own-documents)
8. [How to run the app](#8-how-to-run-the-app)
9. [Using the web interface step by step](#9-using-the-web-interface-step-by-step)
10. [What happens under the hood when you ask a question](#10-what-happens-under-the-hood-when-you-ask-a-question)
11. [Common errors and how to fix them](#11-common-errors-and-how-to-fix-them)
12. [Glossary of terms](#12-glossary-of-terms)

---

## 1. What is this project?

This is a **RAG POC** — a Proof of Concept for Retrieval-Augmented Generation.

In simple terms: you give the system your PDF files, and then you can ask it questions. It reads your files and answers using only the content inside them. It does not use the internet. It runs completely on your own computer.

Think of it like this:

> You have a stack of 50 company reports. Instead of reading all of them yourself, you ask a smart assistant: _"What was the revenue in Q3?"_ — and it finds the answer from the exact page of the exact report.

That is what this project does.

---

## 2. What is RAG?

RAG stands for **Retrieval-Augmented Generation**. It has three steps:

### Step 1 — Retrieve
When you ask a question, the system searches your documents for the most relevant paragraphs. It does not search by keywords — it searches by **meaning**. So "car accident" and "vehicle collision" would match each other even though the words are different.

### Step 2 — Augment
The system takes those relevant paragraphs and **adds them to the question** before sending anything to the AI. This gives the AI the right context to answer from.

### Step 3 — Generate
The AI (running locally via Ollama) reads the question + the context paragraphs and generates an answer. It is instructed to only use what is in the paragraphs — so it won't make things up.

Here is the full picture:

```
Your PDF Files
      |
      | (run: python ingest.py)
      v
[Each page is split into small chunks of ~600 characters]
      |
      v
[Each chunk is converted to a list of numbers called an "embedding"]
      |
      v
[All embeddings are saved in a local database called ChromaDB]


Later, when you ask a question:

Your Question
      |
      v
[Question is also converted to an embedding]
      |
      v
[ChromaDB finds the 4 chunks whose embeddings are closest to the question's embedding]
      |
      v
[Those 4 chunks are pasted into a prompt alongside your question]
      |
      v
[Ollama's llama3.2 model reads the prompt and writes an answer]
      |
      v
Answer appears on screen, streamed word by word
```

---

## 3. What tools are used and why?

| Tool | What it is | Why we use it |
|---|---|---|
| **Python** | Programming language | The entire project is written in Python |
| **Ollama** | A program that runs AI models locally | Lets us run AI models on our own computer, no internet or API key needed |
| **nomic-embed-text** | A dedicated embedding model (~274 MB) | Converts text into numbers (embeddings) for similarity search. Purpose-built for this — fast and accurate |
| **llama3.2** | A large language model (~2 GB) | Reads the retrieved context + your question and writes the final answer |
| **ChromaDB** | A local vector database | Stores the embeddings and lets us search them by similarity |
| **LangChain** | A Python library | Helps us load PDF files and split them into chunks |
| **Streamlit** | A Python library | Creates the web UI with zero HTML or JavaScript |
| **Rich** | A Python library | Makes the terminal output look nice with colors and tables |

> **Why two separate models?** Each model is built for a different task. `nomic-embed-text` is trained specifically to produce high-quality embeddings for search. `llama3.2` is trained specifically to generate fluent text answers. Generative models like `llama3.2` technically support embeddings too, but at much lower quality — which is why we keep the roles separate.

---

## 4. How the project is organized

```
RAG- POC/
│
├── app.py              ← The web application (run this to open the UI)
├── ingest.py           ← The ingestion script (run this to process your PDFs)
│
├── rag/                ← The core logic (the "brain" of the system)
│   ├── ingestion.py    ← Loads files, splits into chunks, creates embeddings
│   ├── retriever.py    ← Searches ChromaDB for relevant chunks
│   ├── generator.py    ← Builds the prompt and calls the LLM
│   └── pipeline.py     ← Connects retriever + generator together
│
├── data/               ← PUT YOUR PDF FILES HERE
│
├── chroma_db/          ← Where ChromaDB saves the embeddings (auto-created)
│
├── .venv/              ← The Python virtual environment (auto-created)
│
├── requirements.txt    ← List of Python packages needed
├── README.md           ← Short quick-start guide
└── GUIDE.md            ← This file
```

---

## 5. What each file does

### `rag/ingestion.py` — The Document Processor

This file is responsible for turning your documents into something the computer can search.

**What it does, step by step:**

1. Receives the path to a file (e.g. `data/report.pdf`)
2. Calculates a **fingerprint** (SHA-256 hash) of the file — like a unique ID based on the file's content
3. Checks if this file was already processed before (by looking up the fingerprint in ChromaDB)
   - If it was processed and hasn't changed → skip it (saves time)
   - If it changed → delete the old version and re-process
4. Loads the file using LangChain (handles PDF, TXT, and MD formats)
5. Splits the text into chunks of about 600 characters, with 100 characters of overlap between chunks
   - Overlap is important — it prevents a sentence from being cut off and losing its meaning
6. Sends each chunk to Ollama's `nomic-embed-text` model, which returns a list of 768 numbers (the embedding)
7. Saves all chunks + their embeddings + source metadata into ChromaDB

**Key settings you can change in this file:**

```python
CHUNK_SIZE = 600              # How many characters per chunk. Increase for more context, decrease for more precision.
CHUNK_OVERLAP = 100           # How many characters the next chunk shares with the previous one.
EMBED_MODEL = "nomic-embed-text"  # The Ollama model used for embeddings. Must be an embedding-capable model.
```

---

### `rag/retriever.py` — The Search Engine

This file answers the question: _"Which parts of my documents are most relevant to this question?"_

**What it does, step by step:**

1. Takes your question (plain English text)
2. Sends it to Ollama's `nomic-embed-text` model to get its embedding — **the same model used during ingestion** (this is critical: both sides must use the same model, otherwise the numbers mean different things and similarity search breaks)
3. Asks ChromaDB: "give me the 4 stored chunks whose embeddings are most similar to this question's embedding"
4. Returns those 4 chunks along with:
   - The actual text of the chunk
   - Which file it came from
   - Which page number (for PDFs)
   - A **similarity score** — a percentage showing how relevant the chunk is (higher = more relevant)

**Key setting:**

```python
TOP_K = 4   # How many chunks to retrieve. You can change this in the UI slider too.
```

**About the similarity score:**
- 90%+ means the chunk is very directly about your question
- 60–90% means it's probably related
- Below 40% means it might be a stretch — the system couldn't find a great match

---

### `rag/generator.py` — The Answer Writer

This file talks to the LLM (the actual AI) and gets an answer.

**What it does, step by step:**

1. Takes the retrieved chunks and your question
2. Builds a prompt that looks like this:

```
[Source 1: report.pdf, page 3, similarity 87.2%]
...text of chunk 1...

---

[Source 2: notes.txt, page 0, similarity 74.1%]
...text of chunk 2...

Question: What was the Q3 revenue?
```

3. Sends this prompt to `llama3.2` running in Ollama
4. Streams back the response token by token (like watching someone type in real time)

**The system instruction given to the LLM:**

```
You are a helpful assistant that answers questions strictly based on the provided context.
Rules:
- Only use information from the context below to answer.
- If the context does not contain enough information, say "I don't have enough information..."
- Be concise and accurate.
- Cite the source document name when relevant.
```

This is why the model won't make things up — it is told to only use what's in the context.

**Key setting:**

```python
LLM_MODEL = "llama3.2:latest"   # Change this to "gemma3:4b" if you want a different model.
```

---

### `rag/pipeline.py` — The Coordinator

This is a thin file that simply calls `retriever.py` → `generator.py` in sequence and returns everything together:

- The retrieved chunks
- The full augmented prompt
- The streaming answer

It exists so that `app.py` has one simple function to call instead of managing the steps itself.

---

### `ingest.py` — The CLI Ingestion Script

This is the script you run from the terminal to process your documents.

**What it does:**

1. Scans the `data/` folder (and all subfolders) for `.pdf`, `.txt`, and `.md` files
2. Calls `rag/ingestion.py` for each file
3. Prints a beautiful table showing which files were added, skipped, or had errors
4. At the end, shows the complete list of everything in your knowledge base

**Available options:**

```bash
python ingest.py                         # Normal run — ingest new/changed files
python ingest.py --clear                 # Delete everything first, then re-ingest all files
python ingest.py --data-dir /other/path  # Use a different folder instead of ./data
```

---

### `app.py` — The Web Interface

This is the Streamlit web application. When you run it, it opens a browser tab at `http://localhost:8501`.

**What the interface contains:**

- **Left sidebar:**
  - Upload files directly from your browser (for one-off files)
  - See which files are in your knowledge base and how many chunks they have
  - A slider to control how many chunks to retrieve (Top-K)
  - Buttons to clear the knowledge base or chat history

- **Main area:**
  - A text box to type your question
  - After asking, it shows three expandable sections:
    1. The retrieved chunks with similarity scores and source filenames
    2. The full augmented prompt that was sent to the LLM (so you can see exactly what the AI read)
    3. The streamed answer

- **Session history:**
  - Every question you asked in this session is saved below
  - Each one has tabs for Answer, Retrieved Chunks, and Augmented Prompt

---

## 6. One-time setup (do this only once)

Follow these steps **once** on a fresh machine. After this, you only need steps 7 and 8 every time.

### Step 1 — Make sure Ollama is installed

Open your terminal and type:

```bash
ollama --version
```

If it prints something like `ollama version 0.x.x` — you're good.
If it says "command not found" — go to [https://ollama.ai](https://ollama.ai) and download it.

---

### Step 2 — Make sure Ollama is running

Ollama needs to be running in the background before we use it. Check if it's already running:

```bash
ollama list
```

You should see your installed models listed. If it throws an error, start Ollama:

```bash
ollama serve
```

Leave that terminal open and open a new terminal tab for the next steps.

---

### Step 3 — Pull the required models

This project uses **two models** — one for search, one for answering:

#### Model 1: nomic-embed-text (for embeddings — search)

```bash
ollama pull nomic-embed-text
```

This is 274 MB. It converts text into numbers for similarity search.

#### Model 2: llama3.2 (for generation — writing answers)

Check if it's already installed:

```bash
ollama list
```

If you see `llama3.2:latest` in the list, you already have it. If not:

```bash
ollama pull llama3.2
```

This is about 2 GB.

After both pulls, verify both are present:

```bash
ollama list
# You should see:
# nomic-embed-text:latest   ...   274 MB
# llama3.2:latest           ...   2.0 GB
```

---

### Step 4 — Navigate to the project folder

In your terminal:

```bash
cd "/Users/paritosh/development/RAG- POC"
```

> Note: The folder name has a space in it, so we wrap it in quotes.

---

### Step 5 — Activate the virtual environment

A **virtual environment** is an isolated copy of Python with only the packages this project needs. It prevents conflicts with other Python projects on your machine.

```bash
source .venv/bin/activate
```

After running this, your terminal prompt will change to show `(.venv)` at the start — that tells you the environment is active.

> You need to do this **every time you open a new terminal window** to work on this project.

**To deactivate it later** (when you're done working):

```bash
deactivate
```

---

### Step 6 — Verify everything installed correctly

```bash
python -c "import ollama, chromadb, streamlit, langchain; print('All good!')"
```

If it prints `All good!` — you're fully set up.

---

## 7. How to add your own documents

### Step 1 — Copy your files into the `data/` folder

The `data/` folder is inside the project directory. Just copy or move your files there.

Supported formats:
- `.pdf` — any PDF (scanned PDFs won't work well; text-based PDFs work best)
- `.txt` — plain text files
- `.md` — Markdown files

You can have subfolders too:

```
data/
├── company/
│   ├── annual_report_2024.pdf
│   └── q3_results.pdf
├── technical/
│   └── architecture.md
└── notes.txt
```

---

### Step 2 — Run the ingestion script

Make sure your virtual environment is active (you see `(.venv)` in your terminal), then:

```bash
python ingest.py
```

**Sample output:**

```
RAG Document Ingestion
Found 3 file(s) in ./data

Ingesting... ━━━━━━━━━━━━━━━━━ 3/3

  File                    Status       Chunks
  annual_report_2024.pdf  ✓ added      142
  q3_results.pdf          ✓ added       38
  notes.txt               ✓ added       11

Done. 3 added  0 updated  0 skipped  0 errors  │  191 total chunks in knowledge base
```

Each file is broken into "chunks" — small passages of about 600 characters. The more pages a file has, the more chunks it produces.

---

### Step 3 — What if you change a file?

Just copy the updated file into `data/` (replacing the old one) and run `python ingest.py` again.

The script automatically detects that the file changed (by comparing its fingerprint) and re-ingests it:

```
  annual_report_2024.pdf  ↺ updated    145   ← was 142 before, now 145
  q3_results.pdf          – skipped     38   ← unchanged, skipped
  notes.txt               – skipped     11   ← unchanged, skipped
```

---

### Step 4 — What if you want to start completely fresh?

To wipe all ingested data and start over:

```bash
python ingest.py --clear
```

This deletes everything from ChromaDB and then re-ingests all files in `data/`.

---

## 8. How to run the app

### Every time you want to use the app, do this:

**Step 1 — Open terminal and go to the project folder:**

```bash
cd "/Users/paritosh/development/RAG- POC"
```

**Step 2 — Activate the virtual environment:**

```bash
source .venv/bin/activate
```

Your prompt should show `(.venv)` after this.

**Step 3 — Make sure Ollama is running** (open a separate terminal if needed):

```bash
ollama serve
```

**Step 4 — Start the app:**

```bash
streamlit run app.py
```

**What happens next:**

- You'll see output like this in the terminal:
  ```
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
  ```
- Your browser should open automatically. If it doesn't, open it manually and go to `http://localhost:8501`.
- The app is now running. The terminal must stay open — closing it stops the app.

**To stop the app:** go back to the terminal and press `Ctrl + C`.

---

## 9. Using the web interface step by step

### The sidebar (left panel)

#### Upload Documents
You can drag and drop PDF, TXT, or MD files here for one-off ingestion directly from the browser. These are processed immediately without needing to use `ingest.py`.

> For bulk ingestion of many files, the `python ingest.py` command is faster and more reliable.

#### Ingested Documents
This shows every file currently in your knowledge base and how many chunks it was split into.

#### Settings — Top-K slider
This controls how many chunks the system retrieves for each question. Default is 4.

- **Higher (e.g. 8):** The LLM gets more context. Good for broad questions. But the answer may be slower and less focused.
- **Lower (e.g. 2):** The LLM gets less context. Good for very specific questions with pinpoint answers.

#### Clear Knowledge Base
Deletes everything from ChromaDB. You'll need to run `python ingest.py` again to re-populate it.

#### Clear Chat History
Removes the session history shown at the bottom of the page. Does not affect the knowledge base.

---

### The main panel

#### Asking a question

1. Type your question in the text box
2. Click the **Ask** button (or press Enter)
3. Wait a few seconds — the system is:
   - Embedding your question
   - Searching ChromaDB
   - Sending the augmented prompt to Ollama
   - Streaming the answer back

#### Step 1 — Retrieved Chunks

After you ask, the first thing shown is the chunks that were retrieved from your documents. For each chunk you see:

- Which file it came from (e.g. `report.pdf`)
- Which page
- A progress bar showing the **similarity score** (e.g. `Similarity: 87.2%`)
  - Green = high similarity (very relevant)
  - Yellow = medium similarity
  - Red = low similarity (the system couldn't find a great match)
- The actual text of that chunk

This section lets you verify that the system found the right parts of your documents.

#### Step 2 — Augmented Prompt

This is the exact text that was sent to the AI. You can click to expand it and see:

```
Context:
[Source 1: report.pdf, page 3, similarity 87.2%]
...chunk text...

---

[Source 2: notes.txt, page 0, similarity 74.1%]
...chunk text...

Question: What was the Q3 revenue?
```

This is shown for full transparency — you can see exactly what the AI read before answering.

#### Step 3 — LLM Answer

The answer streams in word by word (like watching someone type). A blinking cursor `▌` shows it is still generating.

Once complete, the full answer remains on screen.

#### Session History

Every previous question from this browser session is saved below the current answer. Click any item to expand it and see:
- The answer
- The chunks that were retrieved
- The augmented prompt that was used

This history resets when you refresh the page or click "Clear Chat History".

---

## 10. What happens under the hood when you ask a question

Here is the complete technical journey from your question to the answer:

```
1. You type: "What were the key findings in the executive summary?"
   and click Ask.

2. app.py calls pipeline.rag_stream("What were the key findings...")

3. pipeline.py calls retriever.retrieve(query, top_k=4)

4. retriever.py sends the question to Ollama:
      ollama.embed(model="nomic-embed-text", input="What were the key...")
   Ollama returns a list of 768 numbers, e.g.:
      [0.023, -0.41, 0.87, 0.002, ...]   ← this is the "embedding"
   Note: must be the same model used during ingestion — both sides must match or search breaks.

5. retriever.py queries ChromaDB:
      "Find the 4 stored chunks whose embeddings are closest to this one"
   ChromaDB uses a mathematical distance called "cosine similarity" to compare
   768-dimensional vectors and returns the 4 closest matches.

6. retriever.py returns 4 chunks, each with:
      { text: "...", source: "report.pdf", page: 2, similarity: 87.2 }

7. pipeline.py calls generator.build_prompt(query, chunks)
   This creates the augmented prompt (shown in Step 2 of the UI).

8. pipeline.py calls generator.generate_stream(query, chunks)
   This sends the prompt to Ollama:
      ollama.chat(model="llama3.2:latest", messages=[...], stream=True)

9. Ollama runs llama3.2 locally on your machine.
   The model reads the context + question and generates an answer.
   It streams back one token (roughly one word) at a time.

10. app.py receives each token and immediately updates the UI.
    You see the answer appearing word by word.

11. The full answer, retrieved chunks, and prompt are saved in
    st.session_state.history so you can refer back to them.
```

---

## 11. Common errors and how to fix them

### "No module named 'ollama'" or similar import errors

**Cause:** The virtual environment is not active.

**Fix:**
```bash
cd "/Users/paritosh/development/RAG- POC"
source .venv/bin/activate
```

You should see `(.venv)` in your prompt before running any command.

---

### "Connection refused" or "Error communicating with Ollama"

**Cause:** Ollama is not running.

**Fix:** Open a new terminal and run:
```bash
ollama serve
```
Keep that terminal open while you use the app.

---

### "model 'llama3.2:latest' not found"

**Cause:** The LLM was not downloaded.

**Fix:**
```bash
ollama pull llama3.2
```

---

### "No documents in the knowledge base"

**Cause:** You haven't run `python ingest.py` yet, or the `data/` folder is empty.

**Fix:**
1. Copy PDF/TXT/MD files into the `data/` folder
2. Run:
```bash
python ingest.py
```

---

### The answer is wrong or irrelevant

**Possible causes and fixes:**

1. **Low similarity scores (below 50%)** — your documents may not contain information about what you asked. Check which chunks were retrieved.

2. **Chunks are too small or too large** — open `rag/ingestion.py` and try adjusting:
   ```python
   CHUNK_SIZE = 600    # try 400 for more precision, or 900 for more context
   CHUNK_OVERLAP = 100 # try 150 if answers feel cut off
   ```
   Then re-ingest: `python ingest.py --clear`

3. **Top-K is too low** — increase the slider in the UI to 6 or 8.

4. **Scanned PDF** — if your PDF is a scanned image (not text-based), the text extractor can't read it. You'd need an OCR tool first.

---

### The app is slow

**Cause:** The LLM (`llama3.2`) runs on your CPU if you don't have a supported GPU.

**Options:**
- Use a smaller model. In `rag/generator.py`, change:
  ```python
  LLM_MODEL = "llama3.2:latest"
  ```
  to:
  ```python
  LLM_MODEL = "gemma3:1b"   # much faster, less capable
  ```
- Reduce Top-K to 2 (fewer chunks = shorter prompt = faster generation)

---

## 12. Glossary of terms

| Term | Plain English explanation |
|---|---|
| **RAG** | Retrieval-Augmented Generation. A technique where an AI is given relevant document passages before answering a question, so it answers from your data instead of guessing. |
| **LLM** | Large Language Model. The AI that reads text and generates answers. In this project: `llama3.2`. |
| **Embedding** | A list of numbers that represents the "meaning" of a piece of text. Similar texts have similar embeddings. This is how the system finds relevant chunks without exact keyword matching. |
| **Chunk** | A small passage of text (about 600 characters) that a document is split into. The system works with chunks instead of whole documents because LLMs have a limit on how much text they can read at once. |
| **Vector** | Another name for an embedding — a list of numbers. |
| **Vector Database** | A database designed to store and search embeddings. In this project: ChromaDB. |
| **ChromaDB** | The local database that stores all your document chunks and their embeddings. It lives in the `chroma_db/` folder. |
| **Cosine Similarity** | A mathematical way to measure how similar two embeddings (lists of numbers) are. A score of 1.0 means identical meaning; 0 means completely unrelated. |
| **Similarity Score** | The percentage shown next to each chunk in the UI. Higher = more relevant to your question. |
| **Ollama** | A program that lets you run AI models locally on your laptop without needing the internet or paying for API access. |
| **nomic-embed-text** | The Ollama model used to convert text into embeddings. Purpose-built for similarity search. (~274 MB) |
| **llama3.2** | The Ollama model that reads the context + question and generates the answer. (~2 GB) |
| **Augmented Prompt** | The combined text of your question + the retrieved chunks. This is what gets sent to the LLM. |
| **Virtual Environment (.venv)** | An isolated Python installation for this project. Keeps this project's dependencies separate from your system Python. |
| **Ingestion** | The process of loading a document, splitting it into chunks, embedding each chunk, and storing everything in ChromaDB. Done once per file (or when a file changes). |
| **SHA-256 Hash** | A unique fingerprint calculated from a file's content. Used to detect if a file has changed since it was last ingested. |
| **Top-K** | The number of chunks retrieved per question. Default is 4. |
| **Streamlit** | A Python library that turns a Python script into a web app automatically. |
| **Token** | The smallest unit of text the LLM processes — roughly a word or part of a word. The answer streams one token at a time. |
| **Streaming** | Instead of waiting for the full answer to be generated before showing it, streaming shows each word as soon as it is generated — like watching someone type. |

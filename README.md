# ClearPath Support Chatbot

A RAG-powered customer support chatbot for ClearPath — a fictional project management SaaS — built with FastAPI, Groq LLMs, and a plain HTML/CSS/JS frontend.

---

## Features

| Layer | Description |
|-------|-------------|
| **RAG Pipeline** | TF-IDF retrieval over 30 PDF documents — no external RAG libraries |
| **Model Router** | 8-rule deterministic classifier → `llama-3.1-8b-instant` or `llama-3.3-70b-versatile` |
| **Output Evaluator** | Flags `no_context`, `refusal`, and `pricing_conflict` issues |
| **Chat UI** | Dark glassmorphism design with live debug sidebar |
| **Conversation Memory** | Server-side session store, last 6 turns injected as history |

---

## Project Structure

```
Lemnisca/
├── clearpath_docs/          # 30 ClearPath PDF documents
├── backend/
│   ├── main.py              # FastAPI app + /query endpoint
│   ├── rag_pipeline.py      # PDF ingestion, chunking, TF-IDF retrieval
│   ├── router.py            # Deterministic rule-based model router
│   ├── evaluator.py         # Post-generation output evaluator
│   ├── llm_client.py        # Groq API wrapper with prompt builder
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Environment variable template
├── frontend/
│   ├── index.html           # Chat UI
│   ├── style.css            # Design system styles
│   └── app.js               # Frontend application logic
├── written_answers.md       # Q1–Q4 answers + AI usage disclosure
└── README.md
```

---

## Setup & Running Locally

### Prerequisites

- Python 3.10–3.13 (3.14 is not yet supported by Pydantic/FastAPI)
- A free [Groq API key](https://console.groq.com)

### 1. Clone and enter the repo

```bash
git clone https://github.com/Json604/lemnisca_takeHomeAssignment.git
cd lemnisca_takeHomeAssignment
```

### 2. Set up the backend

Use Python 3.12 or 3.13 (required; Python 3.14 is not yet supported). If needed, install with Homebrew: `brew install python@3.12`.

```bash
cd backend

# Remove old venv if you used Python 3.14
rm -rf venv

# Create venv with Python 3.12 or 3.13 (e.g. python3.12 -m venv venv)
python3.12 -m venv venv   # or: python3.13 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and paste your Groq API key:
#   GROQ_API_KEY=gsk_...
```

### 3. Start the backend

```bash
# From the backend/ directory, with venv active:
python main.py
```

The server will:
1. Parse all 30 PDFs and build a TF-IDF index (takes ~10–20 seconds on first run)
2. Cache the index to `.rag_cache.pkl` for fast subsequent startups
3. Start listening on **http://localhost:8000**

> **Tip:** Visit `http://localhost:8000/docs` for the interactive Swagger UI.

### 4. Open the frontend

```bash
# From the repo root — open the frontend in your browser:
open frontend/index.html
# Or simply double-click frontend/index.html in Finder
```

No build step required — it's pure HTML/CSS/JS.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | **Yes** | Your Groq API key (get one free at console.groq.com) |
| `PORT` | No | Server port (defaults to 8000) |

---

## Models Used

| Purpose | Groq model string |
|---------|-------------------|
| Simple queries | `llama-3.1-8b-instant` |
| Complex queries | `llama-3.3-70b-versatile` |

---

## Routing Rules (Summary)

The router is a deterministic, rule-based classifier — no LLM call involved.

| Rule | Condition | → Model |
|------|-----------|---------|
| R1 Greeting | Social openers, ≤5 words | 8B |
| R2 Very short | ≤6 words, ≤1 question mark | 8B |
| R3 Single-fact | "what is / list / how many" + <15 words | 8B |
| R4 Long | ≥25 words | 70B |
| R5 Multi-question | ≥2 question marks | 70B |
| R6 Reasoning | explain / compare / troubleshoot / configure… | 70B |
| R7 Complaint | error / broken / not working / can't… | 70B |
| R8 Conditional | if/when + then/should/will | 70B |
| Default | None matched | 8B |

Every decision is logged to `backend/logs/routing.log` in JSON format.

---

## Evaluator Flags

| Flag | Condition |
|------|-----------|
| `no_context` | 0 chunks retrieved but model still answered |
| `refusal` | Answer contains refusal phrases ("I don't have", "not mentioned"…) |
| `pricing_conflict` | 3+ distinct dollar amounts in a pricing-related answer |

Flagged responses display a yellow warning in the chat UI.

---

## Bonus Challenges Attempted

| Challenge | Status | Notes |
|-----------|--------|-------|
| Conversation memory | ✅ Implemented | Server-side session store, last 6 turns, `conversation_id` in request/response |
| Streaming | ❌ Not attempted | — |
| Eval harness | ❌ Not attempted | — |
| Live deploy | ❌ Not attempted | Local only |

---

## Known Issues & Limitations

- **TF-IDF retrieval** misses semantically equivalent queries that don't share exact vocabulary with the docs. See Q4 in `written_answers.md` for full analysis and fix.
- **Conversation memory is in-memory only** — it resets when the server restarts.
- **No authentication** — the `/query` endpoint is open. In production, add API key / JWT auth.
- **PDF parsing quality** depends on `pypdf` — some complex multi-column PDFs may lose formatting.
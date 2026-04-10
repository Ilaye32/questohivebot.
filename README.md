# QuestoHive 🤖

> A production-grade, multimodal AI assistant built with LangGraph, Chainlit, and Google Gemini — featuring voice input, document understanding, real-time web search, and RAG-powered knowledge retrieval.

---

## Overview

QuestoHive is a full-stack conversational AI application designed for real-world deployment. It combines a **ReAct agent architecture** with a polished Chainlit UI to deliver a chatbot that can reason, search the web, scrape websites, process uploaded documents, and answer questions from a custom knowledge base — all while supporting both text and voice input.

Built as a core project within the [Questohive](https://github.com/Ilaye32/questohivebot) AI startup, this codebase demonstrates end-to-end LLM engineering from prompt design to async streaming to multi-modal input handling.

---

## Key Features

| Feature | Details |
|---|---|
| 🎙️ **Voice Input (STT)** | Records audio via Chainlit, detects format (WebM, WAV, PCM, OGG, MP3), converts raw PCM to WAV, and transcribes using **Groq Whisper Large v3** |
| 🧠 **ReAct Agent** | Powered by `langgraph.prebuilt.create_react_agent` with multi-tool reasoning loop |
| 🔍 **Web Search** | Integrated **Tavily Search** (advanced depth) for real-time information retrieval |
| 🕷️ **Web Scraping** | Dual scraper setup: **Firecrawl** for standard pages and **Crawl4AI** with headless browser + proxy for bot-protected sites |
| 📚 **RAG / Knowledge Base** | Gemini `file_search` tool backed by a **Google File Search Store** for domain-specific Q&A |
| 📄 **Document Processing** | Accepts PDF (PyMuPDF), DOCX (python-docx), TXT, and images; images are described via **Llama 4 Scout** vision model through Groq |
| 💬 **Streaming Responses** | Full async token streaming via `astream_events` with animated thinking indicator |
| 🗂️ **Conversation Memory** | Rolling message history with configurable trim window (default: 20 messages) |

---

## Architecture

```
User Input (Text / Voice / File)
        │
        ▼
  Chainlit UI Layer
        │
   ┌────┴─────────────────────────────┐
   │         on_message handler        │
   │   on_audio_end → Groq Whisper STT │
   └────┬─────────────────────────────┘
        │
        ▼
  read_documents()          ← PDF / DOCX / TXT / Image
        │
        ▼
  process_user_input()
        │
        ▼
  LangGraph ReAct Agent (Gemini 2.5 Flash Lite)
        │
   ┌────┴──────────────────────────────────┐
   │              Tool Router               │
   ├── TavilySearch       (web search)      │
   ├── scrape_with_firecrawl  (web scrape)  │
   ├── deep_scrape_tool   (headless scrape) │
   └── get_ai_response    (RAG / KB lookup) │
        └──────────────────────────────────┘
        │
        ▼
  Streaming Response → Chainlit UI
```

---

## Tech Stack

**LLM & Agent**
- `langchain-google-genai` — Gemini 2.5 Flash Lite as primary LLM
- `langgraph` — ReAct agent with `create_react_agent`
- `langchain-groq` — Groq API integration
- `google-genai` — Native Gemini client for RAG / File Search

**Voice**
- `groq` — Whisper Large v3 for speech-to-text
- Custom PCM → WAV converter with format auto-detection

**Web & Data**
- `langchain-tavily` — Advanced web search
- `firecrawl` — Markdown-first web scraping
- `crawl4ai` — Headless browser scraping with proxy support

**Document Parsing**
- `PyMuPDF (fitz)` — PDF extraction
- `python-docx` — DOCX parsing
- `Llama 4 Scout` via Groq — Image description (vision)

**UI & Infrastructure**
- `chainlit` — Chat UI with audio, file upload, and streaming support
- `python-dotenv` — Environment configuration
- `langchain-mcp-adapters` — MCP tool integration support

---

## Project Structure

```
questohivebot/
├── main.py              # Chainlit app, agent setup, all event handlers
├── read.py              # Document reader (PDF, DOCX, TXT, images)
├── audio.py             # Raw PCM → WAV converter + logging
├── detect_format.py     # Magic-byte audio format detection
├── requirements.txt     # Pinned dependencies
└── .env                 # API keys (not committed)
```

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- API keys for: Groq, Google AI, Tavily, Firecrawl

### Install

```bash
git clone https://github.com/Ilaye32/questohivebot.git
cd questohivebot
pip install -r requirements.txt
playwright install  # Required for Crawl4AI headless browser
```

### Configure

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_key
GOOGLE_API_KEY=your_google_key
TAVILY_API_KEY=your_tavily_key
FIRECRAWL_API_KEY=your_firecrawl_key
```

### Run

```bash
chainlit run main.py
```

Open `http://localhost:8000` in your browser.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ | Groq API — Whisper STT + Llama 4 vision |
| `GOOGLE_API_KEY` | ✅ | Gemini LLM + File Search RAG |
| `TAVILY_API_KEY` | ✅ | Real-time web search |
| `FIRECRAWL_API_KEY` | ✅ | Web scraping |

---

## Engineering Highlights

- **Format-agnostic audio pipeline**: Magic-byte detection across WebM, WAV, OGG, MP3, and raw PCM with automatic conversion before transcription.
- **Dual scraper fallback**: Firecrawl handles standard pages; Crawl4AI with headless Playwright and proxy handles bot-protected sites.
- **Async-first design**: All I/O-heavy operations (`process_audio`, `process_user_input`, agent streaming) are fully `async` with `asyncio.to_thread` for blocking SDK calls.
- **Graceful error handling**: User-friendly error messages for rate limits, timeouts, auth failures, and empty transcriptions — no raw stack traces exposed.
- **Streaming UX**: Animated thinking dots shown while the agent reasons; replaced token-by-token once the first chunk arrives.

---

## Author

**Ilaye Timibofa Clifford**  
AI Engineer · LLM QA Specialist · B.Eng Mechanical Engineering (Rivers State University)

- 🔗 [GitHub](https://github.com/Ilaye32)
- 💼 AI Engineer @ Questohive | AI Trainer @ Mindrift (Toloka)
- 🛠️ Skills: LangChain · LangGraph · RAG · Prompt Engineering · LLM Evaluation · Red-teaming

---

## License

MIT

# QuestoHive 🎓

An AI-powered academic tutoring chatbot that helps students master past exam questions through voice and text interaction. Built with Chainlit, LangGraph, and Groq.

---

## Features

- 🎙️ **Voice Input** — Record questions using the built-in microphone; audio is transcribed via Groq Whisper
- ⌨️ **Text Chat** — Type questions directly for instant structured explanations
- 📄 **Document Upload** — Upload PDF, DOCX, or TXT files for the bot to analyze and extract exam-relevant content
- 🔍 **Web Search** — Powered by Tavily, the agent searches the web when real-time or verified information is needed
- 🕸️ **Web Crawling** — Advanced page crawling and content analysis tools for deep research
- 🧠 **Agentic Reasoning** — LangGraph ReAct agent with tool-use for multi-step problem solving
- 🔄 **Streaming Responses** — Real-time token streaming for a smooth chat experience
- 📝 **Conversation History** — Maintains context across the session with automatic history trimming

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI / Chat Interface | [Chainlit](https://chainlit.io) |
| LLM | Groq (`llama-3.1-8b-instant`) |
| Speech-to-Text | Groq Whisper (`whisper-large-v3`) |
| Agent Framework | LangGraph (`create_react_agent`) |
| Web Search | Tavily |
| Web Crawling | Crawl4AI + Playwright |
| Document Parsing | PyMuPDF (PDF), python-docx (DOCX) |
| Audio Processing | Python `wave` module (PCM → WAV) |

---

## Project Structure

```
questohive/
├── main.py              # App entry point, Chainlit handlers, agent setup
├── prompt.py            # System prompt for the academic tutor persona
├── audio.py             # Raw PCM to WAV conversion and audio logging
├── detect_format.py     # Magic-byte audio format detection
├── read.py              # Document reading (PDF, DOCX, TXT)
├── seek.py              # Web crawling and page analysis tools
├── requirements.txt     # Python dependencies
├── LICENSE              # MIT License
└── .env                 # Environment variables (not committed)
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- A [Groq API key](https://console.groq.com)
- A [Tavily API key](https://tavily.com)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/questohive.git
   cd questohive
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate      # macOS/Linux
   venv\Scripts\activate         # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers** (required for web crawling)

   ```bash
   playwright install
   ```

5. **Set up environment variables**

   Create a `.env` file in the project root:

   ```env
   GROQ_API_KEY=your_groq_api_key_here
   TAVILY_API_KEY=your_tavily_api_key_here
   ```

### Running the App

```bash
chainlit run main.py
```

Then open your browser at `http://localhost:8000`.

---

## Usage

| Action | How |
|---|---|
| Ask a question | Type in the chat input and press Enter |
| Voice question | Click the microphone icon, speak, then stop recording |
| Upload a document | Attach a PDF, DOCX, or TXT file with your message |
| Web-verified answer | The agent automatically searches when needed |

---

## Configuration

Key settings are managed in the `Config` class inside `main.py`:

| Setting | Default | Description |
|---|---|---|
| `LLM_MODEL` | `llama-3.1-8b-instant` | Groq chat model |
| `WHISPER_MODEL` | `whisper-large-v3` | Groq transcription model |
| `LLM_TEMPERATURE` | `0.7` | Response creativity |
| `MAX_HISTORY_MESSAGES` | `20` | Rolling context window size |
| `MAX_AUDIO_SIZE_MB` | `25` | Maximum audio upload size |
| `MAX_INPUT_LENGTH` | `10000` | Maximum text input length |

---

## How It Works

1. **User sends a message** (text, voice, or file upload)
2. **Audio** is buffered in chunks, converted from raw PCM to WAV if needed, then transcribed with Groq Whisper
3. **Documents** are parsed by `read.py` and prepended as context to the user message
4. **The LangGraph agent** receives the full conversation history and decides whether to answer directly or invoke tools (Tavily search, web crawl, page analysis)
5. **Streamed response** is sent token-by-token back to the Chainlit UI
6. **Conversation history** is updated and trimmed to the configured window size

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Author

**Ilaye Clifford Timibofa**  
AI Engineer · LLM Evaluation Specialist  
[GitHub](https://github.com/your-username) · [LinkedIn](https://linkedin.com/in/your-profile)

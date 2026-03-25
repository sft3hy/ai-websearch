# AI Web Search

An agentic AI chat application powered by [Open WebUI](https://github.com/open-webui/open-webui), [Groq](https://groq.com), and [Tavily](https://tavily.com). The system intelligently decides when a user's question requires a live web search and seamlessly augments the LLM's response with real-time information and sources.

## How It Works

1. You ask a question in the Open WebUI chat interface.
2. A lightweight backend proxy classifies your query to determine if it needs fresh web data.
3. If yes — Tavily searches the web and the results are injected into the LLM's context.
4. The selected Groq model generates a response, citing sources when search was used.

> **No tool calling is used.** The system avoids Groq's native function-calling API entirely. Instead, it uses a fast classifier model (`llama-3.1-8b-instant`) and direct context injection — a much more reliable approach.

## Quick Start

```bash
# Set your API keys
export GROQ_API_KEY=your_groq_key
export TAVILY_API_KEY=your_tavily_key

# Run
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Available Models

| Model | Type | Best For |
|---|---|---|
| `meta-llama/llama-4-scout-17b-16e-instruct` | Production | General purpose, code, reasoning |
| `meta-llama/llama-4-maverick-17b-128e-instruct` | Production | Multilingual, creative |
| `llama-3.3-70b-versatile` | Production | Complex reasoning |
| `llama-3.1-8b-instant` | Production | Fast, cost-effective |
| `llama-3.2-90b-vision-preview` | Preview | Image understanding |
| `deepseek-r1-distill-llama-70b` | Preview | Deep reasoning |
| `qwen/qwen3-32b` | Production | General purpose |

## Project Structure

```
ai-websearch/
├── api/                        # Backend proxy
│   ├── agent.py                # Search classification + context injection logic
│   ├── main.py                 # FastAPI server (OpenAI-compatible API)
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile
├── charts/ai-websearch/        # Helm chart for Kubernetes
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── ingress.yaml
│       └── secrets.yaml
├── docker-compose.yaml
└── README.md
```

---

## Detailed Architecture

### Overview

The application consists of two containers orchestrated via Docker Compose:

1. **Backend Proxy** (`api/`) — A FastAPI application that intercepts all chat requests from Open WebUI. It classifies user queries, optionally performs web searches via Tavily, and forwards everything to Groq for final response generation.
2. **Open WebUI** — The frontend chat interface. It is configured to use the backend proxy as its OpenAI-compatible API provider (`OPENAI_API_BASE_URL=http://backend:8000/v1`).

### Request Flow

```
┌──────────────┐     ┌──────────────────────────────────────────────┐     ┌──────────┐
│              │     │              Backend Proxy                    │     │          │
│              │     │                                              │     │          │
│  Open WebUI  │────▶│  1. Receive /v1/chat/completions request     │     │   Groq   │
│  (Frontend)  │     │  2. Extract last user message                │     │   API    │
│              │     │  3. Classify with llama-3.1-8b-instant  ────▶│────▶│          │
│              │     │  4. If needs_search:                         │     │          │
│              │     │       └─ Call Tavily Search API ────────────▶│ T   │          │
│              │     │       └─ Inject results as system message    │ a   │          │
│              │     │  5. Call Groq with (possibly augmented)      │ v   │          │
│              │◀────│     messages for final response ────────────▶│ i   │          │
│              │     │  6. Return OpenAI-compatible response        │ l   │          │
│              │     │                                              │ y   │          │
└──────────────┘     └──────────────────────────────────────────────┘     └──────────┘
```

### Search Classification (`api/agent.py`)

The classifier uses `llama-3.1-8b-instant` (fast, ~100ms) with a carefully crafted prompt to decide if web search is needed. It returns a JSON object:

```json
{"needs_search": true, "search_query": "optimized search query"}
```
or
```json
{"needs_search": false}
```

**Triggers search:**
- Current events, news, recent happenings
- Weather forecasts or current conditions
- Stock prices, sports scores, live data
- Product/company questions with potential recent updates
- Factual questions where the answer may have changed

**Skips search:**
- General knowledge (math, science, history, definitions)
- Creative tasks (writing, brainstorming, coding)
- Conversational messages (greetings, opinions, advice)
- Well-established facts unlikely to change

### Context Injection

When search is triggered, Tavily results are formatted and injected as a system message just before the last user message in the conversation:

```
[1] Page Title
URL: https://example.com/article
Content snippet from the page...

[2] Another Page Title
URL: https://example.com/other
More content...
```

The system message also instructs the model to cite sources in a `## Sources` section at the end of its response.

### OpenAI-Compatible API (`api/main.py`)

The backend exposes two endpoints that Open WebUI consumes:

| Endpoint | Method | Description |
|---|---|---|
| `/v1/chat/completions` | POST | Chat completion with agentic search |
| `/v1/models` | GET | Lists all available Groq models |
| `/health` | GET | Health check |

The `/v1/chat/completions` endpoint accepts the standard OpenAI request format and returns a standard OpenAI response format, making it fully compatible with Open WebUI (or any OpenAI-compatible client).

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | API key from [console.groq.com](https://console.groq.com) |
| `TAVILY_API_KEY` | Yes | API key from [app.tavily.com](https://app.tavily.com) |
| `WEBUI_SECRET_KEY` | No | Secret key for Open WebUI sessions (defaults to `t0p-s3cr3t`) |

### Docker Compose Services

| Service | Image | Port | Description |
|---|---|---|---|
| `backend` | Built from `./api` | 8000 | FastAPI proxy with search agent |
| `open-webui` | `ghcr.io/open-webui/open-webui:main` | 3000→8080 | Chat frontend |

### Kubernetes Deployment (Helm)

A Helm chart is provided in `charts/ai-websearch/` for Kubernetes deployment. Both containers run as sidecars in the same pod, communicating over `localhost`.

```bash
# Install
helm install ai-websearch ./charts/ai-websearch \
  --set secrets.groqApiKey=YOUR_KEY \
  --set secrets.tavilyApiKey=YOUR_KEY

# Upgrade
helm upgrade ai-websearch ./charts/ai-websearch
```

Key Helm values:
- `image.repository` — Docker registry for the backend image
- `ingress.hosts[0].host` — Your domain
- `resources.webui` / `resources.backend` — CPU/memory limits
- `secrets.*` — API keys (stored as Kubernetes Secrets)

### Logging

The backend emits structured logs for every request:

```
💬 User: what's the weather in NYC?
Classification result: {"needs_search": true, "search_query": "current weather New York City"}
🔍 Searching web for: current weather New York City
📄 Found 5 results
✅ Search context injected into prompt
🤖 Generating response with model: meta-llama/llama-4-scout-17b-16e-instruct
✅ Response generated (847 chars)
```

View logs with:
```bash
docker compose logs -f backend
```

### Dependencies

**Backend (`api/requirements.txt`):**
- `groq` — Groq Python SDK (direct API calls, no LangChain)
- `fastapi` — Web framework
- `uvicorn` — ASGI server
- `tavily-python` — Tavily search client
# Financial Portfolio Analyzer

An AI-powered multi-agent system that analyzes your real stock portfolio, fetches live news, runs technical analysis with actual market indicators, and generates actionable risk mitigation recommendations — all streamed to a real-time web dashboard.

Built with **LangGraph** + **Gemini 2.5 Pro** + **MCP (Model Context Protocol)** for connecting to a live Indian stock broker (Groww).

https://github.com/user-attachments/assets/your-demo-video-id

> *Replace the link above with your 30-second demo video after uploading it to the GitHub repo.*

---

## Screenshots

<div align="center">

| Portfolio & News | Technical Analysis | Recommendations |
|:---:|:---:|:---:|
| ![Portfolio](assets/screenshot-portfolio.png) | ![Analysis](assets/screenshot-analysis.png) | ![Recommendations](assets/screenshot-recommendations.png) |

</div>

> *Add your screenshots to the `assets/` folder. Name them `screenshot-portfolio.png`, `screenshot-analysis.png`, `screenshot-recommendations.png`.*

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Server (SSE Streaming)                      │
│                                                                             │
│  GET /analyze ──────────────────────┐    POST /continue ──────────────────┐ │
│  (Phase 1: EventSource)            │    (Phase 2: fetch + ReadableStream) │ │
│                                     │                                      │ │
│  ┌──────────┐    ┌──────────┐      │    ┌──────────────┐   ┌───────────┐ │ │
│  │ Portfolio │───▶│   News   │──────┼───▶│   Analysis   │──▶│ Mitigation│ │ │
│  │  Agent    │    │  Agent   │      │    │    Agent     │   │   Agent   │ │ │
│  └────┬─────┘    └────┬─────┘      │    └──────┬───────┘   └─────┬─────┘ │ │
│       │               │      ┌─────┘           │                 │       │ │
│       │               │      │ INTERRUPT        │                 │       │ │
│       │               │      │ (Human Review)   │                 │       │ │
│       │               │      └─────────────────▶│                 │       │ │
│       ▼               ▼                         ▼                 ▼       │ │
│  ┌─────────────────────────────────────────────────────────────────────┐  │ │
│  │                     LangGraph StateGraph                           │  │ │
│  │                                                                     │  │ │
│  │  AgentState: { portfolio, news, analysis, recommendations,         │  │ │
│  │               messages, is_relevant }                               │  │ │
│  │                                                                     │  │ │
│  │  Checkpointer: MemorySaver (persists state across SSE phases)      │  │ │
│  └─────────────────────────────────────────────────────────────────────┘  │ │
└──────────┬──────────────┬─────────────────────────┬──────────────────────┘ │
           │              │                         │                        │
     ┌─────▼─────┐  ┌────▼─────┐          ┌───────▼────────┐               │
     │ Groww MCP  │  │ News API │          │  Groww MCP     │               │
     │ Server     │  │          │          │  Server        │               │
     │            │  │ search   │          │                │               │
     │ • holdings │  │ articles │          │ • RSI          │               │
     │ • LTP      │  │ • query  │          │ • MACD         │               │
     │ • search   │  │ • filter │          │ • Bollinger    │               │
     └────────────┘  └──────────┘          │ • Candlestick  │               │
                                           │ • Historical   │               │
                                           └────────────────┘               │
                                                                            │
┌───────────────────────────────────────────────────────────────────────────┘
│                     Frontend (HTML/CSS/JS)
│
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐
│  │Portfolio │─▶│  News &  │─▶│  Human   │─▶│Technical │─▶│   Recom-    │
│  │ Table    │  │Sentiment │  │  Review  │  │ Analysis │  │  mendations │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └─────────────┘
│       ●──────────────●──────────────●──────────────●──────────────●
│              Progress Bar (real-time step tracking)
└──────────────────────────────────────────────────────────────────────────
```

### Agent Details

| Agent | Type | LLM | Tools | Output |
|-------|------|-----|-------|--------|
| **Portfolio Agent** | ReAct | Gemini 2.5 Pro | `get_holdings`, `get_ltp` (MCP) | `PortfolioData` — holdings with live prices |
| **News Agent** | ReAct | Gemini 2.5 Pro | `search_financial_news` (NewsAPI) | `NewsData` — articles + sentiment per stock |
| **Analysis Agent** | ReAct | Gemini 2.5 Pro | `calculate_rsi`, `calculate_macd`, `calculate_bollinger_bands`, `analyze_candlestick_patterns` (MCP) | `AnalysisData` — technical indicators + risk scores |
| **Mitigation Agent** | Direct LLM | Gemini 2.5 Pro | None (structured output) | `RecommendationsData` — rebalancing, hedging, exits |

### Data Flow

```
START ──▶ Portfolio Agent ──▶ News Agent ──▶ [INTERRUPT: Human Review] ──▶ Analysis Agent ──▶ Mitigation Agent ──▶ END
              │                    │                    │                        │                    │
              ▼                    ▼                    ▼                        ▼                    ▼
         SSE: portfolio       SSE: news         User clicks             SSE: analysis        SSE: recommendations
         (Phase 1)           (Phase 1)        Yes/No button             (Phase 2)             (Phase 2)
```

---

## Key Concepts

### LangGraph StateGraph
The entire pipeline is a **LangGraph StateGraph** — a directed graph where each node is an agent function that reads/writes to shared state (`AgentState`). The graph is compiled once at server startup and reused per request with different `thread_id`s.

### ReAct Pattern (Reasoning + Acting)
Three of the four agents use the **ReAct pattern** — an LLM loop that reasons about what tool to call, executes it, observes the result, and repeats until done. This is implemented via a custom `build_react_agent()` using LangGraph's `MessagesState`, `tools_condition`, and `ToolNode`.

### Human-in-the-Loop
The graph uses `interrupt_before=["analysis"]` to pause execution after the news agent. The frontend shows portfolio + news data, then waits for the user to decide if news is relevant. The backend resumes via `aupdate_state()` + `astream(None)`.

### MCP (Model Context Protocol)
Instead of REST APIs, the broker data comes via **MCP** — a protocol that exposes tools (functions) from external servers. The Groww MCP server provides portfolio holdings, live prices, and technical analysis indicators as callable tools that LangGraph agents can use directly.

### SSE Streaming (Two-Phase)
- **Phase 1** (`GET /analyze`): Uses browser-native `EventSource` to stream portfolio and news events
- **Phase 2** (`POST /continue`): Uses `fetch()` + `ReadableStream` to parse SSE manually (EventSource doesn't support POST)

### Structured Outputs
Every agent parses its raw LLM response into **Pydantic models** using `with_structured_output()`. This guarantees consistent JSON for the frontend, regardless of how the LLM phrases its response.

### Anti-Hallucination Pattern
The portfolio and analysis agents extract **raw tool outputs** from the ReAct message history (`msg.type == "tool"`) instead of trusting the LLM's final summary. This prevents Gemini from hallucinating portfolio data or indicator values.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Google Gemini 2.5 Pro (via `langchain-google-genai`) |
| **Agent Framework** | LangGraph + LangChain |
| **Broker Data** | [Groww MCP Server](https://github.com/anurag-groww/groww-mcp-server) (Model Context Protocol) |
| **News Data** | [NewsAPI](https://newsapi.org/) |
| **Backend** | FastAPI with SSE streaming |
| **Frontend** | Vanilla HTML/CSS/JS (dark theme) |
| **State Management** | LangGraph MemorySaver checkpointer |

---

## Prerequisites

- **Python 3.11+**
- **Google Cloud account** with Gemini API access and a service account JSON key
- **Groww account** with an active session JWT token
- **NewsAPI key** (free tier at [newsapi.org](https://newsapi.org/register))
- **Groww MCP Server** running locally on port 8181

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/financial-agent.git
cd financial-agent
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.sample .env
```

Edit `.env` and fill in your keys:

| Variable | How to get it |
|----------|---------------|
| `GROWW_API_KEY` | Log into Groww web app, open DevTools → Network tab → copy the `authorization` header value from any API request |
| `NEWS_API_KEY` | Register at [newsapi.org](https://newsapi.org/register) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Create a service account in GCP Console → download JSON key file → place in project root |
| `GOOGLE_CLOUD_PROJECT` | Your GCP project ID (e.g. `my-project-123`) |

### 5. Start the Groww MCP Server

Follow the setup instructions at [groww-mcp-server](https://github.com/anurag-groww/groww-mcp-server):

```bash
# In a separate terminal
cd groww-mcp-server
npm start
# Server runs on http://localhost:8181
```

### 6. Run the application

```bash
python server.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Project Structure

```
financial-agent/
├── server.py                  # FastAPI server — SSE endpoints, graph compilation
├── app.py                     # CLI version (standalone, for testing)
│
├── agents/
│   ├── portfolio_agent.py     # ReAct agent — fetches holdings via MCP
│   ├── news_agent.py          # ReAct agent — searches news via NewsAPI
│   ├── portfolio_analysis_agent.py  # ReAct agent — technical indicators via MCP
│   └── mitigation_agent.py    # Direct LLM — generates recommendations
│
├── utils/
│   ├── models.py              # Pydantic models for all agent outputs
│   ├── llm.py                 # Centralized LLM config (Gemini 2.5 Pro)
│   └── create_react_agent.py  # ReAct agent builder (LangGraph)
│
├── frontend/
│   ├── index.html             # Dashboard UI
│   ├── style.css              # Dark theme styles
│   └── app.js                 # SSE client — Phase 1 (EventSource) + Phase 2 (fetch)
│
├── assets/                    # Screenshots and demo media
├── requirements.txt
├── .env.sample                # Template for environment variables
└── .gitignore
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/analyze` | Starts Phase 1 — streams `portfolio` → `news` → `human_review_needed` events via SSE |
| `POST` | `/continue` | Starts Phase 2 — sends `{ thread_id, is_relevant }`, streams `analysis` → `recommendations` → `done` |
| `GET` | `/state/{thread_id}` | Debug endpoint — returns current graph state for a thread |

### SSE Event Types

**Phase 1** (`GET /analyze`):
```
event: thread_id
data: {"thread_id": "uuid-here"}

event: portfolio
data: {"holdings": [...], "total_portfolio_value": 12345.67}

event: news
data: {"stock_news": [...], "overall_market_sentiment": "neutral"}

event: human_review_needed
data: {"message": "Review portfolio and news above", "thread_id": "..."}
```

**Phase 2** (`POST /continue`):
```
event: analysis
data: {"stock_analyses": [...], "portfolio_risk_score": 5, ...}

event: recommendations
data: {"rebalancing": [...], "hedging": [...], "exits": [...], "summary": "..."}

event: done
data: {"message": "Analysis complete"}
```

---

## How It Works (Step by Step)

1. **User clicks "Analyze My Portfolio"** — browser opens SSE connection to `GET /analyze`

2. **Portfolio Agent** calls `get_holdings` and `get_ltp` via MCP to fetch real holdings with live prices. Raw tool outputs are extracted from the ReAct message history to prevent hallucination. Parsed into `PortfolioData`.

3. **News Agent** translates ticker symbols into meaningful search queries (e.g. `GOLDBETA` → `"Gold ETF India"`), searches NewsAPI, and rates sentiment per stock. Parsed into `NewsData`.

4. **Graph pauses** (`interrupt_before=["analysis"]`) — SSE sends `human_review_needed`. Frontend shows portfolio + news with a review prompt.

5. **User reviews news** and clicks "Yes" (include in analysis) or "No" (technical only). Frontend POSTs to `/continue`.

6. **Analysis Agent** calls MCP tools for each stock: `calculate_rsi`, `calculate_macd`, `calculate_bollinger_bands`, `analyze_candlestick_patterns`. Uses real indicator values (extracted from tool outputs, not LLM summary). Parsed into `AnalysisData`.

7. **Mitigation Agent** takes portfolio + analysis data and generates rebalancing actions, hedging strategies, and exit recommendations. Direct structured output (no ReAct loop needed). Parsed into `RecommendationsData`.

8. **Frontend renders** each section progressively as SSE events arrive, with a step-by-step progress bar.

---

## Switching the LLM

All agents use `get_llm()` from `utils/llm.py`. To switch models, edit that one file:

```python
# For OpenAI GPT-4o
from langchain_openai import ChatOpenAI
def get_llm(temperature=0):
    return ChatOpenAI(model="gpt-4o", temperature=temperature)

# For Anthropic Claude
from langchain_anthropic import ChatAnthropic
def get_llm(temperature=0):
    return ChatAnthropic(model="claude-sonnet-4-20250514", temperature=temperature)
```

---

## Known Limitations

- **NewsAPI free tier** returns articles up to 1 month old, and `get_top_headlines` often returns empty for financial queries. Currently using `get_everything` sorted by date.
- **Groww JWT tokens expire** — you'll need to re-extract the token periodically from the Groww web app.
- **Gemini occasional hallucination** — despite the anti-hallucination pattern, Gemini 2.5 Pro may rarely fabricate data. The tool-output extraction pattern mitigates but doesn't fully eliminate this.
- **In-memory checkpointer** — `MemorySaver` loses state on server restart. For production, use a persistent checkpointer (Redis, PostgreSQL).

---

## License

MIT

---

<div align="center">

Built while learning LangGraph and multi-agent architecture.

</div>

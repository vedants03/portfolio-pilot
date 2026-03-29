import warnings
import logging

# Suppress Gemini schema warnings (MCP tool schemas have keys Gemini doesn't support)
logging.getLogger("langchain_google_genai").setLevel(logging.ERROR)
logging.getLogger("langchain_google_vertexai").setLevel(logging.ERROR)
# Suppress checkpoint deserialization warnings
warnings.filterwarnings("ignore", message=".*Deserializing unregistered type.*")

"""
FastAPI server for the financial agent pipeline with SSE streaming.

Uses StreamingResponse to send SSE events. Each event is formatted as:
    event: <type>\ndata: <json>\n\n

Phase 1: GET /analyze  → streams portfolio, news, then pauses for human review
Phase 2: POST /continue → streams analysis, recommendations
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import base64
import os
import uuid
from dotenv import load_dotenv
from utils.models import AgentState
from agents.portfolio_agent import make_portfolio_node
from agents.news_agent import make_news_node
from agents.portfolio_analysis_agent import make_analysis_node
from agents.mitigation_agent import make_mitigation_node

load_dotenv()


# ── FastAPI app setup ──

app = FastAPI(title="Financial Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

checkpointer = MemorySaver()
compiled_graph = None
mcp_client = None


def get_mcp_config():
    config = {"apiKey": os.environ["GROWW_API_KEY"], "debug": True}
    encoded = base64.urlsafe_b64encode(json.dumps(config).encode()).decode()
    SERVER_URL = f"http://localhost:8181/mcp?config={encoded}"
    return {"groww": {"url": SERVER_URL, "transport": "streamable_http"}}


@app.on_event("startup")
async def startup():
    global compiled_graph, mcp_client

    mcp_client = MultiServerMCPClient(get_mcp_config())
    mcp_tools = await mcp_client.get_tools()

    portfolio_node = make_portfolio_node(mcp_tools)
    news_node = make_news_node()
    analysis_node = make_analysis_node(mcp_tools)
    mitigation_node = make_mitigation_node()

    graph = StateGraph(AgentState)
    graph.add_node("portfolio", portfolio_node)
    graph.add_node("news", news_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("mitigation", mitigation_node)

    graph.add_edge(START, "portfolio")
    graph.add_edge("portfolio", "news")
    graph.add_edge("news", "analysis")
    graph.add_edge("analysis", "mitigation")
    graph.add_edge("mitigation", END)

    compiled_graph = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["analysis"],
    )

    print("Graph compiled and ready.")


# ── Request/Response models ──

class ContinueRequest(BaseModel):
    thread_id: str
    is_relevant: bool


# ── Helpers ──

def serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj


def sse_event(event: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── Phase 1: Start analysis ──

@app.get("/analyze")
async def analyze():
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    async def event_generator():
        yield sse_event("thread_id", {"thread_id": thread_id})

        async for event in compiled_graph.astream(
            {"portfolio": {}, "news": {}, "messages": []},
            config=config,
        ):
            for node_name, state_update in event.items():
                if node_name == "__interrupt__":
                    continue
                if node_name == "portfolio":
                    yield sse_event("portfolio", serialize(state_update["portfolio"]))
                elif node_name == "news":
                    yield sse_event("news", serialize(state_update["news"]))

        yield sse_event("human_review_needed", {
            "message": "Review portfolio and news above, then POST to /continue",
            "thread_id": thread_id,
        })

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Phase 2: Continue after human review ──

@app.post("/continue")
async def continue_analysis(req: ContinueRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    async def event_generator():
        await compiled_graph.aupdate_state(config, {"is_relevant": req.is_relevant})

        async for event in compiled_graph.astream(None, config=config):
            for node_name, state_update in event.items():
                if node_name == "analysis":
                    yield sse_event("analysis", serialize(state_update["analysis"]))
                elif node_name == "mitigation":
                    yield sse_event("recommendations", serialize(state_update["recommendations"]))

        yield sse_event("done", {"message": "Analysis complete"})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Utility: check thread state ──

@app.get("/state/{thread_id}")
async def get_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = compiled_graph.get_state(config)
    return {
        "next_nodes": list(state.next) if state.next else [],
        "values": {k: serialize(v) for k, v in state.values.items()},
    }


# ── Serve frontend static files ──
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


# ── Run with: python server.py ──

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

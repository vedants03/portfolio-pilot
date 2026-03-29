import asyncio
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import base64
import os
from dotenv import load_dotenv
from utils.models import AgentState, PortfolioData, NewsData, AnalysisData, RecommendationsData
from agents.portfolio_agent import make_portfolio_node
from agents.news_agent import make_news_node
from agents.portfolio_analysis_agent import make_analysis_node
from agents.mitigation_agent import make_mitigation_node


load_dotenv()

checkpointer = MemorySaver()


def get_mcp_config():
    config = {"apiKey": os.environ["GROWW_API_KEY"], "debug": True}
    encoded = base64.urlsafe_b64encode(json.dumps(config).encode()).decode()
    SERVER_URL = f"http://localhost:8181/mcp?config={encoded}"
    return {"groww": {"url": SERVER_URL, "transport": "streamable_http"}}


def print_portfolio(portfolio: PortfolioData):
    print("\n=== PORTFOLIO ===")
    for h in portfolio.holdings:
        print(f"  {h.symbol} ({h.name}): {h.quantity} units @ ₹{h.current_price:.2f} = ₹{h.total_value:.2f}")
    print(f"  Total: ₹{portfolio.total_portfolio_value:.2f}")


def print_news(news: NewsData):
    print("\n=== NEWS & SENTIMENT ===")
    for sn in news.stock_news:
        print(f"\n  {sn.symbol} — {sn.sentiment.upper()}")
        print(f"    Reason: {sn.sentiment_reasoning}")
        for a in sn.articles:
            print(f"    • [{a.date}] {a.title} ({a.source})")
    print(f"\n  Overall market: {news.overall_market_sentiment}")


def print_analysis(analysis: AnalysisData):
    print("\n=== TECHNICAL ANALYSIS ===")
    for sa in analysis.stock_analyses:
        ind = sa.indicators
        print(f"\n  {sa.symbol} — Risk: {sa.risk_score}/10 — Signal: {sa.signal.upper()}")
        print(f"    RSI: {ind.rsi} ({ind.rsi_signal})")
        print(f"    MACD: line={ind.macd_line}, signal={ind.macd_signal_line}, histogram={ind.macd_histogram} ({ind.macd_signal})")
        print(f"    Bollinger: upper={ind.bollinger_upper}, mid={ind.bollinger_middle}, lower={ind.bollinger_lower} ({ind.bollinger_position})")
        if ind.candlestick_patterns:
            print(f"    Patterns: {', '.join(ind.candlestick_patterns)}")
        print(f"    {sa.reasoning}")
    print(f"\n  Portfolio Risk: {analysis.portfolio_risk_score}/10")
    print(f"  Sector Risk: {analysis.sector_concentration_risk}")
    print(f"  Summary: {analysis.summary}")


def print_recommendations(rec: RecommendationsData):
    print("\n=== RECOMMENDATIONS ===")
    print("\n  Rebalancing:")
    for r in rec.rebalancing:
        print(f"    {r.symbol}: {r.action.upper()} {r.quantity} shares — {r.reasoning}")
    print("\n  Hedging:")
    for h in rec.hedging:
        print(f"    Strategy: {h.strategy}")
        print(f"    Instruments: {', '.join(h.instruments)}")
        print(f"    Reason: {h.reasoning}")
    print("\n  Exit Recommendations:")
    for e in rec.exits:
        status = "EXIT" if e.should_exit else "HOLD"
        print(f"    {e.symbol}: {status} — {e.reasoning}")
    print(f"\n  Summary: {rec.summary}")


async def main():
    mcp_client = MultiServerMCPClient(get_mcp_config())
    mcp_tools = await mcp_client.get_tools()

    portfolio_node = make_portfolio_node(mcp_tools)
    news_node = make_news_node()
    analysis_node = make_analysis_node(mcp_tools)
    mitigation_node = make_mitigation_node()

    # Build the graph
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

    app = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["analysis"],
    )

    config = {"configurable": {"thread_id": "1"}}

    # Phase 1: Run portfolio + news, then pause for human review
    result = await app.ainvoke({"portfolio": {}, "news": {}, "messages": []}, config=config)

    state = app.get_state(config)
    if state.next:
        portfolio = state.values.get("portfolio")
        news = state.values.get("news")

        print_portfolio(portfolio)
        print_news(news)

        user_input = input("\nContinue with analysis? (y/n): ")

        # Update state with human decision, then resume the graph
        await app.aupdate_state(config, {"is_relevant": user_input == "y"})
        result = await app.ainvoke(None, config=config)

        print_analysis(result["analysis"])
        print_recommendations(result["recommendations"])

asyncio.run(main())

from utils.create_react_agent import build_react_agent
from utils.llm import get_llm
from utils.models import AgentState, AnalysisData, PortfolioData, NewsData

ANALYSIS_PROMPT = """You are a senior financial risk analyst with technical analysis expertise.
You have access to technical analysis tools. You MUST call them to get real data — never produce analysis without actual indicator values.

CRITICAL — Tool parameter format:
- trading_symbol: The stock name from the portfolio (e.g. "GOLDBETA", "SILVERBETA", "RELIANCE") — use it exactly as given
- exchange: "NSE"
- segment: "CASH"
- start_time / end_time: "YYYY-MM-DD HH:mm:ss" format
- interval_in_minutes: 1440 for daily candles

Step-by-step workflow:
1. Call get_current_date to know today's date
2. For EACH stock in the portfolio, call these tools IN PARALLEL where possible:
   - calculate_rsi with trading_symbol=<stock>, exchange="NSE", segment="CASH", start_time=<90 days ago>, end_time=<today>, interval_in_minutes=1440, period=14
   - calculate_macd with same params
   - calculate_bollinger_bands with same params
   - analyze_candlestick_patterns with same params
3. After getting ALL indicator results, produce your analysis

Output format:
For each stock:
- RSI value and interpretation (overbought >70 / oversold <30 / neutral)
- MACD signal (bullish/bearish crossover, histogram direction)
- Bollinger Band position (near upper/lower/middle band)
- Candlestick patterns detected
- Risk score (1-10) with justification from the above data

Overall:
- Portfolio risk score (1-10)
- Sector concentration risk (both are precious metals ETFs)

NEVER skip the tool calls. NEVER say "I couldn't retrieve data". If a tool fails, retry with slightly different date ranges."""


def make_analysis_node(all_tools):
    analysis_tools = [t for t in all_tools if t.name in [
        "get_current_date",
        "search_instruments",
        "calculate_rsi",
        "calculate_macd",
        "calculate_bollinger_bands",
        "calculate_moving_averages",
        "calculate_support_resistance",
        "calculate_volatility_metrics",
        "analyze_candlestick_patterns",
        "get_historical_data",
    ]]

    llm = get_llm()
    analysis_agent = build_react_agent(llm, analysis_tools, ANALYSIS_PROMPT)

    parser_llm = get_llm().with_structured_output(AnalysisData)

    async def analysis_node(state: AgentState):
        portfolio: PortfolioData = state.get("portfolio")
        news: NewsData = state.get("news")
        is_relevant = state.get("is_relevant", False)

        # Build portfolio summary from structured data
        portfolio_summary = "\n".join(
            f"- {h.symbol} ({h.name}): {h.quantity} units @ ₹{h.current_price}, total ₹{h.total_value}"
            for h in portfolio.holdings
        )

        news_section = ""
        if is_relevant and news:
            news_lines = []
            for sn in news.stock_news:
                news_lines.append(f"- {sn.symbol}: Sentiment={sn.sentiment} — {sn.sentiment_reasoning}")
            news_section = (
                "Recent news and sentiment (human-approved as relevant):\n"
                + "\n".join(news_lines)
                + "\n\nCombine technical analysis with the news sentiment."
            )
        else:
            news_section = "The human reviewer marked the news as not relevant. Focus only on technical indicators."

        result = await analysis_agent.ainvoke(
            {"messages": [("user",
                f"Analyze the risk for this portfolio using technical indicators.\n\n"
                f"Portfolio:\n{portfolio_summary}\n\n"
                f"{news_section}"
            )]}
        )

        # Extract actual tool responses — these contain real indicator values
        tool_outputs = []
        for msg in result["messages"]:
            if msg.type == "tool":
                content = msg.content
                if isinstance(content, list):
                    content = "\n".join(str(c) for c in content)
                tool_outputs.append(f"[{msg.name}]: {content}")

        # Combine tool outputs + LLM's final interpretation
        raw_data = "\n\n".join(tool_outputs)
        llm_summary = result["messages"][-1].content
        print("  [Analysis] ReAct done. Parsing into structured data...")

        symbols = [h.symbol for h in portfolio.holdings]
        structured = await parser_llm.ainvoke(
            f"Extract the technical analysis into structured data. "
            f"Stock symbols: {', '.join(symbols)}.\n\n"
            f"Raw tool outputs (source of truth for indicator values):\n{raw_data}\n\n"
            f"LLM interpretation:\n{llm_summary}"
        )
        print("  [Analysis] Structured parsing complete.")

        return {"analysis": structured}

    return analysis_node

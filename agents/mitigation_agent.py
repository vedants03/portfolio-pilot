from utils.llm import get_llm
from utils.models import AgentState, RecommendationsData, PortfolioData, AnalysisData


MITIGATION_PROMPT = """You are a financial advisor. Based on the risk analysis provided,
suggest specific mitigations:

1. Rebalancing - which stocks to reduce/increase and by how much (specific share quantities)
2. Hedging - any options or ETF strategies to reduce exposure
3. Exit recommendations - should any position be closed entirely?

Be actionable and specific. Reference actual holdings, quantities, and indicator values."""


def make_mitigation_node():
    llm = get_llm().with_structured_output(RecommendationsData)

    async def mitigation_node(state: AgentState):
        portfolio: PortfolioData = state.get("portfolio")
        analysis: AnalysisData = state.get("analysis")

        # Build structured context for the LLM
        portfolio_summary = "\n".join(
            f"- {h.symbol} ({h.name}): {h.quantity} units @ ₹{h.current_price}, total ₹{h.total_value}"
            for h in portfolio.holdings
        )
        portfolio_summary += f"\nTotal portfolio value: ₹{portfolio.total_portfolio_value}"

        analysis_summary = f"Portfolio risk score: {analysis.portfolio_risk_score}/10\n"
        analysis_summary += f"Sector concentration: {analysis.sector_concentration_risk}\n\n"
        for sa in analysis.stock_analyses:
            ind = sa.indicators
            analysis_summary += (
                f"{sa.symbol}: Risk {sa.risk_score}/10, Signal={sa.signal}\n"
                f"  RSI={ind.rsi} ({ind.rsi_signal}), "
                f"MACD histogram={ind.macd_histogram} ({ind.macd_signal}), "
                f"Bollinger={ind.bollinger_position}\n"
                f"  Patterns: {', '.join(ind.candlestick_patterns) or 'none'}\n"
                f"  {sa.reasoning}\n\n"
            )

        print("  [Mitigation] Generating recommendations...")
        structured = await llm.ainvoke(
            f"{MITIGATION_PROMPT}\n\n"
            f"Portfolio:\n{portfolio_summary}\n\n"
            f"Risk Analysis:\n{analysis_summary}"
        )
        print("  [Mitigation] Complete.")

        return {"recommendations": structured}

    return mitigation_node

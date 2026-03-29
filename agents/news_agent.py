from dotenv import load_dotenv
from utils.llm import get_llm
from utils.models import AgentState, NewsData, PortfolioData
from langchain_core.tools import tool
from newsapi import NewsApiClient
from utils.create_react_agent import build_react_agent
import os

load_dotenv()

prompt = """You are a financial news research agent. Your job is to find relevant news for stocks in a portfolio.

IMPORTANT: Portfolio holdings often use ticker symbols or short codes (e.g. GOLDBETA, SILVERBETA, NIFTYBEES).
These are NOT searchable as-is. You MUST translate them into meaningful search queries:
- GOLDBETA, GOLDBEES → search "Gold ETF India" or "gold prices"
- SILVERBETA, SILVERBEES → search "Silver ETF India" or "silver prices"
- NIFTYBEES → search "Nifty 50 index India"
- For individual stocks like RELIANCE, TCS, INFY → search their full company names

Always search using the underlying asset or company name, not the ticker symbol.
After finding news, provide a brief sentiment summary (bullish/bearish/neutral) for each holding."""


@tool
def search_financial_news(query: str) -> str:
    """Search for recent financial news articles about a stock or company.
    Args:
        query: Stock name or company name to search news for (e.g. 'Reliance Industries' or 'Gold ETF')
    """
    newsapi = NewsApiClient(api_key=os.environ["NEWS_API_KEY"])

    results = newsapi.get_everything(
        q=query,
        language="en",
        sort_by="publishedAt",
        page_size=5,
    )

    if results["totalResults"] == 0:
        return f"No recent news found for {query}"

    articles = []
    for article in results["articles"]:
        articles.append(
            f"Title: {article['title']}\n"
            f"Source: {article['source']['name']}\n"
            f"Date: {article['publishedAt'][:10]}\n"
            f"Summary: {article.get('description', 'No summary')}\n"
            f"URL: {article.get('url', '')}\n"
        )

    return f"Found {results['totalResults']} articles for '{query}'. Top results:\n\n" + "\n---\n".join(articles)


def make_news_node():
    llm = get_llm()
    financial_news_tools = [search_financial_news]
    news_agent = build_react_agent(llm, financial_news_tools, prompt)

    parser_llm = get_llm().with_structured_output(NewsData)

    async def news_node(state: AgentState):
        portfolio: PortfolioData = state.get("portfolio")

        # Build a summary of holdings for the news agent
        holdings_summary = ", ".join(
            f"{h.symbol} ({h.name})" for h in portfolio.holdings
        )

        result = await news_agent.ainvoke(
            {"messages": [("user",
                f"Find recent news for these stocks and analyze sentiment: {holdings_summary}"
            )]}
        )
        raw_response = result["messages"][-1].content

        # Parse into structured NewsData
        structured = await parser_llm.ainvoke(
            f"Extract news articles and sentiment from this text. "
            f"The stock symbols are: {', '.join(h.symbol for h in portfolio.holdings)}.\n\n{raw_response}"
        )

        return {"news": structured}

    return news_node

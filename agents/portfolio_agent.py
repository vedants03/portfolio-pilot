from utils.create_react_agent import build_react_agent
from utils.llm import get_llm
from utils.models import AgentState, PortfolioData

prompt = """You are a portfolio data retrieval agent.

RULES:
1. Call get_holdings to fetch the user's actual holdings. Do NOT make up or guess any data.
2. If holdings don't include current prices, call get_ltp to get live prices.
3. Your response must contain ONLY the data returned by the tools — no invented stocks, no made-up prices.
4. For each holding, report: trading symbol, name, quantity, and current price.
5. If a tool returns an error, report the error — do NOT fabricate data."""


def make_portfolio_node(tools):
    llm = get_llm()
    portfolio_agent = build_react_agent(llm, tools, prompt)

    parser_llm = get_llm().with_structured_output(PortfolioData)

    async def portfolio_node(state: AgentState):
        result = await portfolio_agent.ainvoke(
            {"messages": [("user",
                "Get my holdings with current prices. "
                "Return a structured summary: stock symbol, full name, quantity, current price for each."
            )]}
        )

        # Extract actual tool responses from message history instead of
        # trusting the LLM's final summary (Gemini tends to hallucinate)
        tool_outputs = []
        for msg in result["messages"]:
            if msg.type == "tool":
                content = msg.content
                # content can be str or list of dicts in newer LangChain
                if isinstance(content, list):
                    content = "\n".join(str(c) for c in content)
                tool_outputs.append(content)

        # Use tool outputs as the source of truth for parsing
        raw_data = "\n\n".join(tool_outputs) if tool_outputs else result["messages"][-1].content

        structured = await parser_llm.ainvoke(
            f"Extract the portfolio holdings from the following tool output into structured data. "
            f"ONLY include stocks that appear in this data. Do NOT add any stocks not listed here. "
            f"Calculate total_value as quantity * current_price for each stock, "
            f"and total_portfolio_value as the sum of all total_values.\n\n"
            f"Tool output:\n{raw_data}"
        )

        return {"portfolio": structured}

    return portfolio_node

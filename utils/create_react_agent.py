from typing import Callable, List
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import tools_condition, ToolNode
from langchain_core.language_models import BaseChatModel


def build_react_agent(llm: BaseChatModel, tools: List[Callable], prompt: str = "", recursion_limit: int = 50):
    llm_with_tools = llm.bind_tools(tools)

    async def assistant(state: MessagesState):
        messages = state["messages"]
        if prompt:
            messages = [{"role": "system", "content": prompt}] + messages
        response = await llm_with_tools.ainvoke(messages)

        # Log tool calls for debugging
        if response.tool_calls:
            for tc in response.tool_calls:
                print(f"  [ReAct] Calling tool: {tc['name']}({list(tc['args'].keys())})")
        else:
            print("  [ReAct] Final response (no more tool calls)")

        return {"messages": [response]}

    react_graph = StateGraph(MessagesState)
    react_graph.add_node("assistant", assistant)
    react_graph.add_node("tools", ToolNode(tools))

    react_graph.add_edge(START, "assistant")
    react_graph.add_conditional_edges("assistant", tools_condition)
    react_graph.add_edge("tools", "assistant")

    compiled = react_graph.compile()
    compiled.recursion_limit = recursion_limit
    return compiled





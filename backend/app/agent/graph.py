from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from app.agent.state import AgentState
from app.agent.nodes import rewrite_node, router_node, retrieve_node, generate_node, verify_node
from app.agent.tools import list_documents, count_documents, search_documents, get_document


def _route_after_router(state: AgentState) -> str:
    return state.get("route", "retrieve")


def _route_after_verify(state: AgentState) -> str:
    if state.get("verify_retrieve"):
        return "retrieve"
    return END


def build_agent():
    g = StateGraph(AgentState)
    g.add_node("rewrite", rewrite_node)
    g.add_node("router", router_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("generate", generate_node)
    g.add_node("verify", verify_node)
    g.add_node("tools", ToolNode([list_documents, count_documents, search_documents, get_document]))
    g.add_edge("rewrite", "router")
    g.add_conditional_edges("router", _route_after_router,
                            {"retrieve": "retrieve", "tool": "tools", "direct": "generate"})
    g.add_edge("tools", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "verify")
    g.add_conditional_edges("verify", _route_after_verify, {"retrieve": "retrieve", END: END})
    g.set_entry_point("rewrite")
    return g.compile()


def run_agent(state: AgentState) -> AgentState:
    return build_agent().invoke(state)

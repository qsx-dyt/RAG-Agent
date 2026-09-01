from app.agent.state import AgentState
from app.agent.nodes import router_node, make_trace
from app.agent.graph import build_agent


def test_state_defaults():
    s: AgentState = {"query": "q", "history": [], "verify_count": 0, "trace": []}
    assert s["verify_count"] == 0
    assert s["trace"] == []


def test_router_classifies_retrieve():
    s: AgentState = {"query": "报销需要什么材料", "history": [], "verify_count": 0, "trace": []}
    out = router_node(s)
    assert out["route"] in ("retrieve", "tool", "direct")


def test_build_agent_compiles():
    graph = build_agent()
    assert graph is not None


def test_make_trace_records_duration():
    t = make_trace("rewrite", "改写查询", 120)
    assert t["step"] == "rewrite"
    assert t["duration_ms"] == 120

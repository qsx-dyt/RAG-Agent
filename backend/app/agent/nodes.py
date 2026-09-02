import time
from app.agent.state import AgentState, TraceStep
from app.agent.prompts import REWRITE_PROMPT, ROUTER_PROMPT, GENERATE_PROMPT, VERIFY_PROMPT
from app.core.llm import get_llm
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank
from app.config import get_settings


def make_trace(step: str, summary: str, duration_ms: int) -> TraceStep:
    return TraceStep(step=step, summary=summary, duration_ms=duration_ms)


def _llm_text(prompt: str) -> str:
    resp = get_llm().invoke(prompt)
    return resp.content if isinstance(resp.content, str) else str(resp.content)


def _with_trace(state: AgentState, step: str, summary: str, t0: float) -> dict:
    return {"trace": [*state.get("trace", []),
                      make_trace(step, summary, int((time.time() - t0) * 1000))]}


def rewrite_node(state: AgentState) -> dict:
    t0 = time.time()
    history = state.get("history", [])
    try:
        rewritten = _llm_text(REWRITE_PROMPT.format(query=state["query"], history=history))
    except Exception:
        rewritten = state["query"]
    out = _with_trace(state, "rewrite", "改写查询", t0)
    out["rewritten_query"] = rewritten.strip()
    return out


def router_node(state: AgentState) -> dict:
    t0 = time.time()
    q = state.get("rewritten_query") or state["query"]
    try:
        route = _llm_text(ROUTER_PROMPT.format(query=q)).strip().lower()
    except Exception:
        route = "retrieve"
    if route not in ("tool", "direct"):
        route = "retrieve"
    out = _with_trace(state, "router", f"路由: {route}", t0)
    out["route"] = route
    return out


def retrieve_node(state: AgentState) -> dict:
    t0 = time.time()
    q = state.get("rewritten_query") or state["query"]
    filters = None
    for call in state.get("tool_calls", []):
        if isinstance(call, dict) and call.get("filters"):
            filters = call["filters"]
    hits = hybrid_search(q, get_settings().retrieve_top_k, filters)
    hits = rerank(q, hits, get_settings().retrieve_top_k)
    out = _with_trace(state, "retrieve", f"检索到 {len(hits)} 个切片", t0)
    out["retrieved"] = hits
    return out


def generate_node(state: AgentState) -> dict:
    t0 = time.time()
    q = state.get("rewritten_query") or state["query"]
    retrieved = state.get("retrieved", [])
    context = "\n\n".join(f"[{i + 1}] {h.get('content', '')}" for i, h in enumerate(retrieved))
    try:
        answer = _llm_text(GENERATE_PROMPT.format(context=context or "（无检索结果）", query=q))
    except Exception as exc:
        answer = (f"【生成回答失败】LLM 调用出错（{type(exc).__name__}），以下为检索到的相关片段：\n\n"
                  f"{context or '（无检索结果）'}")
    citations = [{"index": i + 1,
                  "chunk_id": str(h["chunk_id"]) if h.get("chunk_id") else None,
                  "document_id": str(h["document_id"]) if h.get("document_id") else None,
                  "content": h.get("content", ""), "score": h.get("score")}
                 for i, h in enumerate(retrieved)]
    out = _with_trace(state, "generate", "生成回答", t0)
    out["answer"] = answer
    out["citations"] = citations
    return out


def verify_node(state: AgentState) -> dict:
    t0 = time.time()
    if state.get("verify_count", 0) >= 1 or not state.get("retrieved"):
        return _with_trace(state, "verify", "无需补检", t0)
    context = "\n\n".join(h.get("content", "") for h in state.get("retrieved", []))
    try:
        verdict = _llm_text(VERIFY_PROMPT.format(answer=state.get("answer", ""), context=context)).strip().lower()
    except Exception:
        verdict = "yes"
    if verdict.startswith("yes"):
        return _with_trace(state, "verify", "引用充分", t0)
    out = _with_trace(state, "verify", "引用不足,补检", t0)
    out["verify_retrieve"] = True
    out["verify_count"] = state.get("verify_count", 0) + 1
    return out

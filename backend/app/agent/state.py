from typing import TypedDict


class TraceStep(TypedDict, total=False):
    step: str
    summary: str
    duration_ms: int


class AgentState(TypedDict, total=False):
    query: str
    rewritten_query: str
    history: list[dict]
    retrieved: list[dict]
    tool_calls: list[str]
    answer: str
    citations: list[dict]
    verify_count: int
    trace: list[TraceStep]
    route: str

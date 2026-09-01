from typing import Any, Callable
from app.config import get_settings

_reranker: Callable | None = None


def _default_reranker(query: str, hits: list[dict], top_k: int) -> list[dict]:
    # 可选依赖 FlagEmbedding;未安装时抛错,由调用方 try/except 兜底
    from FlagEmbedding import FlagReranker  # type: ignore
    model = FlagReranker(get_settings().rerank_model)
    pairs = [(query, h.get("content", "")) for h in hits]
    scores = model.compute_score(pairs)
    ranked = sorted(zip(hits, scores), key=lambda x: x[1], reverse=True)
    return [{**h, "score": float(s)} for h, s in ranked[:top_k]]


def rerank(query: str, hits: list[dict], top_k: int) -> list[dict]:
    if not get_settings().rerank_enabled:
        return hits[:top_k]
    if _reranker is not None:
        return _reranker(query, hits, top_k)
    try:
        return _default_reranker(query, hits, top_k)
    except Exception:
        return hits[:top_k]

import jieba
from typing import Any
from sqlalchemy import text
from app.core.db import SessionLocal
from app.core.llm import embed_texts
from app.core.milvus import get_milvus_client


def tokenize_cn(text: str) -> str:
    return " ".join(jieba.cut(text))


def keyword_search(query: str, top_k: int, filters: dict | None = None) -> list[dict[str, Any]]:
    q = tokenize_cn(query)
    db = SessionLocal()
    try:
        sql = """
            SELECT c.id AS chunk_id, c.document_id, c.content,
                   ts_rank(to_tsvector('simple', c.content),
                           plainto_tsquery('simple', :q)) AS score
            FROM chunks c
            WHERE to_tsvector('simple', c.content) @@ plainto_tsquery('simple', :q)
            ORDER BY score DESC
            LIMIT :limit
        """
        rows = db.execute(text(sql), {"q": q, "limit": top_k}).mappings().all()
        return [dict(r) for r in rows]
    finally:
        db.close()


def vector_search(query: str, top_k: int, filters: dict | None = None) -> list[dict[str, Any]]:
    expr = None
    if filters and filters.get("document_ids"):
        ids = ",".join(f'"{i}"' for i in filters["document_ids"])
        expr = f"document_id in [{ids}]"
    vec = embed_texts([query])[0]
    return get_milvus_client().search(vec, top_k=top_k, expr=expr)


def rrf_fuse(vec_hits: list[dict], kw_hits: list[dict], k: int = 60) -> list[dict]:
    score_map: dict[str, dict] = {}
    for rank, hit in enumerate(vec_hits):
        key = hit["chunk_id"]
        score_map.setdefault(key, {"chunk_id": key, "score": 0.0, "sources": set()})
        score_map[key]["score"] += 1.0 / (k + rank + 1)
        score_map[key]["sources"].add("vector")
    for rank, hit in enumerate(kw_hits):
        key = hit["chunk_id"]
        score_map.setdefault(key, {"chunk_id": key, "score": 0.0, "sources": set()})
        score_map[key]["score"] += 1.0 / (k + rank + 1)
        score_map[key]["sources"].add("keyword")
    fused = sorted(score_map.values(), key=lambda x: x["score"], reverse=True)
    for item in fused:
        item["sources"] = sorted(item["sources"])
    return fused


def hybrid_search(query: str, top_k: int, filters: dict | None = None) -> list[dict[str, Any]]:
    try:
        vec = vector_search(query, top_k * 2, filters)
    except Exception as exc:
        print(f"[warn] vector search failed, fallback to keyword-only: {exc}")
        return keyword_search(query, top_k, filters)
    kw = keyword_search(query, top_k * 2, filters)
    return rrf_fuse(vec, kw)[:top_k]

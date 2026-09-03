"""此文件实现检索服务：分词、基于关键字的检索、基于向量的检索，以及两者的混合（RRF 融合）。
面向中文文本（使用 jieba 分词）、关系型数据库存储文本块（chunks 表），
向量检索使用 Milvus，向量由 app.core.llm.embed_texts 生成。
先尝试向量检索，若抛异常则打印 warning 并回退到 keyword_search。"""

import jieba
from typing import Any
from sqlalchemy import text
from app.core.db import SessionLocal, engine
from app.core.llm import embed_texts
from app.core.milvus import get_milvus_client


def tokenize_cn(text: str) -> str:
    return " ".join(jieba.cut(text))


def _is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"


def keyword_search(query: str, top_k: int, filters: dict | None = None) -> list[dict[str, Any]]:
    q = tokenize_cn(query)
    db = SessionLocal()
    try:
        if _is_sqlite():
            words = [w for w in jieba.cut(query) if w.strip()]
            if not words:
                return []
            # 逐词 OR 匹配,按命中词数降序(近似 FTS 召回)
            clauses = " OR ".join(["c.content LIKE :w%d" % i for i in range(len(words))])
            params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
            params["limit"] = top_k
            sql = f"""
                SELECT c.id AS chunk_id, c.document_id, c.content,
                       CAST(
                         ({' + '.join(['(c.content LIKE :w%d)' % i for i in range(len(words))])})
                       AS FLOAT) AS score
                FROM chunks c
                WHERE {clauses}
                ORDER BY score DESC
                LIMIT :limit
            """
            rows = db.execute(text(sql), params).mappings().all()
            return [dict(r) for r in rows]
        words = [w for w in jieba.cut(query) if w.strip()]
        if not words:
            return []
        # OR 语义:任一中文词命中即召回,ts_rank 按命中度排序(与向量检索互补)
        tsq = " | ".join('"%s"' % w for w in words)
        sql = """
            SELECT c.id AS chunk_id, c.document_id, c.content,
                   ts_rank(to_tsvector('simple', c.search_text),
                           to_tsquery('simple', :q)) AS score
            FROM chunks c
            WHERE to_tsvector('simple', c.search_text) @@ to_tsquery('simple', :q)
            ORDER BY score DESC
            LIMIT :limit
        """
        rows = db.execute(text(sql), {"q": tsq, "limit": top_k}).mappings().all()
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


def _carry(target: dict, hit: dict) -> None:
    for field in ("document_id", "content"):
        if target.get(field) is None and hit.get(field):
            target[field] = hit[field]


def rrf_fuse(vec_hits: list[dict], kw_hits: list[dict], k: int = 60) -> list[dict]:
    score_map: dict[str, dict] = {}
    for rank, hit in enumerate(vec_hits):
        key = hit["chunk_id"]
        item = score_map.setdefault(key, {"chunk_id": key, "score": 0.0, "sources": set()})
        item["score"] += 1.0 / (k + rank + 1)
        item["sources"].add("vector")
        _carry(item, hit)
    for rank, hit in enumerate(kw_hits):
        key = hit["chunk_id"]
        item = score_map.setdefault(key, {"chunk_id": key, "score": 0.0, "sources": set()})
        item["score"] += 1.0 / (k + rank + 1)
        item["sources"].add("keyword")
        _carry(item, hit)
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


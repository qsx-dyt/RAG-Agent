from langchain_core.tools import tool
from sqlalchemy import text
from app.core.db import SessionLocal


@tool
def list_documents(limit: int = 20) -> str:
    """列出知识库中的文档(标题、类型、状态)。"""
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT title, source_type, status FROM documents ORDER BY created_at DESC LIMIT :l"), {"l": limit}).mappings().all()
        return "\n".join(f"- {r['title']} ({r['source_type']}, {r['status']})" for r in rows)
    finally:
        db.close()


@tool
def count_documents(source_type: str = "") -> str:
    """统计文档数量。source_type 可选 'pdf' 或 'markdown'。"""
    db = SessionLocal()
    try:
        sql = "SELECT count(*) AS n FROM documents"
        params = {}
        if source_type:
            sql += " WHERE source_type = :t"
            params["t"] = source_type
        return str(db.execute(text(sql), params).scalar_one())
    finally:
        db.close()


@tool
def search_documents(query: str, document_ids: list[str] | None = None) -> str:
    """带过滤的检索,返回最相关的切片文本。document_ids 可指定文档。"""
    from app.services.retrieval import hybrid_search
    hits = hybrid_search(query, 5, {"document_ids": document_ids} if document_ids else None)
    return "\n\n".join(f"[{h.get('chunk_id')}] {h.get('content', '')[:500]}" for h in hits)


@tool
def get_document(title: str) -> str:
    """按标题取整篇文档文本。"""
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT c.content FROM chunks c JOIN documents d ON c.document_id = d.id "
            "WHERE d.title = :t ORDER BY c.chunk_index LIMIT 200"), {"t": title}).scalars().all()
        return "\n".join(rows)
    finally:
        db.close()

import hashlib
import uuid
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.llm import embed_texts
from app.core.milvus import get_milvus_client
from app.models.entities import Document, Chunk
from app.services.splitters import parse_and_split
from app.services.retrieval import tokenize_cn

UPLOAD_DIR = Path("storage/uploads")


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ingest_bytes(db: Session, filename: str, data: bytes, source_type: str) -> Document:
    checksum = _checksum(data)
    existing = db.query(Document).filter(Document.checksum == checksum, Document.status == "ready").first()
    if existing:
        return existing
    doc = Document(title=filename, source_type=source_type, checksum=checksum, status="processing")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{doc.id}_{filename}"
    path.write_bytes(data)
    doc.file_path = str(path)
    try:
        chunks = parse_and_split(source_type, str(path))
        rows, chunk_rows = [], []
        for i, c in enumerate(chunks):
            cid = str(uuid.uuid4())
            emb = embed_texts([c["content"]])[0]
            rows.append({"id": cid, "document_id": str(doc.id), "tenant_id": doc.tenant_id,
                         "content": c["content"][:8000], "embedding": emb})
            chunk_rows.append(Chunk(id=uuid.UUID(cid), document_id=doc.id, chunk_index=i,
                                    content=c["content"], heading=c["heading"],
                                    page=c["metadata"].get("page"), metadata_=c["metadata"],
                                    search_text=tokenize_cn(c["content"])))
        get_milvus_client().upsert_chunks(rows)
        db.add_all(chunk_rows)
        doc.status = "ready"
    except Exception as exc:
        db.rollback()
        doc = db.query(Document).get(doc.id)
        doc.status = "failed"
        doc.metadata_ = {**doc.metadata_, "error": str(exc)}
    db.commit()
    db.refresh(doc)
    return doc


def delete_document(db: Session, doc: Document) -> None:
    get_milvus_client().delete_by_document([str(doc.id)])
    db.delete(doc)
    db.commit()

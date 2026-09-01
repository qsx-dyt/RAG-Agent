import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.services import ingestion
from app.schemas.document import DocumentOut, ChunkOut
from app.models.entities import Document

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
MAX_SIZE = 20 * 1024 * 1024


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _source_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return "pdf"
    if ext in ("md", "markdown"):
        return "markdown"
    raise HTTPException(400, "仅支持 pdf / md / markdown 文件")


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    results = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_SIZE:
            results.append({"filename": f.filename, "status": "failed", "error": "文件超过 20MB"})
            continue
        try:
            st = _source_type(f.filename or "")
            doc = ingestion.ingest_bytes(db, f.filename or "unnamed", data, st)
            results.append({"id": str(doc.id), "filename": doc.title, "status": doc.status,
                            "error": doc.metadata_.get("error")})
        except Exception as exc:
            results.append({"filename": f.filename, "status": "failed", "error": str(exc)})
    return results


@router.get("", response_model=list[DocumentOut])
def list_documents(status: str | None = None, source_type: str | None = None,
                   page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_db)):
    q = db.query(Document)
    if status:
        q = q.filter(Document.status == status)
    if source_type:
        q = q.filter(Document.source_type == source_type)
    docs = q.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    out = []
    for d in docs:
        item = DocumentOut.model_validate(d)
        item.chunk_count = len(d.chunks)
        out.append(item)
    return out


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "文档不存在")
    item = DocumentOut.model_validate(d)
    item.chunk_count = len(d.chunks)
    return item


@router.get("/{doc_id}/chunks", response_model=list[ChunkOut])
def list_chunks(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "文档不存在")
    return sorted(d.chunks, key=lambda c: c.chunk_index)


@router.delete("/{doc_id}")
def delete(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "文档不存在")
    ingestion.delete_document(db, d)
    return {"ok": True}

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.models.entities import Conversation, Message
from app.schemas.chat import ConversationCreate, ConversationRename

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("")
def create_conversation(body: ConversationCreate, db: Session = Depends(get_db)):
    conv = Conversation(title=body.title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": str(conv.id), "title": conv.title, "created_at": str(conv.created_at)}


@router.get("")
def list_conversations(db: Session = Depends(get_db)):
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [{"id": str(c.id), "title": c.title, "created_at": str(c.created_at)} for c in convs]


@router.patch("/{conv_id}")
def rename_conversation(conv_id: UUID, body: ConversationRename, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    conv.title = body.title
    db.commit()
    db.refresh(conv)
    return {"id": str(conv.id), "title": conv.title, "created_at": str(conv.created_at)}


@router.delete("/{conv_id}")
def delete_conversation(conv_id: UUID, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    db.delete(conv)
    db.commit()
    return {"ok": True}


@router.get("/{conv_id}/messages")
def get_messages(conv_id: UUID, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at).all()
    out = []
    for m in msgs:
        out.append({"id": str(m.id), "role": m.role, "content": m.content,
                    "citations": [{"index": i + 1, "chunk_id": str(c.chunk_id), "document_id": str(c.document_id),
                                   "content": c.snippet, "score": c.score}
                                  for i, c in enumerate(m.citations)]})
    return out
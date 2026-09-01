from sqlalchemy.orm import Session
from app.agent.graph import run_agent
from app.agent.state import AgentState
from app.models.entities import Conversation, Message, Citation


def ensure_conversation(db: Session, title: str) -> Conversation:
    conv = Conversation(title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def make_message(db: Session, conversation_id, role: str, content: str) -> Message:
    m = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def get_history(db: Session, conversation_id, limit: int = 10) -> list[dict]:
    msgs = (db.query(Message).filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc()).limit(limit).all())
    return [{"role": m.role, "content": m.content} for m in reversed(msgs)]


def save_assistant(db: Session, conversation_id, result: dict) -> Message:
    m = Message(conversation_id=conversation_id, role="assistant", content=result.get("answer", ""))
    db.add(m)
    db.commit()
    db.refresh(m)
    for c in result.get("citations", []):
        db.add(Citation(message_id=m.id, chunk_id=c.get("chunk_id"), document_id=c.get("document_id"),
                        score=c.get("score"), snippet=c.get("content", "")[:500]))
    db.commit()
    return m


def run_agent_for(db: Session, conversation_id, message: str) -> AgentState:
    history = get_history(db, conversation_id, limit=6)
    state: AgentState = {"query": message, "history": history, "verify_count": 0, "trace": []}
    return run_agent(state)

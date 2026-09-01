import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.api.conversations import get_db
from app.schemas.chat import ChatRequest
from app.services import chat_service
from app.models.entities import Conversation

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _emit(event: str, data: dict):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_tokens(text: str, size: int = 8):
    for i in range(0, len(text), size):
        yield text[i : i + size]


@router.post("/chat")
async def chat(body: ChatRequest, db: Session = Depends(get_db)):
    conv = None
    if body.conversation_id is not None:
        conv = db.get(Conversation, body.conversation_id)
    if conv is None:
        conv = chat_service.ensure_conversation(db, body.message[:30])
    chat_service.make_message(db, conv.id, "user", body.message)

    def event_stream():
        yield _emit("start", {"conversation_id": str(conv.id)})
        result = chat_service.run_agent_for(db, conv.id, body.message)
        for t in result.get("trace", []):
            yield _emit("agent_trace", t)
        for token in _stream_tokens(result.get("answer", "")):
            yield _emit("token", {"text": token})
        yield _emit("citations", {"citations": result.get("citations", [])})
        assistant = chat_service.save_assistant(db, conv.id, result)
        yield _emit("done", {"message_id": str(assistant.id), "conversation_id": str(conv.id)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")

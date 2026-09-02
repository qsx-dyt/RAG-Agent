from uuid import UUID
from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = "新会话"


class ConversationRename(BaseModel):
    title: str


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: UUID
    title: str
    source_type: str
    status: str
    page_count: int | None = None
    chunk_count: int = 0
    metadata_: dict = Field(default_factory=dict, alias="metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class ChunkOut(BaseModel):
    id: UUID
    chunk_index: int
    content: str
    heading: str | None = None
    page: int | None = None

    model_config = {"from_attributes": True}

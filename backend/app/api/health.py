from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("")
def health():
    s = get_settings()
    return {"status": "ok", "milvus": s.milvus_host, "postgres": s.postgres_host}

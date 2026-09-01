from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import documents
from app.core.db import init_db
from app.core.milvus import get_milvus_client


def create_app() -> FastAPI:
    app = FastAPI(title="Enterprise RAG Agent", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(documents.router)

    @app.on_event("startup")
    def startup():
        init_db()
        get_milvus_client().ensure_collection()

    return app


app = create_app()

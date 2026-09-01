# 企业级 RAG Agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个可一键运行的企业级 RAG Agent 系统:FastAPI 后端 + LangGraph Agent 编排 + Milvus/PostgreSQL 检索 + React 前端,支持文档上传、混合检索问答、引用溯源与 RAG 评估。

**Architecture:** 写入流(上传→解析→切片→向量化→入库)与问答流(改写→路由→混合检索→生成→自检)两条管线;Agent 编排层用 LangGraph 状态图(rewrite/router/retrieve/tool/generate/verify 节点),数据层用 PostgreSQL(元数据/FTS/历史)+ Milvus(向量)。

**Tech Stack:** Python 3.11 + FastAPI + LangChain/LangGraph + SQLAlchemy 2 + Alembic + pymilvus + jieba + pdfplumber;React 18 + Vite + TypeScript + Ant Design 5 + React Query;Docker Compose;RAGAS。

**Spec:** `docs/superpowers/specs/2026-09-01-enterprise-rag-agent-design.md`

## Global Constraints

- 所有密钥/配置通过环境变量注入,`.env.example` 值全部为空占位;实现代码不得硬编码密钥。
- 支持文档格式仅 `.pdf` / `.md` / `.markdown`,单文件 ≤ 20MB。
- Embedding 维度由 `EMBEDDING_DIM` 决定(默认 1024,bge-m3);Milvus collection 首次创建时按该维度建。
- 检索融合固定用 RRF(k=60);检索 top_k 默认 10(配置 `RETRIEVE_TOP_K`)。
- Agent 自检最多补检 1 次(verify_count < 1)。
- API 统一前缀 `/api/v1`;错误响应使用 FastAPI 标准 `{detail: ...}`。
- 数据库表名与字段名严格遵循 spec §5;Milvus collection 名 `chunk_embeddings`。
- 后端代码在 `backend/`,前端代码在 `frontend/`,演示数据在 `sample_data/`。
- 中文 UI 文案;前端不使用 Redux(React Query + useState)。
- 每个任务结束必须 commit(按任务内给出的 commit 命令)。

---

## 文件结构总览

```
backend/
  pyproject.toml, Dockerfile, alembic.ini
  alembic/env.py, alembic/versions/0001_initial.py
  app/__init__.py, main.py, config.py
  app/core/__init__.py, db.py, milvus.py, llm.py, logging.py
  app/models/__init__.py, entities.py
  app/schemas/__init__.py, document.py, chat.py
  app/api/__init__.py, documents.py, conversations.py, chat.py, eval.py, health.py
  app/services/__init__.py, ingestion.py, retrieval.py, rerank.py, chat_service.py
  app/agent/__init__.py, state.py, nodes.py, tools.py, graph.py, prompts.py
  scripts/seed_sample.py, eval_ragas.py
  tests/conftest.py, fixtures/sample.md, fixtures/sample.pdf
  tests/test_config.py, test_ingestion.py, test_retrieval.py, test_agent.py, test_api.py
frontend/
  package.json, vite.config.ts, tsconfig.json, index.html, Dockerfile, nginx.conf
  src/main.tsx, App.tsx, api/client.ts, hooks/useChatStream.ts
  pages/ChatPage.tsx, pages/DocumentsPage.tsx
  components/MessageItem.tsx, CitationCard.tsx, TracePanel.tsx, UploadDropzone.tsx, DocumentTable.tsx
sample_data/ (6 份 MD + 2 份 PDF)
eval_dataset.json
docker-compose.yml, .env.example, README.md
```

---

## Task 0: 项目初始化与 git 仓库

**Files:**
- Create: `.gitignore`
- Create: `README.md`(骨架:项目名、快速启动段落占位,后续 Task 17 补全)
- Create: `backend/pyproject.toml`
- Create: `.env.example`(照抄 spec §13.1,值全空)

**Interfaces:**
- Produces: git 仓库初始化;`backend/` 包根;`.env.example` 供后续所有配置读取。

- [ ] **Step 1: 初始化 git 并建基础文件**

```bash
git init
```

创建 `.gitignore`:

```gitignore
__pycache__/
*.pyc
.venv/
node_modules/
dist/
.env
*.log
.idea/
.vscode/
```

创建 `backend/pyproject.toml`:

```toml
[project]
name = "enterprise-rag-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg[binary]>=3.1",
    "pymilvus>=2.4",
    "langchain>=0.3",
    "langchain-openai>=0.2",
    "langgraph>=0.2",
    "pypdf>=5.0",
    "pdfplumber>=0.11",
    "markdown-it-py>=3.0",
    "jieba>=0.42",
    "pydantic-settings>=2.4",
    "httpx>=0.27",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ragas>=0.2",
]
```

- [ ] **Step 2: 验证 python 环境可用**

Run: `python -c "import sys; print(sys.version)"`
Expected: 输出 3.11+ 版本号。

- [ ] **Step 3: Commit**

```bash
git add .gitignore README.md backend/pyproject.toml .env.example
git commit -m "chore: project scaffolding"
```

---

## Task 1: 配置模块(config.py)

**Files:**
- Create: `backend/app/__init__.py`(空)
- Create: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `get_settings() -> Settings` 单例;`Settings` 字段:
  `openai_api_key, openai_base_url, llm_model, embedding_api_key, embedding_base_url, embedding_model, embedding_dim, rerank_enabled, rerank_model, postgres_host, postgres_port, postgres_user, postgres_password, postgres_db, milvus_host, milvus_port, retrieve_top_k, chunk_size, chunk_overlap`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py
import os
from app.config import get_settings

def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "rag_test")
    s = get_settings()
    assert s.postgres_db == "rag_test"

def test_defaults_when_env_missing(monkeypatch):
    monkeypatch.delenv("RERANK_ENABLED", raising=False)
    s = get_settings()
    assert s.rerank_enabled is False
    assert s.embedding_dim == 1024
    assert s.chunk_size == 500
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL,`ModuleNotFoundError: app`。

- [ ] **Step 3: 实现配置模块**

```python
# app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = ""
    llm_model: str = ""

    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024

    rerank_enabled: bool = False
    rerank_model: str = "BAAI/bge-reranker-base"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "rag"
    postgres_password: str = ""
    postgres_db: str = "rag"

    milvus_host: str = "localhost"
    milvus_port: int = 19530

    retrieve_top_k: int = 10
    chunk_size: int = 500
    chunk_overlap: int = 80

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: pydantic-settings configuration module"
```
---

## Task 2: 数据库模型与迁移

**Files:**
- Create: `backend/app/core/__init__.py`(空)
- Create: `backend/app/core/db.py`
- Create: `backend/app/models/__init__.py`, `backend/app/models/entities.py`
- Create: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `get_settings()`(Task 1)
- Produces: `engine`(SQLAlchemy engine)、`SessionLocal`、`Base`;ORM 类 `Document, Chunk, Conversation, Message, Citation`(字段与 spec §5 一致);`init_db()`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_models.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.entities import Base, Document

def test_document_table_columns():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        d = Document(title="t", source_type="markdown", checksum="abc", status="processing")
        s.add(d)
        s.commit()
        assert d.id is not None
        assert d.tenant_id == "default"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL,`ModuleNotFoundError`。

- [ ] **Step 3: 实现 ORM 模型**

```python
# app/models/entities.py
import uuid
from datetime import datetime
from sqlalchemy import (
    UUID, String, Text, Integer, ForeignKey, JSON, DateTime, Float, func, CheckConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("source_type IN ('pdf','markdown')", name="ck_source_type"),
        CheckConstraint("status IN ('processing','ready','failed')", name="ck_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, default="default")
    title: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="processing")
    checksum: Mapped[str] = mapped_column(String)
    file_path: Mapped[str | None] = mapped_column(String)
    page_count: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    heading: Mapped[str | None] = mapped_column(String)
    page: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    checksum: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="chunks")
```

```python
# app/models/entities.py (追加,同一文件)
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, default="default")
    title: Mapped[str] = mapped_column(String, default="新会话")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    citations: Mapped[list["Citation"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("messages.id", ondelete="CASCADE"))
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID)
    score: Mapped[float | None] = mapped_column(Float)
    snippet: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped[Message] = relationship(back_populates="citations")
```

```python
# app/core/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.models.entities import Base


def make_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 4: 生成 Alembic 初始迁移**

```bash
cd backend
alembic init alembic
```

编辑 `alembic/env.py`:设置 `config.set_main_option("sqlalchemy.url", get_settings().database_url)`,并把 `target_metadata = Base.metadata`(从 `app.models.entities` import)。然后:

```bash
alembic revision --autogenerate -m "initial schema"
```

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/models backend/app/core/db.py backend/alembic backend/tests/test_models.py
git commit -m "feat: sqlalchemy models and initial alembic migration"
```

---

## Task 3: Milvus 客户端与 collection 初始化

**Files:**
- Create: `backend/app/core/milvus.py`
- Test: `backend/tests/test_milvus.py`(mock pymilvus)

**Interfaces:**
- Consumes: `get_settings()`(Task 1)
- Produces: `MilvusClient` 类:`ensure_collection()`, `upsert_chunks(rows)`, `search(query_embedding, top_k, expr=None) -> list[dict]`, `delete_by_document(document_ids)`;模块级 `get_milvus_client()`;测试注入 contextmanager `_client_override(fake)`。

- [ ] **Step 1: 写失败测试(mock)**

```python
# tests/test_milvus.py
from unittest.mock import MagicMock, patch
from app.core.milvus import MilvusClient

def test_ensure_collection_creates_when_missing():
    with patch("app.core.milvus.MilvusClient._collection_exists", return_value=False) as exists, \
         patch("app.core.milvus.MilvusClient._create_collection") as create:
        client = MilvusClient(host="h", port=19530, dim=1024)
        client.ensure_collection()
        exists.assert_called_once()
        create.assert_called_once()

def test_search_returns_hits():
    fake_hit = MagicMock()
    fake_hit.entity.get = {"id": "c1", "document_id": "d1", "content": "x"}
    fake_hit.distance = 0.9
    with patch.object(MilvusClient, "_raw_search", return_value=[[fake_hit]]):
        client = MilvusClient(host="h", port=19530, dim=1024)
        hits = client.search([0.1] * 1024, top_k=3)
        assert hits[0]["id"] == "c1"
        assert hits[0]["score"] == 0.9
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_milvus.py -v`
Expected: FAIL,`ImportError`。

- [ ] **Step 3: 实现 Milvus 客户端**

```python
# app/core/milvus.py
from contextlib import contextmanager
from typing import Any
from pymilvus import MilvusClient as PyMilvusClient, DataType


class MilvusClient:
    COLLECTION = "chunk_embeddings"

    def __init__(self, host: str, port: int, dim: int):
        self.uri = f"http://{host}:{port}"
        self.dim = dim
        self._client = PyMilvusClient(uri=self.uri)

    def _collection_exists(self) -> bool:
        return self._client.has_collection(self.COLLECTION)

    def _create_collection(self) -> None:
        schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, max_length=64, is_primary=True)
        schema.add_field("document_id", DataType.VARCHAR, max_length=64)
        schema.add_field("tenant_id", DataType.VARCHAR, max_length=64)
        schema.add_field("content", DataType.VARCHAR, max_length=8192)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.dim)
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="embedding", index_type="HNSW", metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        index_params.add_index(field_name="document_id", index_type="Trie")
        self._client.create_collection(self.COLLECTION, schema=schema, index_params=index_params)

    def ensure_collection(self) -> None:
        if not self._collection_exists():
            self._create_collection()

    def upsert_chunks(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            self._client.upsert(collection_name=self.COLLECTION, data=rows)

    def search(self, query_embedding: list[float], top_k: int, expr: str | None = None) -> list[dict[str, Any]]:
        res = self._raw_search(query_embedding, top_k, expr)
        out = []
        for hit in res[0]:
            out.append({"id": hit.entity.get("id"), "document_id": hit.entity.get("document_id"),
                        "content": hit.entity.get("content"), "score": hit.distance})
        return out

    def _raw_search(self, query_embedding, top_k, expr):
        return self._client.search(
            collection_name=self.COLLECTION, data=[query_embedding], limit=top_k,
            output_fields=["id", "document_id", "content"], filter=expr,
        )

    def delete_by_document(self, document_ids: list[str]) -> None:
        if not document_ids:
            return
        ids = ",".join(f'"{i}"' for i in document_ids)
        self._client.delete(collection_name=self.COLLECTION, filter=f"document_id in [{ids}]")


_client: MilvusClient | None = None


@contextmanager
def _client_override(fake):
    global _client
    old = _client
    _client = fake
    try:
        yield fake
    finally:
        _client = old


def get_milvus_client() -> MilvusClient:
    global _client
    if _client is None:
        from app.config import get_settings
        s = get_settings()
        _client = MilvusClient(host=s.milvus_host, port=s.milvus_port, dim=s.embedding_dim)
    return _client
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_milvus.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/milvus.py backend/tests/test_milvus.py
git commit -m "feat: milvus client with collection bootstrap"
```
---

## Task 4: LLM / Embedding 客户端

**Files:**
- Create: `backend/app/core/llm.py`
- Test: `backend/tests/test_llm.py`(mock 响应)

**Interfaces:**
- Produces: `get_llm() -> ChatOpenAI`(temperature=0.2, timeout=60)、`get_embeddings() -> OpenAIEmbeddings`;`embed_texts(texts, batch_size=16) -> list[list[float]]`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_llm.py
from unittest.mock import patch
from app.core.llm import embed_texts

def test_embed_texts_batches():
    fake = lambda texts: [[0.1] * 4 for _ in texts]
    with patch("app.core.llm.get_embeddings", return_value=fake):
        out = embed_texts(["a"] * 17, batch_size=16)
        assert len(out) == 17
        assert len(out[0]) == 4
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_llm.py -v`
Expected: FAIL,`ImportError`。

- [ ] **Step 3: 实现**

```python
# app/core/llm.py
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.config import get_settings


def get_llm() -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(model=s.llm_model, api_key=s.openai_api_key or "EMPTY",
                      base_url=s.openai_base_url or None, temperature=0.2,
                      timeout=60, max_retries=1)


def get_embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    return OpenAIEmbeddings(model=s.embedding_model, api_key=s.embedding_api_key or "EMPTY",
                            base_url=s.embedding_base_url or None)


def embed_texts(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    embeddings = get_embeddings()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        out.extend(embeddings.embed_documents(batch))
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_llm.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/llm.py backend/tests/test_llm.py
git commit -m "feat: llm and embedding clients"
```

---

## Task 5: 文档解析器与切片器

**Files:**
- Create: `backend/app/services/__init__.py`(空)
- Create: `backend/app/services/parsers.py`
- Create: `backend/app/services/splitters.py`
- Test: `backend/tests/test_parsers.py`, `backend/tests/test_splitters.py`

**Interfaces:**
- Consumes: `get_settings()`(chunk_size/chunk_overlap)
- Produces:
  - `parse_pdf(path: str) -> list[dict]`(每项 `{text, page}`)
  - `parse_markdown(path: str) -> str`
  - `split_markdown(text: str) -> list[dict]`(`{content, heading, metadata}`)
  - `split_text_pages(pages: list[dict]) -> list[dict]`
  - `parse_and_split(source_type, path) -> list[dict]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_splitters.py
from app.services.splitters import split_markdown, split_text_pages

def test_markdown_header_split():
    md = "# 报销制度\n差旅费报销需要发票。\n## 审批流程\n需财务审核。"
    chunks = split_markdown(md)
    assert any(c["heading"] == "报销制度" for c in chunks)

def test_pdf_pages_keep_page_number():
    pages = [{"text": "第一页内容" * 200, "page": 1},
             {"text": "第二页内容" * 200, "page": 2}]
    chunks = split_text_pages(pages)
    assert chunks[0]["metadata"]["page"] in (1, 2)
    assert len(chunks) > 2
```

```python
# tests/test_parsers.py
import pytest
from reportlab.pdfgen import canvas
from app.services.parsers import parse_pdf

def test_parse_pdf(tmp_path):
    p = tmp_path / "tiny.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(100, 700, "hello rag")
    c.save()
    pages = parse_pdf(str(p))
    assert pages[0]["page"] == 1
    assert "hello rag" in pages[0]["text"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_splitters.py tests/test_parsers.py -v`
Expected: FAIL,`ImportError`。

- [ ] **Step 3: 实现解析器**

```python
# app/services/parsers.py
from pathlib import Path
import pdfplumber


def parse_pdf(path: str) -> list[dict]:
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"text": text, "page": i})
    return pages


def parse_markdown(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")
```

```python
# app/services/splitters.py
from typing import Any
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from app.config import get_settings


def split_markdown(text: str) -> list[dict[str, Any]]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")]
    )
    docs = splitter.split_text(text)
    out = []
    for i, d in enumerate(docs):
        heading = d.metadata.get("h1") or d.metadata.get("h2") or d.metadata.get("h3") or ""
        out.append({"content": d.page_content, "heading": heading, "metadata": {}})
    return out


def split_text_pages(pages: list[dict]) -> list[dict[str, Any]]:
    s = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )
    out = []
    for page in pages:
        for piece in splitter.split_text(page["text"]):
            out.append({"content": piece, "heading": None, "metadata": {"page": page["page"]}})
    return out


def parse_and_split(source_type: str, path: str) -> list[dict[str, Any]]:
    if source_type == "pdf":
        from app.services.parsers import parse_pdf
        return split_text_pages(parse_pdf(path))
    if source_type == "markdown":
        from app.services.parsers import parse_markdown
        return split_markdown(parse_markdown(path))
    raise ValueError(f"unsupported source_type: {source_type}")
```

- [ ] **Step 4: 安装测试依赖并运行**

Run: `cd backend && pip install "reportlab" && python -m pytest tests/test_splitters.py tests/test_parsers.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services backend/tests
git commit -m "feat: pdf/markdown parsing and chunking"
```

---

## Task 6: 摄取服务(Ingestion)与文档 API

**Files:**
- Create: `backend/app/schemas/__init__.py`, `backend/app/schemas/document.py`
- Create: `backend/app/services/ingestion.py`
- Create: `backend/app/api/__init__.py`, `backend/app/api/documents.py`
- Create: `backend/app/main.py`(create_app 工厂 + 路由挂载 + CORS)
- Test: `backend/tests/test_api.py`(TestClient,mock Milvus 与 embedding)

**Interfaces:**
- Consumes: `get_settings()`, `SessionLocal`, `get_milvus_client()`, `embed_texts()`, `parse_and_split()`
- Produces:
  - `ingest_bytes(db, filename, data, source_type) -> Document`(校验去重、切片、embedding、Milvus upsert、写 chunks、状态流转)
  - `delete_document(db, doc) -> None`(先删 Milvus 再删 PG)
  - 路由:`POST /api/v1/documents/upload`、`GET /api/v1/documents`、`GET /api/v1/documents/{id}`、`DELETE /api/v1/documents/{id}`、`GET /api/v1/documents/{id}/chunks`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api.py
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.core import llm as llm_mod
from app.core.milvus import _client_override


def test_upload_markdown(tmp_path):
    fake_milvus = MagicMock()
    with _client_override(fake_milvus), \
         patch.object(llm_mod, "embed_texts", return_value=[[0.1] * 1024]):
        app = create_app()
        client = TestClient(app)
        f = tmp_path / "a.md"
        f.write_text("# 制度\n内容", encoding="utf-8")
        resp = client.post("/api/v1/documents/upload",
                           files={"files": ("a.md", f.read_bytes(), "text/markdown")})
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["status"] == "ready"
```

> 说明:`ingest_bytes` 会写 `storage/uploads/`(相对 backend 工作目录);测试依赖 sqlite 兼容的 ORM,若默认连 PG 失败,在测试 conftest 中用 sqlite 覆盖 `database_url`(见 Step 4)。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: FAIL,`ModuleNotFoundError: app.main`。

- [ ] **Step 3: 实现摄取服务**

```python
# app/services/ingestion.py
import hashlib
import uuid
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.llm import embed_texts
from app.core.milvus import get_milvus_client
from app.models.entities import Document, Chunk
from app.services.splitters import parse_and_split

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
                                    page=c["metadata"].get("page"), metadata_=c["metadata"]))
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
```

```python
# app/schemas/document.py
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
```

- [ ] **Step 4: 实现文档路由与 main,并加测试 conftest(sqlite 覆盖)**

```python
# tests/conftest.py
import os

os.environ.setdefault("POSTGRES_DB", "rag")
os.environ.setdefault("DATABASE_URL_TEST", "sqlite+pysqlite:///:memory:")
```

> 说明:`app/core/db.py` 的 engine 在 import 时创建;测试若需 sqlite,可在 conftest 中先设 `POSTGRES_HOST` 等,或把 `make_engine()` 改为读取 `DATABASE_URL` 环境变量(优先)。实现时: `engine = create_engine(os.environ.get("DATABASE_URL") or get_settings().database_url)`;测试 conftest 设 `DATABASE_URL=sqlite+pysqlite:///:memory:`。

```python
# app/api/documents.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.services import ingestion
from app.schemas.document import DocumentOut, ChunkOut
from app.models.entities import Document

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
ALLOWED = {"pdf", "markdown"}
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
```

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import documents
from app.core.db import init_db
from app.core.milvus import get_milvus_client


def create_app() -> FastAPI:
    app = FastAPI(title="Enterprise RAG Agent", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(documents.router)
    return app


app = create_app()


@app.on_event("startup")
def startup():
    init_db()
    get_milvus_client().ensure_collection()
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests/conftest.py backend/tests/test_api.py
git commit -m "feat: document upload/ingestion pipeline and document APIs"
```
---

## Task 7: 关键词检索(FTS + jieba)与混合检索 + RRF

**Files:**
- Create: `backend/app/services/retrieval.py`
- Test: `backend/tests/test_retrieval.py`

**Interfaces:**
- Consumes: `SessionLocal`, `get_milvus_client()`, `embed_texts()`
- Produces:
  - `tokenize_cn(text: str) -> str`(jieba 分词,空格连接)
  - `keyword_search(query, top_k, filters=None) -> list[dict]`(PG FTS,返回 `{chunk_id, document_id, content, score}`)
  - `vector_search(query, top_k, filters=None) -> list[dict]`
  - `rrf_fuse(vec_hits, kw_hits, k=60) -> list[dict]`(融合,`sources` 标记)
  - `hybrid_search(query, top_k, filters=None) -> list[dict]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_retrieval.py
from app.services.retrieval import rrf_fuse, tokenize_cn

def test_rrf_fuse_merges_rankings():
    vec = [{"chunk_id": "a"}, {"chunk_id": "b"}]
    kw = [{"chunk_id": "b"}, {"chunk_id": "c"}]
    fused = rrf_fuse(vec, kw, k=60)
    assert [x["chunk_id"] for x in fused] == ["b", "a", "c"]
    scores = {x["chunk_id"]: x["score"] for x in fused}
    assert scores["b"] > scores["a"]

def test_tokenize_cn_joins_with_space():
    assert tokenize_cn("报销审批流程") == "报销 审批 流程"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_retrieval.py -v`
Expected: FAIL,`ImportError`。

- [ ] **Step 3: 实现**

```python
# app/services/retrieval.py
import jieba
from typing import Any
from sqlalchemy import text
from app.core.db import SessionLocal
from app.core.llm import embed_texts
from app.core.milvus import get_milvus_client


def tokenize_cn(text: str) -> str:
    return " ".join(jieba.cut(text))


def keyword_search(query: str, top_k: int, filters: dict | None = None) -> list[dict[str, Any]]:
    q = tokenize_cn(query)
    db = SessionLocal()
    try:
        sql = """
            SELECT c.id AS chunk_id, c.document_id, c.content,
                   ts_rank(to_tsvector('simple', c.content),
                           plainto_tsquery('simple', :q)) AS score
            FROM chunks c
            WHERE to_tsvector('simple', c.content) @@ plainto_tsquery('simple', :q)
            ORDER BY score DESC
            LIMIT :limit
        """
        rows = db.execute(text(sql), {"q": q, "limit": top_k}).mappings().all()
        return [dict(r) for r in rows]
    finally:
        db.close()


def vector_search(query: str, top_k: int, filters: dict | None = None) -> list[dict[str, Any]]:
    expr = None
    if filters and filters.get("document_ids"):
        ids = ",".join(f'"{i}"' for i in filters["document_ids"])
        expr = f"document_id in [{ids}]"
    vec = embed_texts([query])[0]
    return get_milvus_client().search(vec, top_k=top_k, expr=expr)


def rrf_fuse(vec_hits: list[dict], kw_hits: list[dict], k: int = 60) -> list[dict]:
    score_map: dict[str, dict] = {}
    for rank, hit in enumerate(vec_hits):
        key = hit["chunk_id"]
        score_map.setdefault(key, {"chunk_id": key, "score": 0.0, "sources": set()})
        score_map[key]["score"] += 1.0 / (k + rank + 1)
        score_map[key]["sources"].add("vector")
    for rank, hit in enumerate(kw_hits):
        key = hit["chunk_id"]
        score_map.setdefault(key, {"chunk_id": key, "score": 0.0, "sources": set()})
        score_map[key]["score"] += 1.0 / (k + rank + 1)
        score_map[key]["sources"].add("keyword")
    fused = sorted(score_map.values(), key=lambda x: x["score"], reverse=True)
    for item in fused:
        item["sources"] = sorted(item["sources"])
    return fused


def hybrid_search(query: str, top_k: int, filters: dict | None = None) -> list[dict[str, Any]]:
    try:
        vec = vector_search(query, top_k * 2, filters)
    except Exception as exc:
        print(f"[warn] vector search failed, fallback to keyword-only: {exc}")
        return keyword_search(query, top_k, filters)
    kw = keyword_search(query, top_k * 2, filters)
    return rrf_fuse(vec, kw)[:top_k]
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_retrieval.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/retrieval.py backend/tests/test_retrieval.py
git commit -m "feat: hybrid retrieval with rrf fusion"
```

---

## Task 8: 重排服务(可选)

**Files:**
- Create: `backend/app/services/rerank.py`
- Test: `backend/tests/test_rerank.py`

**Interfaces:**
- Produces: `rerank(query, hits, top_k) -> list[dict]`;`RERANK_ENABLED=false` 时原样截断返回。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rerank.py
from app.services.rerank import rerank

def test_rerank_disabled_passthrough(monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "false")
    hits = [{"chunk_id": "a"}, {"chunk_id": "b"}]
    assert rerank("q", hits, top_k=2) == hits

def test_rerank_enabled_reorders(monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "true")
    fake = lambda q, docs, top_k: [{"chunk_id": d["chunk_id"], "score": s}
                                   for s, d in zip([0.9, 0.8], docs)]
    import app.services.rerank as mod
    mod._reranker = fake
    hits = [{"chunk_id": "a", "score": 0.1}, {"chunk_id": "b", "score": 0.2}]
    out = rerank("q", hits, top_k=2)
    assert out[0]["chunk_id"] == "a"
    mod._reranker = None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_rerank.py -v`
Expected: FAIL,`ImportError`。

- [ ] **Step 3: 实现**

```python
# app/services/rerank.py
from typing import Any, Callable
from app.config import get_settings

_reranker: Callable | None = None


def _default_reranker(query: str, hits: list[dict], top_k: int) -> list[dict]:
    # 可选依赖 FlagEmbedding;未安装时抛错,由调用方 try/except 兜底
    from FlagEmbedding import FlagReranker  # type: ignore
    model = FlagReranker(get_settings().rerank_model)
    pairs = [(query, h.get("content", "")) for h in hits]
    scores = model.compute_score(pairs)
    ranked = sorted(zip(hits, scores), key=lambda x: x[1], reverse=True)
    return [{**h, "score": float(s)} for h, s in ranked[:top_k]]


def rerank(query: str, hits: list[dict], top_k: int) -> list[dict]:
    if not get_settings().rerank_enabled:
        return hits[:top_k]
    if _reranker is not None:
        return _reranker(query, hits, top_k)
    try:
        return _default_reranker(query, hits, top_k)
    except Exception:
        return hits[:top_k]
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_rerank.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/rerank.py backend/tests/test_rerank.py
git commit -m "feat: optional rerank service"
```

---

## Task 9: Agent 状态、节点与图

**Files:**
- Create: `backend/app/agent/__init__.py`
- Create: `backend/app/agent/state.py`
- Create: `backend/app/agent/prompts.py`
- Create: `backend/app/agent/nodes.py`
- Create: `backend/app/agent/tools.py`
- Create: `backend/app/agent/graph.py`
- Test: `backend/tests/test_agent.py`

**Interfaces:**
- Consumes: `hybrid_search()`, `rerank()`, `get_llm()`, `SessionLocal`
- Produces:
  - `AgentState`(TypedDict)、`TraceStep`
  - 节点函数:`rewrite_node`, `router_node`, `retrieve_node`, `generate_node`, `verify_node`
  - 工具:`list_documents`, `count_documents`, `search_documents`, `get_document`
  - `build_agent() -> CompiledStateGraph`;`run_agent(state) -> AgentState`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent.py
from app.agent.state import AgentState
from app.agent.nodes import router_node
from app.agent.graph import build_agent

def test_state_defaults():
    s: AgentState = {"query": "q", "history": [], "verify_count": 0, "trace": []}
    assert s["verify_count"] == 0
    assert s["trace"] == []

def test_router_classifies_retrieve():
    s: AgentState = {"query": "报销需要什么材料", "history": [], "verify_count": 0, "trace": []}
    out = router_node(s)
    assert out["route"] in ("retrieve", "tool", "direct")

def test_build_agent_compiles():
    graph = build_agent()
    assert graph is not None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_agent.py -v`
Expected: FAIL,`ModuleNotFoundError`。

- [ ] **Step 3: 实现 state 与 prompts**

```python
# app/agent/state.py
from typing import TypedDict


class TraceStep(TypedDict, total=False):
    step: str
    summary: str
    duration_ms: int


class AgentState(TypedDict, total=False):
    query: str
    rewritten_query: str
    history: list[dict]
    retrieved: list[dict]
    tool_calls: list[str]
    answer: str
    citations: list[dict]
    verify_count: int
    trace: list[TraceStep]
    route: str
```

```python
# app/agent/prompts.py
REWRITE_PROMPT = """你是查询改写助手。根据对话历史,把用户的最后一句话改写成独立、自包含的检索查询。
只输出改写后的查询,不要任何解释。若无需改写,原样输出。
历史: {history}
用户: {query}"""

ROUTER_PROMPT = """判断用户问题类型,只输出一个词:
- tool: 需要统计、列举知识库文档元数据(如"共有几份文档"、"有哪些制度")
- retrieve: 需要从知识库文档中查找信息(默认)
- direct: 闲聊、天气、无关话题或感谢
问题: {query}"""

GENERATE_PROMPT = """你是企业知识库助手。基于给定的上下文回答,必须使用[1][2]等编号标注引用来源。
若上下文不足以回答,明确说明"知识库中未找到相关信息",不要编造。
上下文:
{context}
问题: {query}"""

VERIFY_PROMPT = """判断答案是否被引用的上下文充分支撑。回答 only yes 或 no。
答案: {answer}
上下文: {context}"""
```

- [ ] **Step 4: 实现节点**

```python
# app/agent/nodes.py
import time
from app.agent.state import AgentState, TraceStep
from app.agent.prompts import REWRITE_PROMPT, ROUTER_PROMPT, GENERATE_PROMPT, VERIFY_PROMPT
from app.core.llm import get_llm
from app.services.retrieval import hybrid_search
from app.services.rerank import rerank
from app.config import get_settings


def make_trace(step: str, summary: str, duration_ms: int) -> TraceStep:
    return TraceStep(step=step, summary=summary, duration_ms=duration_ms)


def _llm_text(prompt: str) -> str:
    resp = get_llm().invoke(prompt)
    return resp.content if isinstance(resp.content, str) else str(resp.content)


def _with_trace(state: AgentState, step: str, summary: str, t0: float) -> dict:
    return {"trace": [*state.get("trace", []),
                      make_trace(step, summary, int((time.time() - t0) * 1000))]}


def rewrite_node(state: AgentState) -> dict:
    t0 = time.time()
    history = state.get("history", [])
    try:
        rewritten = _llm_text(REWRITE_PROMPT.format(query=state["query"], history=history))
    except Exception:
        rewritten = state["query"]
    out = _with_trace(state, "rewrite", "改写查询", t0)
    out["rewritten_query"] = rewritten.strip()
    return out


def router_node(state: AgentState) -> dict:
    t0 = time.time()
    q = state.get("rewritten_query") or state["query"]
    try:
        route = _llm_text(ROUTER_PROMPT.format(query=q)).strip().lower()
    except Exception:
        route = "retrieve"
    if route not in ("tool", "direct"):
        route = "retrieve"
    out = _with_trace(state, "router", f"路由: {route}", t0)
    out["route"] = route
    return out


def retrieve_node(state: AgentState) -> dict:
    t0 = time.time()
    q = state.get("rewritten_query") or state["query"]
    filters = None
    for call in state.get("tool_calls", []):
        if isinstance(call, dict) and call.get("filters"):
            filters = call["filters"]
    hits = hybrid_search(q, get_settings().retrieve_top_k, filters)
    hits = rerank(q, hits, get_settings().retrieve_top_k)
    out = _with_trace(state, "retrieve", f"检索到 {len(hits)} 个切片", t0)
    out["retrieved"] = hits
    return out


def generate_node(state: AgentState) -> dict:
    t0 = time.time()
    q = state.get("rewritten_query") or state["query"]
    context = "\n\n".join(f"[{i + 1}] {h.get('content', '')}" for i, h in enumerate(state.get("retrieved", [])))
    answer = _llm_text(GENERATE_PROMPT.format(context=context or "（无检索结果）", query=q))
    citations = [{"index": i + 1, "chunk_id": h.get("chunk_id"), "document_id": h.get("document_id"),
                  "content": h.get("content", ""), "score": h.get("score")}
                 for i, h in enumerate(state.get("retrieved", []))]
    out = _with_trace(state, "generate", "生成回答", t0)
    out["answer"] = answer
    out["citations"] = citations
    return out


def verify_node(state: AgentState) -> dict:
    t0 = time.time()
    if state.get("verify_count", 0) >= 1 or not state.get("retrieved"):
        return _with_trace(state, "verify", "无需补检", t0)
    context = "\n\n".join(h.get("content", "") for h in state.get("retrieved", []))
    verdict = _llm_text(VERIFY_PROMPT.format(answer=state.get("answer", ""), context=context)).strip().lower()
    if verdict.startswith("yes"):
        return _with_trace(state, "verify", "引用充分", t0)
    out = _with_trace(state, "verify", "引用不足,补检", t0)
    out["verify_count"] = state.get("verify_count", 0) + 1
    return out
```

- [ ] **Step 5: 实现工具**

```python
# app/agent/tools.py
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
```

- [ ] **Step 6: 实现图**

```python
# app/agent/graph.py
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from app.agent.state import AgentState
from app.agent.nodes import rewrite_node, router_node, retrieve_node, generate_node, verify_node
from app.agent.tools import list_documents, count_documents, search_documents, get_document


def _route_after_router(state: AgentState) -> str:
    return state.get("route", "retrieve")


def _route_after_verify(state: AgentState) -> str:
    if state.get("verify_count", 0) < 1 and state.get("retrieved"):
        return "retrieve"
    return END


def build_agent():
    g = StateGraph(AgentState)
    g.add_node("rewrite", rewrite_node)
    g.add_node("router", router_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("generate", generate_node)
    g.add_node("verify", verify_node)
    g.add_node("tools", ToolNode([list_documents, count_documents, search_documents, get_document]))
    g.add_edge("rewrite", "router")
    g.add_conditional_edges("router", _route_after_router,
                            {"retrieve": "retrieve", "tool": "tools", "direct": "generate"})
    g.add_edge("tools", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "verify")
    g.add_conditional_edges("verify", _route_after_verify, {"retrieve": "retrieve", END: END})
    g.set_entry_point("rewrite")
    return g.compile()


def run_agent(state: AgentState) -> AgentState:
    return build_agent().invoke(state)
```

- [ ] **Step 7: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_agent.py -v`
Expected: PASS(3 passed)。

- [ ] **Step 8: Commit**

```bash
git add backend/app/agent backend/tests/test_agent.py
git commit -m "feat: langgraph agent with rewrite/router/retrieve/generate/verify"
```
---

## Task 10: 会话存储与 Chat API(SSE)

**Files:**
- Create: `backend/app/schemas/chat.py`
- Create: `backend/app/api/conversations.py`
- Create: `backend/app/api/chat.py`
- Create: `backend/app/services/chat_service.py`
- Modify: `backend/app/main.py`(挂载新路由)
- Test: `backend/tests/test_chat.py`

**Interfaces:**
- Consumes: `run_agent()`(Task 9)、`SessionLocal`、ORM `Conversation/Message/Citation`
- Produces:
  - `ensure_conversation(db, title) -> Conversation`
  - `make_message(db, conversation_id, role, content) -> Message`
  - `get_history(db, conversation_id, limit=10) -> list[dict]`
  - `save_assistant(db, conversation_id, result) -> Message`(保存答案 + citations)
  - 路由:`POST /api/v1/conversations`、`GET /api/v1/conversations`、`GET /api/v1/conversations/{id}/messages`
  - `POST /api/v1/chat`:SSE 事件 `start / agent_trace / token / citations / done`(格式见 spec §9)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_chat.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app


def test_create_conversation():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/v1/conversations", json={"title": "测试会话"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "测试会话"


def test_chat_streams_events():
    fake_state = {"answer": "答案是X", "citations": [], "trace": []}
    with patch("app.api.chat.run_agent", return_value=fake_state):
        app = create_app()
        client = TestClient(app)
        with client.stream("POST", "/api/v1/chat", json={"conversation_id": None, "message": "你好"}) as r:
            body = r.read().decode()
            assert "event: start" in body
            assert "event: done" in body
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_chat.py -v`
Expected: FAIL,`ModuleNotFoundError`。

- [ ] **Step 3: 实现 chat_service**

```python
# app/services/chat_service.py
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
```

- [ ] **Step 4: 实现 API**

```python
# app/schemas/chat.py
from uuid import UUID
from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = "新会话"


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    message: str
```

```python
# app/api/conversations.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.models.entities import Conversation, Message
from app.schemas.chat import ConversationCreate

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


@router.get("/{conv_id}/messages")
def get_messages(conv_id: UUID, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "会话不存在")
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at).all()
    out = []
    for m in msgs:
        out.append({"id": str(m.id), "role": m.role, "content": m.content,
                    "citations": [{"chunk_id": str(c.chunk_id), "document_id": str(c.document_id),
                                   "snippet": c.snippet, "score": c.score} for c in m.citations]})
    return out
```

```python
# app/api/chat.py
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.api.conversations import get_db
from app.schemas.chat import ChatRequest
from app.services import chat_service

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _emit(event: str, data: dict):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_tokens(text: str, size: int = 8):
    for i in range(0, len(text), size):
        yield text[i : i + size]


@router.post("/chat")
async def chat(body: ChatRequest, db: Session = Depends(get_db)):
    from app.models.entities import Conversation
    conv = None
    if body.conversation_id is not None:
        conv = db.get(Conversation, body.conversation_id)
```

```python
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
```

在 `app/main.py` 挂载 `conversations.router` 与 `chat.router`。

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_chat.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests/test_chat.py
git commit -m "feat: conversations and streaming chat API"
```

---

## Task 11: Docker Compose 基础设施与一键启动

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `backend/app/api/health.py`(挂载 `GET /api/v1/health`)
- Create: `frontend/Dockerfile`, `frontend/nginx.conf`(前端镜像占位,Task 13/14 完成后生效)

**Interfaces:**
- Consumes: Task 0–10 全部服务代码
- Produces: 六个容器 `etcd`、`minio`、`milvus-standalone`、`postgres`、`api`、`web`

- [ ] **Step 1: 写健康检查 API**

```python
# app/api/health.py
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("")
def health():
    s = get_settings()
    return {"status": "ok", "milvus": s.milvus_host, "postgres": s.postgres_host}
```

在 `main.py` 挂载 `health.router`。

- [ ] **Step 2: 写 docker-compose.yml**

```yaml
services:
  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
    volumes:
      - etcd_data:/etcd

  minio:
    image: minio/minio:RELEASE.2024-05-28T17-19-04Z
    environment:
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    command: minio server /minio_data --console-address ":9001"
    volumes:
      - minio_data:/minio_data

  milvus-standalone:
    image: milvusdb/milvus:v2.4.4
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    ports:
      - "19530:19530"
    depends_on:
      - etcd
      - minio

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: rag
      POSTGRES_PASSWORD: ragpass
      POSTGRES_DB: rag
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data

  api:
    build: ./backend
    env_file: .env
    environment:
      POSTGRES_HOST: postgres
      MILVUS_HOST: milvus-standalone
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - milvus-standalone

  web:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - api

volumes:
  etcd_data:
  minio_data:
  pg_data:
```

- [ ] **Step 3: 写 backend Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: 写 frontend 镜像占位**(Task 13/14 完成后内容即为最终)

`frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
COPY . .
RUN npm install && npm run build
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

`frontend/nginx.conf`:

```nginx
server {
  listen 80;
  location /api/ { proxy_pass http://api:8000; }
  location / { root /usr/share/nginx/html; try_files $uri /index.html; }
}
```

- [ ] **Step 5: 验收**

Run: `docker compose up -d --build`
Expected: 容器全部 running;`curl http://localhost:8000/api/v1/health` 返回 `{"status":"ok",...}`。

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml backend/Dockerfile frontend/Dockerfile frontend/nginx.conf backend/app/api/health.py
git commit -m "feat: docker compose full-stack bootstrap"
```
---

## Task 12: 前端脚手架(React + Vite + AntD)

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`(Vitest)

**Interfaces:**
- Consumes: 后端 API(spec §9)
- Produces: `apiFetch(path, opts)`、`buildChatUrl()`、`createConversation()`, `listDocuments()`, `uploadDocuments(files)`, `deleteDocument(id)`;`App.tsx` 提供路由 `/`(聊天)与 `/documents`(文档)

- [ ] **Step 1: 写失败测试**

```typescript
// frontend/src/api/client.test.ts
import { describe, it, expect } from "vitest";
import { buildChatUrl } from "./client";

describe("buildChatUrl", () => {
  it("prepends /api/v1", () => {
    expect(buildChatUrl()).toBe("/api/v1/chat");
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npm install && npx vitest run`
Expected: FAIL,`Cannot find module './client'`。

- [ ] **Step 3: 实现 client**

```typescript
// frontend/src/api/client.ts
const BASE = "/api/v1";

export function buildChatUrl(): string {
  return `${BASE}/chat`;
}

export async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const createConversation = (title = "新会话") =>
  apiFetch<{ id: string; title: string }>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });

export const listDocuments = () =>
  apiFetch<Array<Record<string, unknown>>>("/documents");

export const uploadDocuments = async (files: File[]) => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const resp = await fetch(`${BASE}/documents/upload`, { method: "POST", body: form });
  if (!resp.ok) throw new Error(`upload failed: ${resp.status}`);
  return resp.json();
};

export const deleteDocument = (id: string) =>
  apiFetch<{ ok: boolean }>(`/documents/${id}`, { method: "DELETE" });
```

- [ ] **Step 4: 搭脚手架文件**

`frontend/package.json`(关键字段):

```json
{
  "name": "rag-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "antd": "^5.20.0",
    "@tanstack/react-query": "^5.51.0",
    "marked": "^12.0.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "@vitejs/plugin-react": "^4.3.0",
    "vitest": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "jsdom": "^24.0.0"
  }
}
```

`frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: { environment: "node" },
});
```

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["vitest/globals"]
  },
  "include": ["src"]
}
```

`frontend/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <title>Enterprise RAG Agent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
```

`frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Layout, Menu } from "antd";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Layout style={{ minHeight: "100vh" }}>
        <Layout.Header>
          <Menu theme="dark" mode="horizontal" selectable={false}>
            <Menu.Item key="brand" style={{ fontWeight: 700, color: "#fff" }}>
              Enterprise RAG Agent
            </Menu.Item>
            <Menu.Item key="chat"><Link to="/">聊天</Link></Menu.Item>
            <Menu.Item key="docs"><Link to="/documents">文档管理</Link></Menu.Item>
          </Menu>
        </Layout.Header>
        <Layout.Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
          </Routes>
        </Layout.Content>
      </Layout>
    </BrowserRouter>
  );
}
```

> 注意:Task 12 结束时 `ChatPage`/`DocumentsPage` 尚未创建,`tsc -b` 会报错;本任务验收只跑 `vitest`,页面组件在 Task 13/14 补齐后 `npm run build` 才能通过。

- [ ] **Step 5: 运行确认通过**

Run: `cd frontend && npx vitest run`
Expected: PASS(1 passed)。

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: react frontend scaffold"
```

---

## Task 13: 聊天页(消息流 + 引用 + SSE)

**Files:**
- Create: `frontend/src/hooks/useChatStream.ts`
- Create: `frontend/src/pages/ChatPage.tsx`
- Create: `frontend/src/components/MessageItem.tsx`
- Create: `frontend/src/components/CitationCard.tsx`
- Create: `frontend/src/components/TracePanel.tsx`
- Test: `frontend/src/hooks/useChatStream.test.ts`

**Interfaces:**
- Consumes: `buildChatUrl()`(Task 12)
- Produces: `parseSSE(raw, onEvent)`(SSE 解析,测试导出)、`useChatStream()`(`{send(message, conversationId, onEvent)}`);`ChatPage`、`MessageItem`、`CitationCard`、`TracePanel` 组件

- [ ] **Step 1: 写失败测试(SSE 解析器)**

```typescript
// frontend/src/hooks/useChatStream.test.ts
import { describe, it, expect } from "vitest";
import { parseSSE } from "./useChatStream";

describe("parseSSE", () => {
  it("splits event blocks", () => {
    const chunk = "event: token\ndata: {\"text\":\"hi\"}\n\nevent: done\ndata: {}\n\n";
    const events: Array<{ event: string; data: string }> = [];
    parseSSE(chunk, (e) => events.push(e));
    expect(events).toHaveLength(2);
    expect(events[0].event).toBe("token");
    expect(JSON.parse(events[0].data).text).toBe("hi");
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run`
Expected: FAIL,`Cannot find module './useChatStream'`。

- [ ] **Step 3: 实现 SSE hook**

```typescript
// frontend/src/hooks/useChatStream.ts
import { buildChatUrl } from "../api/client";

export interface SSEEvent {
  event: string;
  data: string;
}

export function parseSSE(raw: string, onEvent: (e: SSEEvent) => void): void {
  for (const block of raw.split("\n\n")) {
    if (!block.trim()) continue;
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) event = line.slice(7);
      else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
    }
    if (dataLines.length) onEvent({ event, data: dataLines.join("\n") });
  }
}

export function useChatStream() {
  const send = async (
    message: string,
    conversationId: string | null,
    onEvent: (e: SSEEvent) => void
  ) => {
    const resp = await fetch(buildChatUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message }),
    });
    if (!resp.body) throw new Error("no response body");
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const idx = buffer.lastIndexOf("\n\n");
      if (idx >= 0) {
        parseSSE(buffer.slice(0, idx), onEvent);
        buffer = buffer.slice(idx + 2);
      }
    }
    if (buffer.trim()) parseSSE(buffer, onEvent);
  };
  return { send };
}
```

- [ ] **Step 4: 实现组件与页面**

`frontend/src/components/MessageItem.tsx`:

```tsx
import { marked } from "marked";
import { CitationCard } from "./CitationCard";

export interface Citation {
  index: number;
  chunk_id?: string;
  document_id?: string;
  content?: string;
  score?: number;
}

export default function MessageItem({ role, content, citations }: {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}) {
  if (role === "user") {
    return <div style={{ textAlign: "right" }}>{content}</div>;
  }
  const html = marked.parse(content) as string;
  return (
    <div>
      <div dangerouslySetInnerHTML={{ __html: html }} />
      {citations && citations.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {citations.map((c) => <CitationCard key={c.index} citation={c} />)}
        </div>
      )}
    </div>
  );
}
```

`frontend/src/components/CitationCard.tsx`:

```tsx
export default function CitationCard({ citation }: { citation: { index: number; content?: string; score?: number } }) {
  return (
    <div style={{ border: "1px solid #d9d9d9", borderRadius: 6, padding: 8, marginBottom: 4 }}>
      <strong>[{citation.index}]</strong>{" "}
      <span style={{ color: "#666", fontSize: 12 }}>
        {citation.content?.slice(0, 120)}…
      </span>
      {typeof citation.score === "number" && (
        <span style={{ float: "right", color: "#999" }}>{citation.score.toFixed(2)}</span>
      )}
    </div>
  );
}
```

`frontend/src/components/TracePanel.tsx`:

```tsx
import { Timeline } from "antd";

export interface TraceStep {
  step: string;
  summary: string;
  duration_ms?: number;
}

export default function TracePanel({ trace }: { trace: TraceStep[] }) {
  return (
    <Timeline
      items={trace.map((t) => ({
        children: (
          <span>
            <b>{t.step}</b>: {t.summary}
            {t.duration_ms != null && <span style={{ color: "#999" }}> ({t.duration_ms}ms)</span>}
          </span>
        ),
      }))}
    />
  );
}
```

`frontend/src/pages/ChatPage.tsx`(实现要点):

```tsx
import { useState } from "react";
import { Button, Input, List, Layout } from "antd";
import { useQuery, useMutation } from "@tanstack/react-query";
import MessageItem, { Citation } from "../components/MessageItem";
import TracePanel, { TraceStep } from "../components/TracePanel";
import { createConversation, apiFetch } from "../api/client";
import { useChatStream, SSEEvent } from "../hooks/useChatStream";

interface ConversationItem { id: string; title: string }
interface Msg { id: string; role: "user" | "assistant"; content: string; citations: Citation[] }

export default function ChatPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const { send } = useChatStream();

  const convsQuery = useQuery({ queryKey: ["conversations"],
    queryFn: () => apiFetch<ConversationItem[]>("/conversations") });
  const newConv = useMutation({
    mutationFn: createConversation,
    onSuccess: (c) => { setConversationId(c.id); setMessages([]); convsQuery.refetch(); },
  });

  const onEvent = (e: SSEEvent) => {
    const data = JSON.parse(e.data);
    if (e.event === "agent_trace") setTrace((prev) => [...prev, data]);
    else if (e.event === "token") {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant") {
          return [...prev.slice(0, -1), { ...last, content: last.content + data.text }];
        }
        return [...prev, { id: "tmp", role: "assistant", content: data.text, citations: [] }];
      });
    } else if (e.event === "citations") {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        return [...prev.slice(0, -1), { ...last, citations: data.citations }];
      });
    } else if (e.event === "done") {
      setStreaming(false);
    }
  };

  const submit = () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    setTrace([]);
    setMessages((prev) => [...prev, { id: "u" + Date.now(), role: "user", content: text, citations: [] }]);
    setStreaming(true);
    send(text, conversationId, onEvent).catch(() => setStreaming(false));
  };

  return (
    <Layout style={{ flexDirection: "row", gap: 16 }}>
      <div style={{ width: 220 }}>
        <Button block onClick={() => newConv.mutate()} style={{ marginBottom: 8 }}>新会话</Button>
        <List
          dataSource={convsQuery.data ?? []}
          renderItem={(c) => (
            <List.Item style={{ cursor: "pointer" }}
              onClick={() => { setConversationId(c.id); setMessages([]); }}>
              {c.title}
            </List.Item>
          )}
        />
      </div>
      <div style={{ flex: 1 }}>
        {messages.map((m, i) => <MessageItem key={i} role={m.role} content={m.content} citations={m.citations} />)}
        <Input.TextArea rows={3} value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="输入问题,回车发送" onPressEnter={submit} />
      </div>
      <div style={{ width: 260 }}>
        <h4>Agent 步骤</h4>
        <TracePanel trace={trace} />
      </div>
    </Layout>
  );
}
```

- [ ] **Step 5: 运行确认通过**

Run: `cd frontend && npx vitest run && npm run build`
Expected: PASS;`npm run dev` 打开 `http://localhost:5173` 可见聊天页(后端未起时请求报错属正常)。

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: chat page with streaming and agent trace"
```

---

## Task 14: 文档管理页

**Files:**
- Create: `frontend/src/pages/DocumentsPage.tsx`
- Create: `frontend/src/components/UploadDropzone.tsx`
- Create: `frontend/src/components/DocumentTable.tsx`
- Test: `frontend/src/components/UploadDropzone.test.tsx`

**Interfaces:**
- Consumes: `listDocuments()`, `uploadDocuments()`, `deleteDocument()`(Task 12)
- Produces: `DocumentsPage`(拖拽上传 + 文档表格 + 删除确认)

- [ ] **Step 1: 写失败测试**

```tsx
// frontend/src/components/UploadDropzone.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import UploadDropzone from "./UploadDropzone";

it("calls onUpload with files", async () => {
  const onUpload = vi.fn();
  const { container } = render(<UploadDropzone onUpload={onUpload} />);
  const input = container.querySelector("input[type=file]")!;
  const file = new File(["x"], "a.md", { type: "text/markdown" });
  fireEvent.change(input, { target: { files: [file] } });
  await waitFor(() => expect(onUpload).toHaveBeenCalledWith([file]));
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run`
Expected: FAIL,`Cannot find module './UploadDropzone'`。

- [ ] **Step 3: 实现组件**

`frontend/src/components/UploadDropzone.tsx`:

```tsx
import { Upload } from "antd";
import { InboxOutlined } from "@ant-design/icons";

export default function UploadDropzone({ onUpload }: { onUpload: (files: File[]) => void }) {
  return (
    <Upload.Dragger
      multiple
      accept=".pdf,.md,.markdown"
      beforeUpload={() => false}
      onChange={({ fileList }) => {
        if (fileList.length && fileList[fileList.length - 1].originFileObj) {
          onUpload(fileList.map((f) => f.originFileObj as File));
        }
      }}
    >
      <p className="ant-upload-drag-icon"><InboxOutlined /></p>
      <p>点击或拖拽上传 PDF / Markdown 文档</p>
    </Upload.Dragger>
  );
}
```

`frontend/src/components/DocumentTable.tsx`:

```tsx
import { Table, Button, Modal, Tag } from "antd";

export interface DocumentRow {
  id: string;
  title: string;
  source_type: string;
  status: string;
  chunk_count?: number;
  created_at: string;
}

const statusColor: Record<string, string> = { ready: "green", processing: "blue", failed: "red" };

export default function DocumentTable({ data, onDelete }: {
  data: DocumentRow[];
  onDelete: (id: string) => void;
}) {
  const columns = [
    { title: "标题", dataIndex: "title" },
    { title: "类型", dataIndex: "source_type", render: (v: string) => v === "pdf" ? "PDF" : "Markdown" },
    { title: "状态", dataIndex: "status",
      render: (v: string) => <Tag color={statusColor[v] ?? "default"}>{v}</Tag> },
    { title: "切片数", dataIndex: "chunk_count" },
    { title: "创建时间", dataIndex: "created_at", render: (v: string) => v?.slice(0, 19).replace("T", " ") },
    { title: "操作", key: "op",
      render: (_: unknown, row: DocumentRow) => (
        <Button danger size="small" onClick={() => {
          Modal.confirm({
            title: "删除文档",
            content: `确定删除「${row.title}」吗?相关切片与向量将一并清理。`,
            onOk: () => onDelete(row.id),
          });
        }}>删除</Button>
      ) },
  ];
  return <Table rowKey="id" dataSource={data} columns={columns} pagination={false} />;
}
```

`frontend/src/pages/DocumentsPage.tsx`(实现要点):

```tsx
import { message as antMessage } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import UploadDropzone from "../components/UploadDropzone";
import DocumentTable, { DocumentRow } from "../components/DocumentTable";
import { listDocuments, uploadDocuments, deleteDocument } from "../api/client";

export default function DocumentsPage() {
  const qc = useQueryClient();
  const docsQuery = useQuery({ queryKey: ["documents"], queryFn: listDocuments });
  const upload = useMutation({
    mutationFn: uploadDocuments,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["documents"] }); antMessage.success("上传完成"); },
    onError: (e: Error) => antMessage.error(e.message),
  });
  const del = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["documents"] }); antMessage.success("已删除"); },
  });
  return (
    <div style={{ maxWidth: 960, margin: "0 auto" }}>
      <UploadDropzone onUpload={(files) => upload.mutate(files)} />
      <div style={{ marginTop: 16 }}>
        <DocumentTable data={docsQuery.data ?? []} onDelete={(id) => del.mutate(id)} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run && npm run build`
Expected: PASS。

> 说明:`UploadDropzone.test.tsx` 需要 jsdom 环境;将 `vite.config.ts` 的 `test.environment` 改为 `"jsdom"`(或按测试文件用 `// @vitest-environment jsdom`)。

- [ ] **Step 5: Commit**

```bash
git add frontend/src frontend/vite.config.ts
git commit -m "feat: document management page"
```
---

## Task 15: 样例数据与种子脚本

**Files:**
- Create: `sample_data/`(6 份 MD + 2 份 PDF)
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/seed_sample.py`
- Create: `backend/scripts/make_sample_pdfs.py`
- Test: `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: `ingest_bytes()`(Task 6)
- Produces: `python -m scripts.seed_sample` 把 `sample_data/` 全部导入知识库

- [ ] **Step 1: 写样例文档(MD 内容要求)**

- `sample_data/员工手册.md`:入职流程、试用期考核(覆盖演示问题"新员工入职当天要签哪些文件")。
- `sample_data/报销制度.md`:差旅费报销所需材料与审批流程(覆盖"报销差旅费需要哪些材料"、"审批流程")。
- `sample_data/考勤制度.md`:上下班时间、请假流程。
- `sample_data/信息安全规范.md`:密码策略、数据分级。
- `sample_data/招聘流程.md`:面试轮次、offer 流程。
- `sample_data/绩效考核.md`:考核周期与等级。
- 每份 MD 使用 `#`/`##` 标题结构,正文 800–1500 字,含可检索的明确事实句(如"报销需提供发票、行程单、审批单")。

- [ ] **Step 2: 写 PDF 生成脚本与两份 PDF**

```python
# backend/scripts/make_sample_pdfs.py
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


def _register_font():
    for path in FONT_CANDIDATES:
        p = Path(path)
        if p.exists():
            pdfmetrics.registerFont(TTFont("CN", str(p)))
            return "CN"
    raise RuntimeError("未找到支持中文的 TTF 字体")


def _make_pdf(path: Path, title: str, lines: list[str]) -> None:
    font = _register_font()
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont(font, 14)
    c.drawString(72, 800, title)
    c.setFont(font, 11)
    y = 770
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
        if y < 60:
            c.showPage()
            c.setFont(font, 11)
            y = 800
    c.save()


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    _make_pdf(SAMPLE_DIR / "差旅管理规定.pdf", "差旅管理规定",
              ["1. 出差前需在系统提交出差申请并获得审批。",
               "2. 住宿标准:一线城市每晚不超过 500 元,其他城市不超过 350 元。",
               "3. 市内交通按实报销,需保留票据。",
               "4. 出差补贴:每人每天 100 元。"])
    _make_pdf(SAMPLE_DIR / "办公用品领用指南.pdf", "办公用品领用指南",
              ["1. 领用办公用品需填写领用单并经过部门负责人审批。",
               "2. 常用耗材(笔、纸)每月领用上限为 2 次。",
               "3. 单价超过 200 元的物品需行政部备案。",
               "4. 离职时需归还登记在个人名下的设备。"])


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 写种子脚本**

```python
# backend/scripts/seed_sample.py
import sys
from pathlib import Path
from app.core.db import SessionLocal, init_db
from app.core.milvus import get_milvus_client
from app.services import ingestion

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"


def main() -> None:
    init_db()
    get_milvus_client().ensure_collection()
    db = SessionLocal()
    try:
        for path in sorted(SAMPLE_DIR.iterdir()):
            if path.suffix.lower() == ".pdf":
                st = "pdf"
            elif path.suffix.lower() in (".md", ".markdown"):
                st = "markdown"
            else:
                continue
            doc = ingestion.ingest_bytes(db, path.name, path.read_bytes(), st)
            print(f"{doc.title}: {doc.status}")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 写测试并验收**

```python
# backend/tests/test_seed.py
from pathlib import Path

def test_sample_data_exists():
    root = Path(__file__).resolve().parents[2]
    files = list((root / "sample_data").glob("*"))
    md = [f for f in files if f.suffix in (".md", ".markdown")]
    pdf = [f for f in files if f.suffix == ".pdf"]
    assert len(md) >= 6
    assert len(pdf) >= 2
```

Run: `cd backend && python -m scripts.make_sample_pdfs && python -m pytest tests/test_seed.py -v`
Expected: PASS(样例文件齐全)。

- [ ] **Step 5: Commit**

```bash
git add sample_data backend/scripts backend/tests/test_seed.py
git commit -m "feat: sample enterprise documents and seed script"
```

---

## Task 16: RAGAS 评估

**Files:**
- Create: `eval_dataset.json`(12 条)
- Create: `backend/scripts/eval_ragas.py`
- Test: `backend/tests/test_eval.py`

**Interfaces:**
- Consumes: `run_agent()`(Task 9)
- Produces: `python -m scripts.eval_ragas` 输出 `eval_report.json`(faithfulness / answer_relevancy / context_precision 平均分)
- 注:spec §9 的 `/eval/run` API 本期由脚本替代(spec §12 允许 JSON 落盘简化),不单独实现。

- [ ] **Step 1: 写数据集(完整 12 条)**

`eval_dataset.json` 结构(每条):`{"question": "...", "reference": "...", "contexts": ["报销制度.md"]}`。覆盖四类:
- 单文档事实查询 ×4(如"报销差旅费需要哪些材料?")
- 跨文档多跳 ×3(如"新员工入职当天要签哪些文件?和试用期考核有什么关系?")
- 统计/工具 ×3(如"知识库里一共有几份制度文档?")
- 拒答 ×2(如"今天天气怎么样?")
`contexts` 填对应 sample_data 文件名;统计/拒答类填 `[]`。

- [ ] **Step 2: 写评估脚本**

```python
# backend/scripts/eval_ragas.py
import json
import sys
from pathlib import Path
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from app.agent.graph import run_agent
from app.agent.state import AgentState

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    with open(ROOT / "eval_dataset.json", encoding="utf-8") as f:
        items = json.load(f)
    rows = []
    for it in items:
        state: AgentState = {"query": it["question"], "history": [], "verify_count": 0, "trace": []}
        result = run_agent(state)
        rows.append({
            "question": it["question"],
            "answer": result.get("answer", ""),
            "contexts": [c.get("content", "") for c in result.get("citations", [])],
            "ground_truth": it["reference"],
        })
    ds = Dataset.from_list(rows)
    report = evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision])
    out = ROOT / "eval_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"report written to {out}")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 写 schema 测试**

```python
# backend/tests/test_eval.py
import json
from pathlib import Path

def test_eval_dataset_schema():
    root = Path(__file__).resolve().parents[2]
    with open(root / "eval_dataset.json", encoding="utf-8") as f:
        items = json.load(f)
    assert 10 <= len(items) <= 15
    for it in items:
        assert {"question", "reference", "contexts"} <= set(it)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_eval.py -v`
Expected: PASS。评估全量运行需配置好 API Key 后人工执行(README 说明)。

- [ ] **Step 5: Commit**

```bash
git add eval_dataset.json backend/scripts/eval_ragas.py backend/tests/test_eval.py
git commit -m "feat: ragas evaluation script and dataset"
```

---

## Task 17: README 与演示文档打磨

**Files:**
- Modify: `README.md`(补全)
- Modify: `.env.example`(确认与 spec §13.1 完全一致)

**Interfaces:**
- Consumes: 全部任务产物
- Produces: 可交付文档(求职展示入口)

- [ ] **Step 1: 写 README 内容**

按 spec §18 组织,包含:
- 项目简介与技术亮点(混合检索、LangGraph Agent 编排、引用溯源、RAGAS 评估、Docker 全家桶)。
- 快速开始: `cp .env.example .env` 填 Key → `docker compose up --build` → 打开 `http://localhost:5173` → `docker compose exec api python -m scripts.seed_sample` 导入样例。
- 演示提问清单(spec §18 的 5 类问题)。
- 环境变量表(.env.example 逐项说明,注明哪些必填)。
- RAGAS 评估运行方法(`docker compose exec api python -m scripts.eval_ragas`)。
- 目录结构(spec §16)。
- 常见问题:Embedding 维度不匹配、Milvus 首次启动慢、中文 PDF 字体、RERANK 可选依赖。

- [ ] **Step 2: 校验 .env.example 与 config.py 字段对应**

Run: `cd backend && python -c "from app.config import get_settings; s=get_settings(); print(s.embedding_dim)"`
Expected: 输出 `1024`。

- [ ] **Step 3: 全量测试**

Run: `cd backend && python -m pytest -q && cd ../frontend && npx vitest run`
Expected: 全部 PASS。

- [ ] **Step 4: Commit**

```bash
git add README.md .env.example
git commit -m "docs: finalize readme and env example"
```

---

## 验收清单(对照 spec)

- [ ] `docker compose up --build` 一键启动,`/api/v1/health` 返回 ok(spec §13.2)。
- [ ] 上传 8 份样例 → 全部 `ready`,Milvus 有向量,文档页可管理(spec §10/§11)。
- [ ] 演示提问 5 类全部正确回答且带引用(spec §18)。
- [ ] Milvus 停掉后混合检索降级 FTS 仍可回答(spec §7.5)。
- [ ] Trace 面板展示 rewrite/router/retrieve/generate 步骤(spec §8/§11)。
- [ ] `eval_ragas.py` 产出报告(spec §12)。
- [ ] `.env.example` 无任何真实密钥(spec §13.1)。
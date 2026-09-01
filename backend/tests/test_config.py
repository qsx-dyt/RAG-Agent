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

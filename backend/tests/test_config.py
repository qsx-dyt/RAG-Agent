from app.config import get_settings, Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "rag_test")
    s = get_settings()
    assert s.postgres_db == "rag_test"


def test_defaults_when_env_missing(monkeypatch):
    # 临时禁用 .env 文件读取,验证代码内置默认值(不受项目根 .env 影响)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    s = Settings()
    assert s.rerank_enabled is False
    assert s.embedding_dim == 1024
    assert s.chunk_size == 500

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.milvus import _client_override


def test_upload_markdown(tmp_path):
    fake_milvus = MagicMock()
    with _client_override(fake_milvus), \
         patch("app.services.ingestion.embed_texts", return_value=[[0.1] * 1024]):
        app = create_app()
        with TestClient(app) as client:
            f = tmp_path / "a.md"
            f.write_text("# 制度\n内容", encoding="utf-8")
            resp = client.post("/api/v1/documents/upload",
                               files={"files": ("a.md", f.read_bytes(), "text/markdown")})
            assert resp.status_code == 200
            body = resp.json()
            assert body[0]["status"] == "ready"


def test_upload_rejects_unsupported_type(tmp_path):
    fake_milvus = MagicMock()
    with _client_override(fake_milvus):
        app = create_app()
        with TestClient(app) as client:
            f = tmp_path / "a.txt"
            f.write_text("hello", encoding="utf-8")
            resp = client.post("/api/v1/documents/upload",
                               files={"files": ("a.txt", f.read_bytes(), "text/plain")})
            assert resp.status_code == 200
            assert resp.json()[0]["status"] == "failed"

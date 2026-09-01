from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.milvus import _client_override


def test_create_conversation():
    with _client_override(MagicMock()):
        app = create_app()
        with TestClient(app) as client:
            resp = client.post("/api/v1/conversations", json={"title": "测试会话"})
            assert resp.status_code == 200
            assert resp.json()["title"] == "测试会话"


def test_chat_streams_events():
    fake_state = {"answer": "答案是X", "citations": [], "trace": [{"step": "rewrite", "summary": "s", "duration_ms": 1}]}
    with _client_override(MagicMock()), \
         patch("app.services.chat_service.run_agent_for", return_value=fake_state):
        app = create_app()
        with TestClient(app) as client:
            with client.stream("POST", "/api/v1/chat", json={"conversation_id": None, "message": "你好"}) as r:
                body = r.read().decode()
                assert "event: start" in body
                assert "event: agent_trace" in body
                assert "event: done" in body

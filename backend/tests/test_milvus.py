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
    entity_data = {"id": "c1", "document_id": "d1", "content": "x"}
    fake_hit.entity.get = entity_data.get
    fake_hit.distance = 0.9
    with patch.object(MilvusClient, "_raw_search", return_value=[[fake_hit]]):
        client = MilvusClient(host="h", port=19530, dim=1024)
        hits = client.search([0.1] * 1024, top_k=3)
        assert hits[0]["id"] == "c1"
        assert hits[0]["score"] == 0.9

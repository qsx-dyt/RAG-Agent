from contextlib import contextmanager
from typing import Any
from pymilvus import MilvusClient as PyMilvusClient, DataType


class MilvusClient:
    COLLECTION = "chunk_embeddings"

    def __init__(self, host: str, port: int, dim: int):
        self.uri = f"http://{host}:{port}"
        self.dim = dim
        self._client = None

    def _get_client(self) -> PyMilvusClient:
        if self._client is None:
            self._client = PyMilvusClient(uri=self.uri)
        return self._client

    def _collection_exists(self) -> bool:
        return self._get_client().has_collection(self.COLLECTION)

    def _create_collection(self) -> None:
        client = self._get_client()
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, max_length=64, is_primary=True)
        schema.add_field("document_id", DataType.VARCHAR, max_length=64)
        schema.add_field("tenant_id", DataType.VARCHAR, max_length=64)
        schema.add_field("content", DataType.VARCHAR, max_length=8192)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.dim)
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding", index_type="HNSW", metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        index_params.add_index(field_name="document_id", index_type="Trie")
        client.create_collection(self.COLLECTION, schema=schema, index_params=index_params)

    def ensure_collection(self) -> None:
        if not self._collection_exists():
            self._create_collection()

    def upsert_chunks(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            self._get_client().upsert(collection_name=self.COLLECTION, data=rows)

    def search(self, query_embedding: list[float], top_k: int, expr: str | None = None) -> list[dict[str, Any]]:
        res = self._raw_search(query_embedding, top_k, expr)
        out = []
        for hit in res[0]:
            out.append({"chunk_id": hit.entity.get("id"), "document_id": hit.entity.get("document_id"),
                        "content": hit.entity.get("content"), "score": hit.distance})
        return out

    def _raw_search(self, query_embedding, top_k, expr):
        return self._get_client().search(
            collection_name=self.COLLECTION, data=[query_embedding], limit=top_k,
            output_fields=["id", "document_id", "content"], filter=expr,
        )

    def delete_by_document(self, document_ids: list[str]) -> None:
        if not document_ids:
            return
        ids = ",".join(f'"{i}"' for i in document_ids)
        self._get_client().delete(collection_name=self.COLLECTION, filter=f"document_id in [{ids}]")


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


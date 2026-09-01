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
    try:
        hits = [{"chunk_id": "a", "score": 0.1}, {"chunk_id": "b", "score": 0.2}]
        out = rerank("q", hits, top_k=2)
        assert out[0]["chunk_id"] == "a"
    finally:
        mod._reranker = None


def test_rerank_enabled_fallback_on_error(monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "true")
    import app.services.rerank as mod
    mod._reranker = None  # _default_reranker will fail (FlagEmbedding not installed)
    hits = [{"chunk_id": "a"}, {"chunk_id": "b"}]
    out = rerank("q", hits, top_k=2)
    assert [h["chunk_id"] for h in out] == ["a", "b"]

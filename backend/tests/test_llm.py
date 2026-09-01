from unittest.mock import patch
from app.core.llm import embed_texts


class _FakeEmbeddings:
    def embed_documents(self, texts):
        return [[0.1] * 4 for _ in texts]


def test_embed_texts_batches():
    with patch("app.core.llm.get_embeddings", return_value=_FakeEmbeddings()):
        out = embed_texts(["a"] * 17, batch_size=16)
        assert len(out) == 17
        assert len(out[0]) == 4


def test_embed_texts_calls_batching():
    # 17 items with batch_size=16 should call embed_documents twice
    calls = []
    seen = []
    fake = object()

    class _Spy:
        def embed_documents(self, texts):
            calls.append(len(texts))
            seen.extend(texts)
            return [[0.1] * 4 for _ in texts]

    with patch("app.core.llm.get_embeddings", return_value=_Spy()):
        embed_texts(["t"] * 17, batch_size=16)
    assert calls == [16, 1]

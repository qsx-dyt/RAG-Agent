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


def test_rrf_fuse_marks_sources():
    vec = [{"chunk_id": "a"}]
    kw = [{"chunk_id": "a"}]
    fused = rrf_fuse(vec, kw, k=60)
    assert fused[0]["sources"] == ["keyword", "vector"]

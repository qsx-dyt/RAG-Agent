import json
from pathlib import Path


def test_eval_dataset_schema():
    root = Path(__file__).resolve().parents[2]
    with open(root / "eval_dataset.json", encoding="utf-8") as f:
        items = json.load(f)
    assert 10 <= len(items) <= 15
    for it in items:
        assert {"question", "reference", "contexts"} <= set(it)

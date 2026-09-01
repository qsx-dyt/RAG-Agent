import json
import sys
from pathlib import Path
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from app.agent.graph import run_agent
from app.agent.state import AgentState

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    with open(ROOT / "eval_dataset.json", encoding="utf-8") as f:
        items = json.load(f)
    rows = []
    for it in items:
        state: AgentState = {"query": it["question"], "history": [], "verify_count": 0, "trace": []}
        result = run_agent(state)
        rows.append({
            "question": it["question"],
            "answer": result.get("answer", ""),
            "contexts": [c.get("content", "") for c in result.get("citations", [])],
            "ground_truth": it["reference"],
        })
    ds = Dataset.from_list(rows)
    report = evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision])
    out = ROOT / "eval_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"report written to {out}")


if __name__ == "__main__":
    sys.exit(main())

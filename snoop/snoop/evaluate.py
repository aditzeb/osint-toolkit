"""Run the small bundled synthetic identity-link evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from snoop.evidence import CONFIRMED, PROBABLE, UNRELATED, assess
from snoop.model import ensure_account


def run_evaluation(path: Path | None = None) -> dict:
    source = path or (Path(__file__).parent / "data" / "identity_eval.json")
    fixture = json.loads(source.read_text("utf-8"))
    rows = []
    tp = fp = resolved = 0
    for case in fixture["cases"]:
        hits = case["hits"]
        used = set()
        for hit in hits:
            ensure_account(hit, used)
            used.add(hit["ref"])
        verdicts = [
            x.verdict
            for x in assess(hits, target=case["target"], kind="name", context=case.get("context"))
        ]
        predicted = (
            "linked"
            if any(v in {CONFIRMED, PROBABLE} for v in verdicts)
            else ("unrelated" if all(v == UNRELATED for v in verdicts) else "unresolved")
        )
        expected = case["label"]
        tp += predicted == expected == "linked"
        fp += predicted == "linked" and expected != "linked"
        resolved += predicted != "unresolved"
        rows.append(
            {"id": case["id"], "expected": expected, "predicted": predicted, "verdicts": verdicts}
        )
    positives = sum(row["expected"] == "linked" for row in rows)
    return {
        "fixture": "synthetic",
        "cases": len(rows),
        "precision": tp / (tp + fp) if tp + fp else None,
        "linked_coverage": tp / positives if positives else None,
        "resolved_coverage": resolved / len(rows),
        "unresolved": sum(row["predicted"] == "unresolved" for row in rows),
        "results": rows,
        "limitation": "This tiny synthetic set tests regressions; it does not establish real-world accuracy.",
    }

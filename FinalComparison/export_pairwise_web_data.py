"""Export pairwise comparison scores as a browser-ready JavaScript dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from run_final_comparison_uq import OFFICE_SYSTEM_LABELS, RESIDENTIAL_SYSTEM_LABELS


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "plots" / "pairwise_comparison_uq.xlsx"
DEFAULT_OUTPUT = REPO_ROOT / "FinalComparison" / "pairwise_weighting_web" / "data.js"


def short_label(case: str, system: str) -> str:
    labels = RESIDENTIAL_SYSTEM_LABELS if case.lower() == "residential" else OFFICE_SYSTEM_LABELS
    return labels.get(system, system).replace("\n", " | ")


def build_payload(scores: pd.DataFrame) -> dict:
    records = []
    for row in scores.itertuples(index=False):
        records.append({
            "case": row.case,
            "span": float(row.span_l_m),
            "scenario": row.scenario,
            "metric": row.metric,
            "system": row.system,
            "systemId": row.system_id,
            "label": short_label(str(row.case), str(row.system)),
            "score": round(float(row.pairwise_score_normalized), 8),
        })
    return {
        "version": 1,
        "source": "pairwise_comparison_uq.xlsx / aggregate_scores",
        "criteria": ["GWP", "height", "mass", "cost", "time"],
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    scores = pd.read_excel(args.input, sheet_name="aggregate_scores")
    payload = build_payload(scores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "window.PAIRWISE_DATA = " + json.dumps(payload, ensure_ascii=True) + ";\n",
        encoding="utf-8",
    )
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()

"""
Consistency testing. Runs ONE representative resume/JD pair through
evaluate_semantic_match N times and reports min/max/avg/stdev of overall_score
and each category score. Uses a "good" (nuanced, judgment-call-heavy) pair by
default, since a clean-cut excellent/very-poor pair is less likely to expose
variance than one requiring real partial-credit judgment.

Usage:
    python -m tests.benchmark.consistency
    python -m tests.benchmark.consistency --pair-id good_09_cloud --runs 5

Makes real GLM API calls (N of them) -- not collected by a plain `pytest` run
(no test_*.py name, no test_* functions), same rationale as runner.py.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from tests.benchmark.dataset import BENCHMARK  # noqa: E402
from semantic_matching.evaluate_semantic_match import evaluate_semantic_match  # noqa: E402

DEFAULT_TARGET_ID = "good_06_genai"
DEFAULT_N_RUNS = 10
DEFAULT_RESULTS_PATH = Path(__file__).parent / "output" / "consistency_results.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-id", default=DEFAULT_TARGET_ID)
    parser.add_argument("--runs", type=int, default=DEFAULT_N_RUNS)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS_PATH)
    args = parser.parse_args()

    pair = next(p for p in BENCHMARK if p["id"] == args.pair_id)
    runs = []

    for i in range(1, args.runs + 1):
        print(f"Run {i}/{args.runs}...", flush=True)
        t0 = time.monotonic()
        result = evaluate_semantic_match(pair["resume"], pair["jd"])
        elapsed = time.monotonic() - t0
        run_data = {
            "run": i,
            "overall_score": result.overall_score,
            "category_scores": result.category_scores,
            "missing_skills": result.missing_skills,
            "elapsed_seconds": round(elapsed, 2),
        }
        runs.append(run_data)
        print(f"  overall_score={result.overall_score} categories={result.category_scores}", flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"target_id": args.pair_id, "runs": runs}, indent=2))

    scores = [r["overall_score"] for r in runs]
    print("\n--- SUMMARY ---")
    print("scores:", scores)
    print("min:", min(scores), "max:", max(scores), "avg:", round(statistics.mean(scores), 2))
    print("stdev:", round(statistics.stdev(scores), 2) if len(scores) > 1 else 0)

    # Also aggregate per-category consistency
    all_categories = set()
    for r in runs:
        all_categories.update(r["category_scores"].keys())
    print("\nPer-category spread (category may not appear in every run if the model chose different category names):")
    for cat in sorted(all_categories):
        vals = [r["category_scores"][cat] for r in runs if cat in r["category_scores"]]
        if len(vals) >= 2:
            print(f"  {cat}: n={len(vals)} min={min(vals)} max={max(vals)} avg={round(statistics.mean(vals),1)} stdev={round(statistics.stdev(vals),2)}")
        else:
            print(f"  {cat}: n={len(vals)} (appeared in only {len(vals)} run(s), not enough for stdev)")


if __name__ == "__main__":
    main()

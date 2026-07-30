"""
Analysis over a results.json produced by runner.py. Prints a comparison
table, accuracy stats, calibration-band stats, deterministic-vs-semantic
comparison, recruiter_intelligence pipeline stats, and performance metrics.
Emits everything as both a printed report and a JSON summary file.

The JSON summary's recruiter_mean_abs_error / recruiter_pass_rate fields are
exactly what check_regression.py compares against a stored baseline (see the
approved "One Recruiter Match Score" plan, section 8.6) -- keep their keys
stable if this file changes.

Usage:
    python -m tests.benchmark.analyze
    python -m tests.benchmark.analyze --results tests/benchmark/output/results_v2.json \\
        --summary tests/benchmark/output/analysis_summary_v2.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

DEFAULT_RESULTS_PATH = Path(__file__).parent / "output" / "results.json"
DEFAULT_SUMMARY_PATH = Path(__file__).parent / "output" / "analysis_summary.json"

BAND_ORDER = ["excellent", "good", "moderate", "weak", "very_poor"]


def midpoint(lo, hi):
    return (lo + hi) / 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    args = parser.parse_args()

    results = json.loads(args.results.read_text())
    rows = []

    for pair_id, entry in results.items():
        sem = entry.get("semantic", {})
        det = entry.get("deterministic")
        if not sem.get("success"):
            rows.append({
                "id": pair_id, "band": entry["band"], "domain": entry["domain"],
                "expected_min": entry["expected_min"], "expected_max": entry["expected_max"],
                "expected_mid": midpoint(entry["expected_min"], entry["expected_max"]),
                "actual": None, "deterministic": det["score"] if det else None,
                "diff": None, "pass": False, "error": sem.get("error"),
                "attempts": sem.get("attempts"), "elapsed": sem.get("total_elapsed_seconds"),
            })
            continue

        actual = sem["result"]["overall_score"]
        expected_mid = midpoint(entry["expected_min"], entry["expected_max"])
        diff = actual - expected_mid
        in_range = entry["expected_min"] <= actual <= entry["expected_max"]
        rows.append({
            "id": pair_id, "band": entry["band"], "domain": entry["domain"],
            "expected_min": entry["expected_min"], "expected_max": entry["expected_max"],
            "expected_mid": expected_mid,
            "actual": actual, "deterministic": det["score"] if det else None,
            "diff": round(diff, 1), "pass": in_range, "error": None,
            "attempts": sem.get("attempts"), "elapsed": sem.get("total_elapsed_seconds"),
            "category_scores": sem["result"]["category_scores"],
            "missing_skills": sem["result"]["missing_skills"],
            "reasoning": sem["result"]["reasoning"],
        })

    rows.sort(key=lambda r: (BAND_ORDER.index(r["band"]), r["id"]))

    # ---- Comparison table ----
    print("=" * 100)
    print(f"{'ID':<28} {'Band':<11} {'Expected':<10} {'Actual':<8} {'Det.':<6} {'Diff':<7} {'Pass':<5}")
    print("=" * 100)
    n_pass = 0
    n_total = 0
    for r in rows:
        n_total += 1
        expected_str = f"{r['expected_min']}-{r['expected_max']}"
        if r["actual"] is None:
            print(f"{r['id']:<28} {r['band']:<11} {expected_str:<10} {'ERROR':<8} {'-':<6} {'-':<7} {'FAIL':<5}  ({r['error']})")
            continue
        if r["pass"]:
            n_pass += 1
        print(f"{r['id']:<28} {r['band']:<11} {expected_str:<10} {r['actual']:<8} "
              f"{r['deterministic']:<6} {r['diff']:<7} {'PASS' if r['pass'] else 'FAIL':<5}")
    print("=" * 100)
    print(f"Overall: {n_pass}/{n_total} within expected range "
          f"({round(100*n_pass/n_total, 1)}%)")

    # ---- Per-band accuracy ----
    print("\n--- Per-band accuracy ---")
    band_stats = {}
    for band in BAND_ORDER:
        band_rows = [r for r in rows if r["band"] == band and r["actual"] is not None]
        if not band_rows:
            continue
        diffs = [r["diff"] for r in band_rows]
        actuals = [r["actual"] for r in band_rows]
        passes = sum(1 for r in band_rows if r["pass"])
        band_stats[band] = {
            "n": len(band_rows), "passes": passes,
            "actual_min": min(actuals), "actual_max": max(actuals),
            "actual_avg": round(statistics.mean(actuals), 1),
            "mean_diff": round(statistics.mean(diffs), 1),
            "mean_abs_diff": round(statistics.mean([abs(d) for d in diffs]), 1),
        }
        print(f"{band:<12} n={len(band_rows)} pass={passes}/{len(band_rows)} "
              f"actual_range=[{min(actuals)}-{max(actuals)}] avg={round(statistics.mean(actuals),1)} "
              f"mean_diff={round(statistics.mean(diffs),1)} mean_abs_diff={round(statistics.mean([abs(d) for d in diffs]),1)}")

    # ---- Deterministic vs semantic ----
    print("\n--- Deterministic vs Semantic vs Expected ---")
    det_diffs = []
    sem_diffs = []
    det_vs_sem_gap = []
    for r in rows:
        if r["actual"] is None or r["deterministic"] is None:
            continue
        det_diffs.append(abs(r["deterministic"] - r["expected_mid"]))
        sem_diffs.append(abs(r["actual"] - r["expected_mid"]))
        det_vs_sem_gap.append(r["actual"] - r["deterministic"])
    if det_diffs:
        print(f"Deterministic mean abs error vs expected: {round(statistics.mean(det_diffs), 1)}")
        print(f"Semantic mean abs error vs expected:      {round(statistics.mean(sem_diffs), 1)}")
        print(f"Mean (semantic - deterministic) gap:      {round(statistics.mean(det_vs_sem_gap), 1)}")

    # ---- Recruiter Match Score (the current live scoring system) ----
    print("\n--- Recruiter Match Score ---")
    recruiter_rows = []
    for pair_id, entry in results.items():
        rec = entry.get("recruiter", {})
        expected_mid = midpoint(entry["expected_min"], entry["expected_max"])
        if not rec.get("success"):
            recruiter_rows.append({
                "id": pair_id, "band": entry["band"], "actual": None,
                "diff": None, "pass": False, "error": rec.get("error"),
            })
            continue
        actual = rec["result"]["recruiter_match_score"]
        diff = actual - expected_mid
        in_range = entry["expected_min"] <= actual <= entry["expected_max"]
        recruiter_rows.append({
            "id": pair_id, "band": entry["band"], "actual": actual,
            "diff": round(diff, 1), "pass": in_range, "error": None,
        })

    recruiter_diffs = [abs(r["diff"]) for r in recruiter_rows if r["diff"] is not None]
    recruiter_passes = sum(1 for r in recruiter_rows if r["pass"])
    recruiter_n = len(recruiter_rows)
    recruiter_mean_abs_error = round(statistics.mean(recruiter_diffs), 1) if recruiter_diffs else None
    recruiter_pass_rate = round(100 * recruiter_passes / recruiter_n, 1) if recruiter_n else None
    if recruiter_n:
        print(f"Recruiter Match Score: {recruiter_passes}/{recruiter_n} within expected range "
              f"({recruiter_pass_rate}%)")
    if recruiter_diffs:
        print(f"Recruiter Match Score mean abs error vs expected: {recruiter_mean_abs_error}")
    recruiter_failures = [r for r in recruiter_rows if r["error"]]
    if recruiter_failures:
        print(f"Recruiter pipeline failures: {len(recruiter_failures)}/{recruiter_n}")
        for r in recruiter_failures:
            print(f"  {r['id']}: {r['error']}")

    # ---- Performance metrics ----
    print("\n--- Performance ---")
    all_http = []
    for entry in results.values():
        all_http.extend(entry.get("semantic", {}).get("http_calls", []) or [])
    elapsed_list = [c["elapsed_seconds"] for c in all_http]
    prompt_tokens = [c["usage"]["prompt_tokens"] for c in all_http if c.get("usage")]
    completion_tokens = [c["usage"]["completion_tokens"] for c in all_http if c.get("usage")]
    retries = sum(1 for entry in results.values() if entry.get("semantic", {}).get("attempts", 1) > 1)
    failures = sum(1 for entry in results.values() if not entry.get("semantic", {}).get("success"))
    print(f"Total HTTP calls: {len(all_http)}")
    if elapsed_list:
        print(f"Response time: min={min(elapsed_list):.1f}s max={max(elapsed_list):.1f}s "
              f"avg={statistics.mean(elapsed_list):.1f}s")
    if prompt_tokens:
        print(f"Prompt tokens: min={min(prompt_tokens)} max={max(prompt_tokens)} avg={round(statistics.mean(prompt_tokens))}")
    if completion_tokens:
        print(f"Completion tokens: min={min(completion_tokens)} max={max(completion_tokens)} avg={round(statistics.mean(completion_tokens))}")
    print(f"Pairs requiring a retry: {retries}/{len(results)}")
    print(f"Pairs that failed validation entirely: {failures}/{len(results)}")

    summary = {
        "rows": rows, "band_stats": band_stats,
        "overall_pass_rate": round(100 * n_pass / n_total, 1) if n_total else None,
        "det_mean_abs_error": round(statistics.mean(det_diffs), 1) if det_diffs else None,
        "sem_mean_abs_error": round(statistics.mean(sem_diffs), 1) if sem_diffs else None,
        "recruiter_rows": recruiter_rows,
        "recruiter_mean_abs_error": recruiter_mean_abs_error,
        "recruiter_pass_rate": recruiter_pass_rate,
        "http_call_count": len(all_http),
        "elapsed_stats": {
            "min": min(elapsed_list), "max": max(elapsed_list), "avg": round(statistics.mean(elapsed_list), 1),
        } if elapsed_list else None,
        "prompt_tokens_stats": {
            "min": min(prompt_tokens), "max": max(prompt_tokens), "avg": round(statistics.mean(prompt_tokens)),
        } if prompt_tokens else None,
        "completion_tokens_stats": {
            "min": min(completion_tokens), "max": max(completion_tokens), "avg": round(statistics.mean(completion_tokens)),
        } if completion_tokens else None,
        "retries": retries, "failures": failures,
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nFull summary written to {args.summary}")


if __name__ == "__main__":
    main()

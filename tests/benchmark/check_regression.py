"""
Regression gate for the Recruiter Match Score pipeline.

Compares a benchmark analysis summary (produced by analyze.py) against the
committed baseline.json and fails (non-zero exit) if recruiter_mean_abs_error
increases, or recruiter_pass_rate drops, beyond a tolerance. This is the
literal "if recruiter accuracy decreases, the change fails" gate from the
approved "One Recruiter Match Score" plan (section 8.6) -- it's what makes
the calibration loop (plan section 6) safe to repeat.

Usage:
    python -m tests.benchmark.runner --skip-semantic
    python -m tests.benchmark.analyze
    python -m tests.benchmark.check_regression

    # After deliberately accepting a calibration change (never casually):
    python -m tests.benchmark.check_regression --update-baseline

Intended to run as an opt-in CI job (real GLM calls cost money/tokens) on
changes to scoring-relevant paths: recruiter_intelligence/aggregation.py,
recruiter_intelligence/prompts/, recruiter_intelligence/config/scoring_config.yaml,
recruiter_intelligence/data/skill_ontology.yaml.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_SUMMARY_PATH = Path(__file__).parent / "output" / "analysis_summary.json"
DEFAULT_BASELINE_PATH = Path(__file__).parent / "baseline.json"

# Tolerance for how much the metrics may worsen before this counts as a
# regression. Itself a calibration-required value (plan section 8.6), not
# asserted as final here -- chosen as a small, deliberately loose band until
# a real calibration run (plan section 8) produces evidence for a tighter one.
MAX_MAE_INCREASE = 2.0
MAX_PASS_RATE_DROP = 5.0


def check_regression(current: dict, baseline: dict) -> tuple[bool, list[str]]:
    """
    Pure comparison logic, separated from CLI/file I/O so it's directly
    unit-testable. Returns (regressed, messages) -- regressed is True if
    either metric worsened beyond its tolerance.
    """
    mae_delta = current["recruiter_mean_abs_error"] - baseline["recruiter_mean_abs_error"]
    pass_rate_delta = current["recruiter_pass_rate"] - baseline["recruiter_pass_rate"]

    messages = [
        f"Baseline: MAE={baseline['recruiter_mean_abs_error']} pass_rate={baseline['recruiter_pass_rate']}%",
        f"Current:  MAE={current['recruiter_mean_abs_error']} pass_rate={current['recruiter_pass_rate']}%",
        f"Delta:    MAE={mae_delta:+.1f} pass_rate={pass_rate_delta:+.1f}pp",
    ]

    regressed = False
    if mae_delta > MAX_MAE_INCREASE:
        messages.append(f"REGRESSION: MAE increased by {mae_delta:.1f}, exceeding the {MAX_MAE_INCREASE} tolerance.")
        regressed = True
    if pass_rate_delta < -MAX_PASS_RATE_DROP:
        messages.append(
            f"REGRESSION: pass rate dropped by {abs(pass_rate_delta):.1f}pp, "
            f"exceeding the {MAX_PASS_RATE_DROP}pp tolerance."
        )
        regressed = True

    return regressed, messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument(
        "--update-baseline", action="store_true",
        help="Write the current summary's metrics as the new baseline instead "
             "of checking against it (use only after deliberately accepting a "
             "calibration change, never casually).",
    )
    args = parser.parse_args()

    if not args.summary.exists():
        print(f"No analysis summary found at {args.summary} -- run runner.py then analyze.py first.")
        return 1

    summary = json.loads(args.summary.read_text())
    current = {
        "recruiter_mean_abs_error": summary.get("recruiter_mean_abs_error"),
        "recruiter_pass_rate": summary.get("recruiter_pass_rate"),
    }

    if current["recruiter_mean_abs_error"] is None or current["recruiter_pass_rate"] is None:
        print(
            "Summary has no recruiter_mean_abs_error/recruiter_pass_rate -- "
            "did the benchmark run produce any successful recruiter pipeline results?"
        )
        return 1

    if args.update_baseline:
        args.baseline.write_text(json.dumps(current, indent=2) + "\n")
        print(f"Baseline updated at {args.baseline}: {current}")
        return 0

    if not args.baseline.exists():
        print(f"No baseline found at {args.baseline} -- run with --update-baseline once to seed it.")
        return 1

    baseline = json.loads(args.baseline.read_text())
    regressed, messages = check_regression(current, baseline)
    for message in messages:
        print(message)

    if regressed:
        print("\nFAILED: this change regresses recruiter-agreement metrics beyond tolerance.")
        return 1

    print("\nOK: no regression beyond tolerance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

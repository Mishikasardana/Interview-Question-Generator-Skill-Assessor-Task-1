"""
Instrumented benchmark runner. Exercises the REAL implementation:
  - matching_engine.run_matching                (deterministic, unmodified)
  - semantic_matching.evaluate_semantic_match    (real retry/validation logic, unmodified)
  - semantic_matching.semantic_scorer.evaluate_semantic_match_text (real GLM call, unmodified)
  - recruiter_intelligence (extract_requirements -> evaluate_hard_requirements ->
    evaluate_evidence -> aggregate), the current live scoring system -- see the
    approved "One Recruiter Match Score" plan.

matching_engine and semantic_matching stay in this runner as comparison
baselines (per that plan's risk section), even though neither is reachable
through the app/API anymore -- this is what lets Phase 7's calibration and
Phase 8's acceptance check confirm the new system is actually better before
the old ones are deleted from disk.

Instrumentation is added ONLY around httpx.post (timing + token usage capture)
and around attempt-counting for validate_with_retry -- no scoring/prompt logic
is touched or duplicated.

Writes incremental JSON checkpoints after every pair, so a crash/timeout never
loses completed work.

Usage:
    python -m tests.benchmark.runner
    python -m tests.benchmark.runner --output tests/benchmark/output/results_candidate.json
    python -m tests.benchmark.runner --prompt-file tests/benchmark/candidate_prompts/v2.txt \\
        --output tests/benchmark/output/results_v2.json

The --prompt-file option lets you A/B a candidate prompt WITHOUT ever touching
semantic_matching/prompts/semantic_match_prompt.txt on disk -- it monkeypatches
the in-memory prompt loader for the duration of this process only.

This makes real GLM API calls (one per pair, plus one retry on validation
failure) -- it is deliberately NOT collected by a plain `pytest` run (this
file has no test_*.py name, and none of its functions are named test_*), since
it is costly (network + tokens) and its "pass" criterion is a calibration
judgment call, not a fast, deterministic assertion.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

import httpx  # noqa: E402

from tests.benchmark.dataset import BENCHMARK  # noqa: E402
from jd_parsing.schema import ParsedJD  # noqa: E402
from matching_engine import run_matching  # noqa: E402
from matching_engine.exceptions import MatchingEngineError  # noqa: E402
from recruiter_intelligence import (  # noqa: E402
    RecruiterIntelligenceError,
    aggregate,
    evaluate_evidence,
    evaluate_hard_requirements,
    extract_requirements,
)
from resume_processing.schema import ParsedResume  # noqa: E402
from semantic_matching.evaluate_semantic_match import evaluate_semantic_match  # noqa: E402
from semantic_matching.exceptions import SemanticMatchingError  # noqa: E402
from semantic_matching import semantic_scorer  # noqa: E402

DEFAULT_RESULTS_PATH = Path(__file__).parent / "output" / "results.json"

# ---------------------------------------------------------------------------
# Instrumentation: wrap httpx.post to capture timing + token usage without
# touching any scoring/prompt logic. semantic_scorer.py does `import httpx`
# then calls httpx.post(...), so patching the httpx module's `post` name
# directly intercepts every real call it makes.
# ---------------------------------------------------------------------------
_call_log: list[dict] = []  # one entry per real HTTP call made during this run
_original_post = httpx.post


def _instrumented_post(url, *, headers=None, json=None, timeout=None):
    start = time.monotonic()
    response = _original_post(url, headers=headers, json=json, timeout=timeout)
    elapsed = time.monotonic() - start
    entry = {
        "elapsed_seconds": round(elapsed, 3),
        "status_code": response.status_code,
        "prompt_chars": sum(len(m["content"]) for m in json["messages"]),
        "model": json.get("model"),
    }
    try:
        data = response.json()
        entry["usage"] = data.get("usage")
        content = data["choices"][0]["message"]["content"]
        entry["response_chars"] = len(content)
    except Exception:
        entry["usage"] = None
        entry["response_chars"] = None
    _call_log.append(entry)
    return response


httpx.post = _instrumented_post
semantic_scorer.httpx.post = _instrumented_post


def run_semantic_with_instrumentation(resume_json, jd_json):
    """
    Calls the REAL evaluate_semantic_match (real retry/validation logic),
    but tracks attempt count and per-attempt raw content by wrapping the
    real evaluate_semantic_match_text with a counting shim -- no logic is
    duplicated or altered, only counted.
    """
    attempts = {"count": 0, "raw_responses": []}
    real_fn = semantic_scorer.evaluate_semantic_match_text

    def _counting_wrapper(resume_json, jd_json, *, strict=False):
        attempts["count"] += 1
        raw = real_fn(resume_json, jd_json, strict=strict)
        attempts["raw_responses"].append(raw)
        return raw

    # Patch at the point evaluate_semantic_match.py imported it from.
    # NOTE: semantic_matching/__init__.py does
    # `from semantic_matching.evaluate_semantic_match import evaluate_semantic_match`,
    # which shadows the `evaluate_semantic_match` SUBMODULE attribute on the
    # `semantic_matching` package with the identically-named FUNCTION (a
    # pre-existing, harmless pattern shared by every sibling module in this
    # repo -- see resume_processing.process_resume, jd_parsing.parse_jd,
    # etc.). `import semantic_matching.evaluate_semantic_match as x` would
    # therefore silently bind `x` to the function, not the module. Go
    # through sys.modules directly to get the real module object.
    orchestrator_module = sys.modules["semantic_matching.evaluate_semantic_match"]

    original = orchestrator_module.evaluate_semantic_match_text
    orchestrator_module.evaluate_semantic_match_text = _counting_wrapper
    calls_before = len(_call_log)
    t0 = time.monotonic()
    try:
        result = evaluate_semantic_match(resume_json, jd_json)
        total_elapsed = time.monotonic() - t0
        calls_made = _call_log[calls_before:]
        return {
            "success": True,
            "result": result.model_dump(),
            "attempts": attempts["count"],
            "raw_responses": attempts["raw_responses"],
            "total_elapsed_seconds": round(total_elapsed, 3),
            "http_calls": calls_made,
            "error": None,
        }
    except SemanticMatchingError as exc:
        total_elapsed = time.monotonic() - t0
        calls_made = _call_log[calls_before:]
        return {
            "success": False,
            "result": None,
            "attempts": attempts["count"],
            "raw_responses": attempts["raw_responses"],
            "total_elapsed_seconds": round(total_elapsed, 3),
            "http_calls": calls_made,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        orchestrator_module.evaluate_semantic_match_text = original


def run_recruiter_with_instrumentation(resume_json: dict, jd_json: dict) -> dict:
    """
    Runs the real, unmodified recruiter_intelligence pipeline (two GLM
    calls: requirement extraction, evidence evaluation) and reports the
    same shape as run_semantic_with_instrumentation for analyze.py to
    consume uniformly. http_calls/attempts come from the same global
    _call_log the semantic instrumentation already populates (both call
    through the same patched httpx.post), so this needs no separate
    counting shim.
    """
    calls_before = len(_call_log)
    t0 = time.monotonic()
    try:
        jd = ParsedJD.model_validate(jd_json)
        resume = ParsedResume.model_validate(resume_json)
        stage_a = extract_requirements(jd)
        hard_gate = evaluate_hard_requirements(jd, resume)
        stage_c = evaluate_evidence(stage_a, resume)
        result = aggregate(stage_a, stage_c, hard_gate, resume)
        total_elapsed = time.monotonic() - t0
        calls_made = _call_log[calls_before:]
        return {
            "success": True,
            "result": result.model_dump(),
            "attempts": None,  # each stage retries independently; see http_calls for the real count
            "total_elapsed_seconds": round(total_elapsed, 3),
            "http_calls": calls_made,
            "error": None,
        }
    except RecruiterIntelligenceError as exc:
        total_elapsed = time.monotonic() - t0
        calls_made = _call_log[calls_before:]
        return {
            "success": False,
            "result": None,
            "attempts": None,
            "total_elapsed_seconds": round(total_elapsed, 3),
            "http_calls": calls_made,
            "error": f"{type(exc).__name__}: {exc}",
        }


def load_existing_results(results_path: Path) -> dict:
    if results_path.exists():
        return json.loads(results_path.read_text())
    return {}


def save_results(results: dict, results_path: Path) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_RESULTS_PATH,
        help="Where to write incremental JSON results (default: output/results.json).",
    )
    parser.add_argument(
        "--prompt-file", type=Path, default=None,
        help="Optional candidate system-prompt file to A/B against the live "
             "prompt, without touching semantic_matching/prompts/ on disk. "
             "Applies to the old semantic_matching prompt only.",
    )
    parser.add_argument(
        "--skip-semantic", action="store_true",
        help="Skip the old semantic_matching comparison call -- cheaper runs "
             "when only the recruiter_intelligence pipeline is of interest "
             "(e.g. during a Phase 7 calibration sweep).",
    )
    args = parser.parse_args()

    if args.prompt_file is not None:
        candidate_text = args.prompt_file.read_text(encoding="utf-8").strip()
        semantic_scorer._load_system_prompt = lambda: candidate_text
        print(f"Using candidate prompt from {args.prompt_file} (in-memory only).", flush=True)

    results = load_existing_results(args.output)
    total = len(BENCHMARK)

    for i, pair in enumerate(BENCHMARK, start=1):
        pair_id = pair["id"]
        already_done = pair_id in results and results[pair_id].get("recruiter", {}).get("success")
        if already_done and (args.skip_semantic or results[pair_id].get("semantic", {}).get("success")):
            print(f"[{i}/{total}] {pair_id}: already done, skipping", flush=True)
            continue

        print(f"[{i}/{total}] {pair_id} ({pair['domain']}, {pair['band']})...", flush=True)

        entry = {
            "id": pair_id, "band": pair["band"], "domain": pair["domain"],
            "expected_min": pair["expected_min"], "expected_max": pair["expected_max"],
        }

        # Deterministic (instant, no network) -- kept as a comparison
        # baseline (see the approved "One Recruiter Match Score" plan's
        # risk section), even though it's no longer reachable via the app/API.
        try:
            det = run_matching(pair["resume"], pair["jd"])
            entry["deterministic"] = det.to_dict()
        except MatchingEngineError as exc:
            entry["deterministic"] = None
            entry["deterministic_error"] = str(exc)

        # Semantic (real GLM call, instrumented) -- same comparison-baseline reasoning.
        if not args.skip_semantic:
            try:
                entry["semantic"] = run_semantic_with_instrumentation(pair["resume"], pair["jd"])
            except Exception as exc:
                entry["semantic"] = {
                    "success": False, "result": None, "attempts": 0,
                    "raw_responses": [], "total_elapsed_seconds": None,
                    "http_calls": [], "error": f"UNEXPECTED {type(exc).__name__}: {exc}",
                }
                traceback.print_exc()

        # Recruiter Match pipeline (real GLM calls, instrumented) -- the
        # current live scoring system; this is what check_regression.py compares.
        try:
            entry["recruiter"] = run_recruiter_with_instrumentation(pair["resume"], pair["jd"])
        except Exception as exc:
            entry["recruiter"] = {
                "success": False, "result": None, "attempts": None,
                "total_elapsed_seconds": None, "http_calls": [],
                "error": f"UNEXPECTED {type(exc).__name__}: {exc}",
            }
            traceback.print_exc()

        results[pair_id] = entry
        save_results(results, args.output)

        rec = entry["recruiter"]
        if rec["success"]:
            print(
                f"    -> recruiter_match_score={rec['result']['recruiter_match_score']} "
                f"expected=[{pair['expected_min']}-{pair['expected_max']}] "
                f"time={rec['total_elapsed_seconds']}s",
                flush=True,
            )
        else:
            print(f"    -> RECRUITER PIPELINE FAILED: {rec['error']}", flush=True)

    print("\nAll pairs processed. Results saved to", args.output, flush=True)


if __name__ == "__main__":
    main()

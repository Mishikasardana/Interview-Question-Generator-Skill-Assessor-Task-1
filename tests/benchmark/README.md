# Matching/scoring benchmark harness

Evaluates `recruiter_intelligence` (the current live scoring system) against
recruiter-quality expectations using real GLM API calls, keeping
`matching_engine`/`semantic_matching` as comparison baselines (see the
approved "One Recruiter Match Score" plan, section 9's risk analysis — this
is what lets a calibration decision be evidence-based rather than a guess).
This is deliberately **not** part of the fast `pytest` suite for `runner.py`/
`analyze.py`/`consistency.py`/`stress.py` — every run costs real API tokens
and takes minutes, and "does the score match what an experienced recruiter
would give?" is a calibration judgment, not a fast deterministic assertion.
None of those four files are named `test_*.py`, so a plain `pytest`
invocation never collects or runs them. `check_regression.py`'s comparison
logic is pure and IS covered by `test_check_regression.py` in the fast suite;
only running it against a real benchmark result is a manual/CI step.

This harness (and the dataset it runs against) is the tool `recruiter_intelligence`
is calibrated and validated against (see `.claude/plans/` — "One Recruiter
Match Score"). Keep it working as that plan's calibration phase proceeds;
extend `dataset.py`, don't replace it, so historical comparisons stay meaningful.

## What's here

- `dataset.py` — 25 resume/JD pairs, 5 per score band (excellent/good/
  moderate/weak/very_poor), spanning 10 domains. Ground-truth `expected_min`/
  `expected_max` were written *before* any pair was run through the system,
  to avoid post-hoc rationalization. Grow this incrementally (plan section 8.1).
- `runner.py` — runs every pair through `recruiter_intelligence` (the current
  live pipeline: requirement extraction -> hard-requirement gate -> evidence
  evaluation -> deterministic aggregation), plus `matching_engine.run_matching`
  and `semantic_matching.evaluate_semantic_match` as comparison baselines,
  capturing timing/token usage transparently. `--skip-semantic` skips the
  old semantic comparison call for cheaper recruiter-only runs. `--prompt-file`
  A/Bs a candidate `semantic_matching` prompt in-memory (legacy option, kept
  for historical A/B methodology continuity).
- `analyze.py` — turns a `runner.py` results file into a comparison table,
  per-band accuracy, deterministic-vs-semantic-vs-recruiter comparison, and
  performance stats. Its `recruiter_mean_abs_error`/`recruiter_pass_rate`
  summary fields are what `check_regression.py` compares against the baseline.
- `check_regression.py` — the regression gate (plan section 8.6): fails
  (non-zero exit) if `recruiter_mean_abs_error` increases or
  `recruiter_pass_rate` drops beyond tolerance vs. `baseline.json`.
- `baseline.json` — the committed, last-accepted scoreboard. Update only via
  `--update-baseline` after deliberately accepting a calibration change, never
  casually. Currently seeded from a small (5-pair) real run — see the file's
  own note; expand as the dataset and calibration process (plan section 7-8) mature.
- `consistency.py` — runs one pair N times to measure score/category
  stability (temperature is already 0.1, but LLM output still varies).
- `stress.py` — 10 edge cases (empty resume/JD, keyword-stuffing, prompt
  injection, malformed input shapes, etc.) run through both legacy engines.
- `candidate_prompts/` — prompt variants tested via `runner.py --prompt-file`
  but not (yet) promoted to `semantic_matching/prompts/semantic_match_prompt.txt`.
- `output/` — gitignored. Every script writes its results here; nothing in
  this directory is committed, since it's regenerable and goes stale the
  moment the prompt or code changes.

## Usage

```bash
# Full 25-pair run against the live recruiter_intelligence pipeline
# (plus matching_engine/semantic_matching as comparison baselines)
python -m tests.benchmark.runner
python -m tests.benchmark.analyze

# Cheaper recruiter-only run (skips the old semantic_matching comparison call)
python -m tests.benchmark.runner --skip-semantic
python -m tests.benchmark.analyze

# Check for a regression against the committed baseline
python -m tests.benchmark.check_regression

# After deliberately accepting a calibration change (never casually):
python -m tests.benchmark.check_regression --update-baseline

# A/B a candidate semantic_matching prompt without touching the live one
# (legacy option, kept for historical A/B methodology continuity)
python -m tests.benchmark.runner --prompt-file tests/benchmark/candidate_prompts/v2_required_preferred_weighting.txt \
    --output tests/benchmark/output/results_v2.json
python -m tests.benchmark.analyze --results tests/benchmark/output/results_v2.json \
    --summary tests/benchmark/output/analysis_summary_v2.json

# Consistency (10x the same pair)
python -m tests.benchmark.consistency

# Stress / edge cases
python -m tests.benchmark.stress
```

All three runners write incrementally after every pair/case, so a crash or a
provider rate limit never loses completed work — just re-run the same command
and it picks up where it left off (`runner.py`/`stress.py` skip anything that
already *succeeded*; a previously-failed entry is retried).

## Historical findings (original `semantic_match_prompt.txt`, as committed)

A full 25-pair run against the live prompt found:

- **56% pass rate** (14/25 within expected band).
- Semantic mean abs. error **13.9**; deterministic (`matching_engine`) mean
  abs. error on the same 25 pairs: **26.7** (semantic is ~2x more accurate).
- **Root cause of "great candidate, bad score"**: `overall_score` equals a
  plain unweighted average of `category_scores` in **72%** of cases, within 3
  points in **92%**. The prompt gives no instruction on how `overall_score`
  should relate to `category_scores`, so a single weak *preferred*-tier
  category drags the average down exactly as hard as a weak *required* one.
- Band averages were monotonically ordered (ranking quality is good even
  where absolute calibration isn't).

## The `v2_required_preferred_weighting.txt` experiment

`candidate_prompts/v2_required_preferred_weighting.txt` adds an explicit
instruction that `overall_score` must weight required categories over
preferred ones, plus a new AWS/GCP-equivalence worked example. Re-run against
the identical 25 pairs:

- Mean abs. error: **13.9 → 11.7** (-16%).
- Pass rate **fell**: 56% → 48% (new overshoot in 3 cross-vendor "good"-band
  cases, plus 2 new timeouts).
- Excellent-band ceiling-clustering fixed (avg 100→95, mean abs. error 6.6→1.5).
- The target case (`moderate_11_fullstack`, a candidate strong on required
  skills but weak on one preferred category) improved 36→68, landing inside
  its expected band — exactly the bug this was designed to fix.
- Weak band did not improve.
- Cost/latency regressed (~+57% prompt tokens, ~+14% latency, 2 new timeouts).

**This was validated but never merged** into the live prompt — it fixed one
real defect (the averaging bug) while introducing a different one (LLM-judged
weighting still isn't deterministic, hence the new overshoot). The
`recruiter_intelligence` redesign supersedes this approach architecturally:
the backend computes the weighted aggregate deterministically instead of
asking the LLM to reason about required-vs-preferred weighting at all — see
the approved plan for the full rationale.

## Consistency findings (same pair, 10 runs, temperature 0.1)

- `overall_score`: min 87, max 97, avg 91.9, stdev 3.03 (within a 5-point
  tolerance).
- **Category-name instability**: 13 different category-name variants across
  10 runs for the same JD's ~4-8 underlying dimensions.
- Ambiguous "equivalent technology" categories had real score variance (one
  category stdev 12.45); unambiguous categories were rock-solid (stdev 0.0).

## Stress-test findings

- A real prompt-injection payload embedded in resume text was correctly
  ignored (scored the genuine skill only).
- 2 organic 120-second timeouts (empty resume, duplicate-skills case).
- Hit the GLM provider's account-level rate limit (HTTP 429) after 46
  consecutive calls — **no rate-limit-aware backoff exists anywhere in this
  codebase's GLM-calling modules** as of this writing; a 429 fails identically
  to any other unhandled error.
- A 20-buzzword/zero-evidence "keyword-stuffed" resume still scored 70 —
  flagged as a possible over-crediting risk worth re-checking after the
  redesign.

"""
Matching Engine Module — public package interface.

External consumers should only import from here:

    from matching_engine import run_matching, MatchResult, SkillGapEntry

Everything else is an internal implementation detail.
"""

from __future__ import annotations

from matching_engine.exceptions import MatchingEngineError
from matching_engine.matching_engine import MatchResult, SkillGapEntry, run_matching

__all__ = [
    "run_matching",
    "MatchResult",
    "SkillGapEntry",
    "MatchingEngineError",
]

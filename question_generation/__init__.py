"""
Question Generation Module — public package entry point.

Purpose:
    Expose a single public function so other modules can generate interview
    questions without knowing internal implementation details.
"""

from question_generation.generate_questions import generate_questions
from question_generation.schema import GeneratedQuestions, InterviewQuestion

__all__ = ["generate_questions", "GeneratedQuestions", "InterviewQuestion"]

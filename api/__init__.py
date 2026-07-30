"""
API layer — REST interface over the four processing modules.

This package contains no business logic of its own. Every route is a thin
wrapper that validates the HTTP request, calls into
``resume_processing`` / ``jd_parsing`` / ``matching_engine`` /
``question_generation`` / ``answer_evaluation``, and serializes the result.
"""

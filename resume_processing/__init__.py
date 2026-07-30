"""
Resume Processing Module — public package entry point.

Purpose:
    Expose a small public API so other teams can parse resumes without
    knowing internal implementation details.

Public API:
    process_resume(resume_file) -> ParsedResume
    process_resume_with_raw_text(resume_file) -> tuple[str, ParsedResume]

Supports both .pdf and .docx resume files.

Example usage:
    >>> from resume_processing import process_resume
    >>> result = process_resume("path/to/resume.pdf")
    >>> print(result.name, result.skills)
    >>> result = process_resume("path/to/resume.docx")  # also supported
"""

from resume_processing.process_resume import process_resume, process_resume_with_raw_text
from resume_processing.schema import ParsedResume

__all__ = ["process_resume", "process_resume_with_raw_text", "ParsedResume"]

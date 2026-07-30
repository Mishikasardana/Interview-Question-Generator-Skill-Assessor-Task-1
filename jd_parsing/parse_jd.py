"""
Main orchestrator — the single public entry point for JD parsing.

Purpose:
    Wire together the GLM call and output validation into one callable
    function. External consumers import only ``parse_jd``; they never touch
    ``jd_parser`` or ``output_validator`` directly.

Pipeline:
    Raw JD text
        → GLM Parser       (jd_parser)
        → Validate JSON    (output_validator)
        → Return ParsedJD

Inputs:
    ``jd_text``: Raw job description text (``str``).

Outputs:
    ``ParsedJD``: Validated, structured JD data.

Example usage:
    >>> from jd_parsing.parse_jd import parse_jd
    >>> parsed = parse_jd("We are hiring a backend engineer ...")
    >>> parsed.required_skills
"""

from __future__ import annotations

from jd_parsing.jd_parser import parse_jd_text
from jd_parsing.output_validator import validate_with_retry
from jd_parsing.schema import ParsedJD


def parse_jd(jd_text: str) -> ParsedJD:
    """
    Parse a raw job description into structured, validated JSON.

    Args:
        jd_text: Raw job description text.

    Returns:
        Validated ``ParsedJD``.

    Raises:
        JDParsingError: GLM API failure.
        JDValidationError: Schema validation failure after retry.
    """
    return validate_with_retry(lambda strict: parse_jd_text(jd_text, strict=strict))

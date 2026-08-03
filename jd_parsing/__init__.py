"""
JD Parsing Module — public package interface.

External consumers should only import from here:

    from jd_parsing import parse_jd, ParsedJD

Everything else (``jd_parser``, ``output_validator``, ``config``,
``exceptions``) is an internal implementation detail.
"""

from __future__ import annotations

from jd_parsing.exceptions import JDParsingError, JDProcessingError, JDValidationError
from jd_parsing.parse_jd import parse_jd
from jd_parsing.schema import HardRequirement, ParsedJD

__all__ = [
    "parse_jd",
    "ParsedJD",
    "HardRequirement",
    "JDProcessingError",
    "JDParsingError",
    "JDValidationError",
]

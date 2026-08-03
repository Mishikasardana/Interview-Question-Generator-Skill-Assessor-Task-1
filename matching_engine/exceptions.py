"""
Custom exceptions for the Matching Engine Module.

Purpose:
    Provide a meaningful, domain-specific error instead of a generic Python
    exception, mirroring the exception style used across the rest of the
    project so the API layer can handle every module's failures the same way.
"""


class MatchingEngineError(Exception):
    """Raised when matching engine inputs are malformed (not dicts)."""

    pass

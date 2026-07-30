"""Custom exceptions for the database layer."""


class UserAlreadyExistsError(Exception):
    """Raised on sign-up when the email is already registered."""

    pass

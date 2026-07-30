"""Tests for database.repositories — mocked SQLAlchemy sessions, no live DB."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from database.exceptions import UserAlreadyExistsError
from database.models import AuthToken, User
from database.repositories import (
    TOKEN_KIND_RESET_PASSWORD,
    TOKEN_KIND_VERIFY_EMAIL,
    authenticate_user,
    consume_email_verification_token,
    consume_password_reset_token,
    create_email_verification_token,
    create_password_reset_token,
    create_user,
    get_or_create_oauth_user,
    get_user_by_email,
    get_user_by_id,
    set_password,
    touch_last_login,
    update_user_profile,
    validate_token,
)


def _session_context(mock_session: MagicMock) -> MagicMock:
    context = MagicMock()
    context.__enter__.return_value = mock_session
    context.__exit__.return_value = None
    return context


@patch("database.repositories.get_session")
@patch("database.repositories.hash_password", return_value="hashed-secret")
def test_create_user_persists_new_account(
    _mock_hash: MagicMock, mock_get_session: MagicMock
):
    mock_session = MagicMock()
    mock_session.scalar.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    user = create_user(
        name="Jane Doe",
        email="Jane@Example.com",
        password="secure-password",
        role="student",
        phone_number="555-0100",
    )

    assert user.email == "jane@example.com"
    assert user.role == "student"
    assert user.is_verified is False
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@patch("database.repositories.get_session")
@patch("database.repositories.hash_password", return_value="hashed-secret")
def test_create_user_rejects_duplicate_email_from_concurrent_commit(
    _mock_hash: MagicMock, mock_get_session: MagicMock
):
    # Simulates a signup race: the pre-check (session.scalar) finds no
    # existing row (another concurrent request hasn't committed yet), but
    # the unique-constraint violation surfaces at commit time instead. This
    # should still raise the friendly UserAlreadyExistsError, not a raw
    # IntegrityError.
    from sqlalchemy.exc import IntegrityError

    mock_session = MagicMock()
    mock_session.scalar.return_value = None
    mock_session.commit.side_effect = IntegrityError("INSERT", {}, Exception("unique violation"))
    mock_get_session.return_value = _session_context(mock_session)

    with pytest.raises(UserAlreadyExistsError, match="already exists"):
        create_user(
            name="Jane Doe",
            email="jane@example.com",
            password="secure-password",
            role="student",
        )

    mock_session.rollback.assert_called_once()


@patch("database.repositories.get_session")
def test_create_user_rejects_duplicate_email(mock_get_session: MagicMock):
    existing = User(
        name="Existing",
        email="jane@example.com",
        password_hash="hash",
        role="student",
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = existing
    mock_get_session.return_value = _session_context(mock_session)

    with pytest.raises(UserAlreadyExistsError, match="already exists"):
        create_user(
            name="Jane Doe",
            email="jane@example.com",
            password="secure-password",
            role="student",
        )


@patch("database.repositories.verify_password", return_value=True)
@patch("database.repositories.get_session")
def test_authenticate_user_returns_user_for_valid_credentials(
    mock_get_session: MagicMock, _mock_verify: MagicMock
):
    user = User(
        name="Jane Doe",
        email="jane@example.com",
        password_hash="hash",
        role="student",
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = user
    mock_get_session.return_value = _session_context(mock_session)

    result = authenticate_user(email="jane@example.com", password="correct")

    assert result is user


@patch("database.repositories.verify_password", return_value=False)
@patch("database.repositories.get_session")
def test_authenticate_user_returns_none_for_wrong_password(
    mock_get_session: MagicMock, _mock_verify: MagicMock
):
    user = User(
        name="Jane Doe",
        email="jane@example.com",
        password_hash="hash",
        role="student",
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = user
    mock_get_session.return_value = _session_context(mock_session)

    assert authenticate_user(email="jane@example.com", password="wrong") is None


@patch("database.repositories.get_session")
def test_authenticate_user_returns_none_for_unknown_email(
    mock_get_session: MagicMock,
):
    mock_session = MagicMock()
    mock_session.scalar.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    assert authenticate_user(email="missing@example.com", password="any") is None


@patch("database.repositories.get_session")
def test_get_user_by_email_returns_matching_user(mock_get_session: MagicMock):
    user = User(name="Jane Doe", email="jane@example.com", role="student")
    mock_session = MagicMock()
    mock_session.scalar.return_value = user
    mock_get_session.return_value = _session_context(mock_session)

    assert get_user_by_email("Jane@Example.com") is user


@patch("database.repositories.get_session")
def test_get_user_by_email_returns_none_when_missing(mock_get_session: MagicMock):
    mock_session = MagicMock()
    mock_session.scalar.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    assert get_user_by_email("missing@example.com") is None


@patch("database.repositories.get_session")
def test_get_or_create_oauth_user_creates_passwordless_account(
    mock_get_session: MagicMock,
):
    mock_session = MagicMock()
    mock_session.scalar.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    user = get_or_create_oauth_user(
        email="Jane@Example.com", name="Jane Doe", role="student", google_id="sub-123",
    )

    assert user.email == "jane@example.com"
    assert user.role == "student"
    assert user.password_hash is None
    assert user.google_id == "sub-123"
    assert user.is_verified is True
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@patch("database.repositories.get_session")
def test_get_or_create_oauth_user_returns_existing_row_unchanged(
    mock_get_session: MagicMock,
):
    # An existing account (whatever its role/name) is returned as-is —
    # role-mismatch handling and name updates are the caller's job, not
    # this function's, so a returning user's row must not get overwritten.
    existing = User(
        name="Original Name", email="jane@example.com", role="recruiter",
        google_id="already-set",
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = existing
    mock_get_session.return_value = _session_context(mock_session)

    user = get_or_create_oauth_user(
        email="jane@example.com", name="New Name From Google", role="student",
        google_id="a-different-sub",
    )

    assert user is existing
    assert user.name == "Original Name"
    assert user.role == "recruiter"
    assert user.google_id == "already-set"
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@patch("database.repositories.get_session")
def test_get_or_create_oauth_user_backfills_google_id_on_existing_row(
    mock_get_session: MagicMock,
):
    # An account originally created via the old password sign-up (no
    # google_id yet) signing in with a matching Google account should get
    # google_id backfilled, without otherwise changing the row.
    existing = User(
        name="Jane Doe", email="jane@example.com", role="student", google_id=None,
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = existing
    mock_get_session.return_value = _session_context(mock_session)

    user = get_or_create_oauth_user(
        email="jane@example.com", name="Jane Doe", role="student", google_id="sub-456",
    )

    assert user is existing
    assert user.google_id == "sub-456"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@patch("database.repositories.get_session")
def test_get_or_create_oauth_user_handles_concurrent_create_race(
    mock_get_session: MagicMock,
):
    from sqlalchemy.exc import IntegrityError

    existing_after_race = User(
        name="Jane Doe", email="jane@example.com", role="student", google_id="sub-123",
    )
    mock_session = MagicMock()
    mock_session.scalar.side_effect = [None, existing_after_race]
    mock_session.commit.side_effect = IntegrityError("INSERT", {}, Exception("unique violation"))
    mock_get_session.return_value = _session_context(mock_session)

    user = get_or_create_oauth_user(
        email="jane@example.com", name="Jane Doe", role="student", google_id="sub-123",
    )

    assert user is existing_after_race
    mock_session.rollback.assert_called_once()


@patch("database.repositories.get_session")
def test_get_user_by_id_returns_none_when_missing(mock_get_session: MagicMock):
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    result = get_user_by_id(uuid.uuid4())

    assert result is None


@patch("database.repositories.get_session")
def test_get_user_by_id_returns_none_for_malformed_uuid_string(
    mock_get_session: MagicMock,
):
    # A malformed id should resolve to "not found", not a raw ValueError
    # from uuid.UUID(...) — the session should never even be touched.
    result = get_user_by_id("not-a-valid-uuid")  # type: ignore[arg-type]

    assert result is None
    mock_get_session.assert_not_called()


@patch("database.repositories.get_session")
def test_update_user_profile_returns_none_for_malformed_uuid_string(
    mock_get_session: MagicMock,
):
    result = update_user_profile(user_id="not-a-valid-uuid", name="New Name")  # type: ignore[arg-type]

    assert result is None
    mock_get_session.assert_not_called()


# ── Email verification / password reset tokens ─────────────────────────────


@patch("database.repositories.get_session")
def test_create_email_verification_token_returns_raw_token_and_stores_hash(
    mock_get_session: MagicMock,
):
    mock_session = MagicMock()
    mock_session.scalars.return_value.all.return_value = []
    mock_get_session.return_value = _session_context(mock_session)

    user_id = uuid.uuid4()
    raw_token = create_email_verification_token(user_id=user_id)

    assert isinstance(raw_token, str) and len(raw_token) > 20
    mock_session.add.assert_called_once()
    added_token = mock_session.add.call_args[0][0]
    assert isinstance(added_token, AuthToken)
    assert added_token.kind == TOKEN_KIND_VERIFY_EMAIL
    assert added_token.user_id == user_id
    assert added_token.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    mock_session.commit.assert_called_once()


@patch("database.repositories.get_session")
def test_create_email_verification_token_invalidates_previous_unused_token(
    mock_get_session: MagicMock,
):
    stale = AuthToken(
        user_id=uuid.uuid4(), token_hash="old-hash", kind=TOKEN_KIND_VERIFY_EMAIL,
        expires_at=datetime.now(UTC) + timedelta(hours=1), used_at=None,
    )
    mock_session = MagicMock()
    mock_session.scalars.return_value.all.return_value = [stale]
    mock_get_session.return_value = _session_context(mock_session)

    create_email_verification_token(user_id=uuid.uuid4())

    assert stale.used_at is not None


@patch("database.repositories.get_session")
def test_create_password_reset_token_returns_token_for_password_account(
    mock_get_session: MagicMock,
):
    user = User(name="Jane", email="jane@example.com", password_hash="hash", role="student")
    mock_session = MagicMock()
    mock_session.scalar.return_value = user
    mock_session.scalars.return_value.all.return_value = []
    mock_get_session.return_value = _session_context(mock_session)

    raw_token = create_password_reset_token(email="jane@example.com")

    assert isinstance(raw_token, str) and len(raw_token) > 20


@patch("database.repositories.get_session")
def test_create_password_reset_token_returns_none_for_unknown_email(
    mock_get_session: MagicMock,
):
    mock_session = MagicMock()
    mock_session.scalar.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    assert create_password_reset_token(email="missing@example.com") is None


@patch("database.repositories.get_session")
def test_create_password_reset_token_returns_none_for_google_only_account(
    mock_get_session: MagicMock,
):
    # Security guardrail: forgot-password must never be usable to attach a
    # first password to a passwordless (Google-only) account — otherwise
    # anyone who knows/guesses that email could hijack it.
    user = User(
        name="Jane", email="jane@example.com", password_hash=None,
        google_id="sub-123", role="student",
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = user
    mock_get_session.return_value = _session_context(mock_session)

    assert create_password_reset_token(email="jane@example.com") is None


@patch("database.repositories.get_session")
def test_validate_token_returns_user_for_valid_token(mock_get_session: MagicMock):
    user = User(name="Jane", email="jane@example.com", role="student")
    token = AuthToken(
        user_id=uuid.uuid4(), token_hash="h", kind=TOKEN_KIND_VERIFY_EMAIL,
        expires_at=datetime.now(UTC) + timedelta(hours=1), used_at=None,
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = token
    mock_session.get.return_value = user
    mock_get_session.return_value = _session_context(mock_session)

    assert validate_token(raw_token="raw", kind=TOKEN_KIND_VERIFY_EMAIL) is user


@patch("database.repositories.get_session")
def test_validate_token_returns_none_for_wrong_kind(mock_get_session: MagicMock):
    token = AuthToken(
        user_id=uuid.uuid4(), token_hash="h", kind=TOKEN_KIND_VERIFY_EMAIL,
        expires_at=datetime.now(UTC) + timedelta(hours=1), used_at=None,
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = token
    mock_get_session.return_value = _session_context(mock_session)

    assert validate_token(raw_token="raw", kind=TOKEN_KIND_RESET_PASSWORD) is None


@patch("database.repositories.get_session")
def test_validate_token_returns_none_for_expired_token(mock_get_session: MagicMock):
    token = AuthToken(
        user_id=uuid.uuid4(), token_hash="h", kind=TOKEN_KIND_VERIFY_EMAIL,
        expires_at=datetime.now(UTC) - timedelta(hours=1), used_at=None,
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = token
    mock_get_session.return_value = _session_context(mock_session)

    assert validate_token(raw_token="raw", kind=TOKEN_KIND_VERIFY_EMAIL) is None


@patch("database.repositories.get_session")
def test_validate_token_returns_none_for_already_used_token(mock_get_session: MagicMock):
    token = AuthToken(
        user_id=uuid.uuid4(), token_hash="h", kind=TOKEN_KIND_VERIFY_EMAIL,
        expires_at=datetime.now(UTC) + timedelta(hours=1), used_at=datetime.now(UTC),
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = token
    mock_get_session.return_value = _session_context(mock_session)

    assert validate_token(raw_token="raw", kind=TOKEN_KIND_VERIFY_EMAIL) is None


@patch("database.repositories.get_session")
def test_validate_token_returns_none_for_unknown_token(mock_get_session: MagicMock):
    mock_session = MagicMock()
    mock_session.scalar.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    assert validate_token(raw_token="raw", kind=TOKEN_KIND_VERIFY_EMAIL) is None


@patch("database.repositories.get_session")
def test_consume_email_verification_token_marks_used_and_verifies_user(
    mock_get_session: MagicMock,
):
    user = User(name="Jane", email="jane@example.com", role="student", is_verified=False)
    token = AuthToken(
        user_id=uuid.uuid4(), token_hash="h", kind=TOKEN_KIND_VERIFY_EMAIL,
        expires_at=datetime.now(UTC) + timedelta(hours=1), used_at=None,
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = token
    mock_session.get.return_value = user
    mock_get_session.return_value = _session_context(mock_session)

    result = consume_email_verification_token(raw_token="raw")

    assert result is user
    assert user.is_verified is True
    assert token.used_at is not None
    mock_session.commit.assert_called_once()


@patch("database.repositories.get_session")
def test_consume_email_verification_token_returns_none_for_invalid_token(
    mock_get_session: MagicMock,
):
    mock_session = MagicMock()
    mock_session.scalar.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    assert consume_email_verification_token(raw_token="raw") is None


@patch("database.repositories.get_session")
@patch("database.repositories.hash_password", return_value="new-hashed")
def test_consume_password_reset_token_sets_new_password(
    _mock_hash: MagicMock, mock_get_session: MagicMock,
):
    user = User(name="Jane", email="jane@example.com", role="student", password_hash="old-hash")
    token = AuthToken(
        user_id=uuid.uuid4(), token_hash="h", kind=TOKEN_KIND_RESET_PASSWORD,
        expires_at=datetime.now(UTC) + timedelta(hours=1), used_at=None,
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = token
    mock_session.get.return_value = user
    mock_get_session.return_value = _session_context(mock_session)

    result = consume_password_reset_token(raw_token="raw", new_password="NewPass1!")

    assert result is user
    assert user.password_hash == "new-hashed"
    assert token.used_at is not None


@patch("database.repositories.get_session")
def test_consume_password_reset_token_returns_none_for_expired_token(
    mock_get_session: MagicMock,
):
    token = AuthToken(
        user_id=uuid.uuid4(), token_hash="h", kind=TOKEN_KIND_RESET_PASSWORD,
        expires_at=datetime.now(UTC) - timedelta(hours=1), used_at=None,
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = token
    mock_get_session.return_value = _session_context(mock_session)

    assert consume_password_reset_token(raw_token="raw", new_password="NewPass1!") is None


@patch("database.repositories.get_session")
@patch("database.repositories.hash_password", return_value="hashed-new")
def test_set_password_updates_existing_user(
    _mock_hash: MagicMock, mock_get_session: MagicMock,
):
    user = User(name="Jane", email="jane@example.com", role="student", password_hash=None)
    mock_session = MagicMock()
    mock_session.get.return_value = user
    mock_get_session.return_value = _session_context(mock_session)

    result = set_password(user_id=uuid.uuid4(), password="NewPass1!")

    assert result is user
    assert user.password_hash == "hashed-new"


@patch("database.repositories.get_session")
def test_set_password_returns_none_for_malformed_uuid_string(mock_get_session: MagicMock):
    result = set_password(user_id="not-a-valid-uuid", password="NewPass1!")  # type: ignore[arg-type]

    assert result is None
    mock_get_session.assert_not_called()


@patch("database.repositories.get_session")
def test_set_password_returns_none_for_missing_user(mock_get_session: MagicMock):
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    assert set_password(user_id=uuid.uuid4(), password="NewPass1!") is None


@patch("database.repositories.get_session")
def test_touch_last_login_sets_timestamp(mock_get_session: MagicMock):
    user = User(name="Jane", email="jane@example.com", role="student")
    mock_session = MagicMock()
    mock_session.get.return_value = user
    mock_get_session.return_value = _session_context(mock_session)

    touch_last_login(user_id=uuid.uuid4())

    assert user.last_login is not None
    mock_session.commit.assert_called_once()


@patch("database.repositories.get_session")
def test_touch_last_login_is_noop_for_missing_user(mock_get_session: MagicMock):
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_get_session.return_value = _session_context(mock_session)

    touch_last_login(user_id=uuid.uuid4())  # should not raise

    mock_session.commit.assert_not_called()

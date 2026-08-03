"""Repository functions used by the Streamlit app."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database.connection import get_session
from database.exceptions import UserAlreadyExistsError
from database.models import (
    Answer,
    AuthToken,
    Evaluation,
    InterviewSession,
    JobDescription,
    MatchResult,
    Question,
    QuestionSet,
    Report,
    Resume,
    User,
)
from database.security import hash_password, verify_password

DEMO_USER_EMAIL = "demo@interview-platform.local"

TOKEN_KIND_VERIFY_EMAIL = "verify_email"
TOKEN_KIND_RESET_PASSWORD = "reset_password"

_VERIFY_TOKEN_TTL = timedelta(hours=24)
_RESET_TOKEN_TTL = timedelta(hours=1)


def _commit_and_refresh(session, record):
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_user(
    *,
    name: str,
    email: str,
    password: str,
    role: str,
    phone_number: str | None = None,
) -> User:
    """
    Create a new user account (sign-up).

    Args:
        name: Full name.
        email: Email address — used as the login identifier, must be unique.
        password: Plaintext password (hashed before storage, never stored raw).
        role: "student" or "recruiter".
        phone_number: Optional phone number.

    Returns:
        The newly created ``User``.

    Raises:
        UserAlreadyExistsError: If the email is already registered — either
            caught by the pre-check below, or (under a concurrent signup
            race, e.g. a double-submit) by the unique-constraint violation
            on commit.
    """
    normalized_email = email.strip().lower()

    with get_session() as session:
        existing = session.scalar(select(User).where(User.email == normalized_email))
        if existing is not None:
            raise UserAlreadyExistsError(
                f"An account with email '{normalized_email}' already exists."
            )

        user = User(
            name=name.strip(),
            email=normalized_email,
            password_hash=hash_password(password),
            phone_number=(phone_number or "").strip() or None,
            role=role,
            is_verified=False,
        )
        try:
            return _commit_and_refresh(session, user)
        except IntegrityError as exc:
            session.rollback()
            raise UserAlreadyExistsError(
                f"An account with email '{normalized_email}' already exists."
            ) from exc


def authenticate_user(*, email: str, password: str) -> User | None:
    """
    Verify login credentials.

    Args:
        email: Email address.
        password: Plaintext password to check.

    Returns:
        The matching ``User`` if the email exists and the password is
        correct, otherwise ``None``. Deliberately does not distinguish
        "no such account" from "wrong password" in its return value — that
        distinction is a user-enumeration risk and callers should show one
        generic "invalid email or password" message either way.
    """
    normalized_email = email.strip().lower()

    with get_session() as session:
        user = session.scalar(select(User).where(User.email == normalized_email))
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID | None:
    """Return ``value`` as a ``uuid.UUID``, or None if it isn't a valid one."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def get_user_by_id(user_id: uuid.UUID) -> User | None:
    """Fetch a user by primary key, or None if not found (or malformed id)."""
    parsed_id = _coerce_uuid(user_id)
    if parsed_id is None:
        return None
    with get_session() as session:
        return session.get(User, parsed_id)


def get_user_by_email(email: str) -> User | None:
    """Fetch a user by email, or None if not found."""
    normalized_email = email.strip().lower()
    with get_session() as session:
        return session.scalar(select(User).where(User.email == normalized_email))


def get_or_create_oauth_user(
    *,
    email: str,
    name: str,
    role: str,
    google_id: str | None = None,
) -> User:
    """
    Return the existing user for `email`, or create a new passwordless
    Google-authenticated account.

    If a matching row already exists (e.g. an account originally created
    via the old password sign-up, now signing in with a matching Google
    account), this opportunistically backfills `google_id` if it was unset,
    but never overwrites `name` or `role` on an existing row — a user's
    Settings-page edits or existing role assignment shouldn't be clobbered
    by a subsequent Google login. Role-mismatch checking against an
    existing user's `role` is the caller's responsibility.
    """
    normalized_email = email.strip().lower()

    with get_session() as session:
        existing = session.scalar(select(User).where(User.email == normalized_email))
        if existing is not None:
            if google_id and not existing.google_id:
                existing.google_id = google_id
                return _commit_and_refresh(session, existing)
            return existing

        user = User(
            name=name.strip() or normalized_email,
            email=normalized_email,
            password_hash=None,
            google_id=google_id,
            role=role,
            is_verified=True,  # Google already verified this email address
        )
        try:
            return _commit_and_refresh(session, user)
        except IntegrityError:
            session.rollback()
            return session.scalar(select(User).where(User.email == normalized_email))


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _issue_auth_token(*, session, user_id: uuid.UUID, kind: str, ttl: timedelta) -> str:
    """
    Invalidate any previous unused token of this (user_id, kind) — avoids
    multiple simultaneously-valid tokens piling up from repeated "resend"
    clicks — then create and return a brand-new raw token. The raw value
    is only ever available here; only its hash is stored.
    """
    now = datetime.now(UTC)
    stale_tokens = session.scalars(
        select(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.kind == kind,
            AuthToken.used_at.is_(None),
        )
    ).all()
    for stale in stale_tokens:
        stale.used_at = now

    raw_token = secrets.token_urlsafe(32)
    token = AuthToken(
        user_id=user_id,
        token_hash=_hash_token(raw_token),
        kind=kind,
        expires_at=now + ttl,
    )
    session.add(token)
    session.commit()
    return raw_token


def create_email_verification_token(*, user_id: uuid.UUID) -> str:
    """Create a new email-verification token for `user_id`, returning the raw token."""
    with get_session() as session:
        return _issue_auth_token(
            session=session, user_id=user_id, kind=TOKEN_KIND_VERIFY_EMAIL, ttl=_VERIFY_TOKEN_TTL,
        )


def create_password_reset_token(*, email: str) -> str | None:
    """
    Create a password-reset token for the account matching `email`.

    Returns None if no account exists for that email, OR the account has
    no password yet (a Google-only account) — forgot-password must never
    be usable to attach a FIRST password to a passwordless account; that
    would let anyone who merely knows/guesses the email hijack a Google
    account they don't actually control. Adding a first password is only
    possible from the Settings page while already authenticated (see
    `set_password`). Callers should show the same generic "if this email
    is registered, a reset link has been sent" message in every case, to
    avoid leaking which emails have accounts.
    """
    normalized_email = email.strip().lower()
    with get_session() as session:
        user = session.scalar(select(User).where(User.email == normalized_email))
        if user is None or user.password_hash is None:
            return None
        return _issue_auth_token(
            session=session, user_id=user.id, kind=TOKEN_KIND_RESET_PASSWORD, ttl=_RESET_TOKEN_TTL,
        )


def _load_valid_token(session, *, raw_token: str, kind: str) -> AuthToken | None:
    token = session.scalar(
        select(AuthToken).where(AuthToken.token_hash == _hash_token(raw_token))
    )
    if token is None or token.kind != kind or token.used_at is not None:
        return None
    if token.expires_at < datetime.now(UTC):
        return None
    return token


def validate_token(*, raw_token: str, kind: str) -> User | None:
    """Return the associated User if `raw_token` is a valid, unexpired,
    unused token of the given `kind` — without consuming it."""
    with get_session() as session:
        token = _load_valid_token(session, raw_token=raw_token, kind=kind)
        if token is None:
            return None
        return session.get(User, token.user_id)


def consume_email_verification_token(*, raw_token: str) -> User | None:
    """Validate, mark used, and apply a verify-email token: sets is_verified=True."""
    with get_session() as session:
        token = _load_valid_token(session, raw_token=raw_token, kind=TOKEN_KIND_VERIFY_EMAIL)
        if token is None:
            return None
        user = session.get(User, token.user_id)
        if user is None:
            return None
        token.used_at = datetime.now(UTC)
        user.is_verified = True
        return _commit_and_refresh(session, user)


def consume_password_reset_token(*, raw_token: str, new_password: str) -> User | None:
    """Validate, mark used, and apply a reset-password token: sets a new password_hash."""
    with get_session() as session:
        token = _load_valid_token(session, raw_token=raw_token, kind=TOKEN_KIND_RESET_PASSWORD)
        if token is None:
            return None
        user = session.get(User, token.user_id)
        if user is None:
            return None
        token.used_at = datetime.now(UTC)
        user.password_hash = hash_password(new_password)
        return _commit_and_refresh(session, user)


def set_password(*, user_id: uuid.UUID, password: str) -> User | None:
    """
    Set (or replace) a user's password.

    This is the only safe way to attach a FIRST password to an existing
    Google-only account, since calling it requires already knowing a valid
    user_id for an authenticated session — never call this from an
    anonymous/public entry point such as the signup form (use `create_user`
    there instead, which always rejects an already-registered email).
    """
    parsed_id = _coerce_uuid(user_id)
    if parsed_id is None:
        return None
    with get_session() as session:
        user = session.get(User, parsed_id)
        if user is None:
            return None
        user.password_hash = hash_password(password)
        return _commit_and_refresh(session, user)


def touch_last_login(*, user_id: uuid.UUID) -> None:
    """Best-effort update of last_login to now; a no-op if the user doesn't exist."""
    parsed_id = _coerce_uuid(user_id)
    if parsed_id is None:
        return
    with get_session() as session:
        user = session.get(User, parsed_id)
        if user is None:
            return
        user.last_login = datetime.now(UTC)
        session.add(user)
        session.commit()


def update_user_profile(
    *,
    user_id: uuid.UUID,
    name: str | None = None,
    phone_number: str | None = None,
) -> User | None:
    """
    Update editable profile fields for a user.

    Email and role are intentionally not editable here — email is the login
    identifier and role determines which dashboard the account belongs to;
    changing either is a bigger decision than a profile edit.

    Args:
        user_id: The user to update.
        name: New display name, if provided.
        phone_number: New phone number, if provided (pass "" to clear it).

    Returns:
        The updated ``User``, or ``None`` if no user with that id exists
        (or ``user_id`` isn't a valid UUID).
    """
    parsed_id = _coerce_uuid(user_id)
    if parsed_id is None:
        return None

    with get_session() as session:
        user = session.get(User, parsed_id)
        if user is None:
            return None

        if name is not None and name.strip():
            user.name = name.strip()
        if phone_number is not None:
            user.phone_number = phone_number.strip() or None

        return _commit_and_refresh(session, user)


def ensure_demo_user(role: str | None = None) -> User:
    """
    Return a demo user for the given role — used by scripts/tests that need
    a User row without going through full sign-up. Not used by the app's
    real login/sign-up flow (see create_user/authenticate_user above).
    """
    demo_email = DEMO_USER_EMAIL if role != "recruiter" else "demo-recruiter@interview-platform.local"
    with get_session() as session:
        existing = session.scalar(select(User).where(User.email == demo_email))
        if existing:
            return existing

        user = User(
            name="Demo User",
            email=demo_email,
            password_hash=hash_password("demo-password-not-for-real-use"),
            role=role or "student",
        )
        return _commit_and_refresh(session, user)


def save_resume(
    *,
    user_id: uuid.UUID,
    original_file_name: str,
    file_type: str,
    raw_text: str,
    parsed_resume_json: dict[str, Any],
) -> Resume:
    with get_session() as session:
        resume = Resume(
            user_id=user_id,
            original_file_name=original_file_name,
            file_type=file_type,
            raw_text=raw_text,
            parsed_resume_json=parsed_resume_json,
        )
        return _commit_and_refresh(session, resume)


def save_job_description(
    *,
    user_id: uuid.UUID,
    original_file_name: str | None,
    file_type: str,
    raw_text: str,
    parsed_jd_json: dict[str, Any],
) -> JobDescription:
    with get_session() as session:
        jd = JobDescription(
            user_id=user_id,
            original_file_name=original_file_name,
            file_type=file_type,
            raw_text=raw_text,
            parsed_jd_json=parsed_jd_json,
        )
        return _commit_and_refresh(session, jd)


def save_match_result(
    *,
    resume_id: uuid.UUID,
    job_description_id: uuid.UUID,
    score: float,
    result_json: dict[str, Any],
) -> MatchResult:
    with get_session() as session:
        match_result = MatchResult(
            resume_id=resume_id,
            job_description_id=job_description_id,
            score=score,
            result_json=result_json,
        )
        return _commit_and_refresh(session, match_result)


def update_match_result_semantic(
    *,
    match_result_id: uuid.UUID,
    semantic_evaluation: dict[str, Any],
) -> MatchResult | None:
    """
    Best-effort merge of a semantic_matching evaluation into an existing
    match_results row.

    No new column or migration is needed: semantic_matching produces an
    independent evaluation of the same resume/JD pair, so it is nested
    under a "semantic_evaluation" key inside the same JSONB result_json
    blob that save_match_result already writes. Full attribute reassignment
    (rather than in-place dict mutation) is required here so SQLAlchemy's
    change tracking picks it up without needing MutableDict.
    """
    with get_session() as session:
        match_result = session.get(MatchResult, match_result_id)
        if match_result is None:
            return None
        merged = dict(match_result.result_json or {})
        merged["semantic_evaluation"] = semantic_evaluation
        match_result.result_json = merged
        return _commit_and_refresh(session, match_result)


def update_match_result_recruiter(
    *,
    match_result_id: uuid.UUID,
    recruiter_evaluation: dict[str, Any],
) -> MatchResult | None:
    """
    Best-effort merge of a Recruiter Intelligence Engine result into an
    existing match_results row.

    No new column or migration is needed: the Recruiter Intelligence Engine
    produces an independent evaluation of the same resume/JD pair, so it is
    nested under a "recruiter_evaluation" key inside the same JSONB
    result_json blob that save_match_result already writes (the same
    pattern used for the semantic_matching evaluation). Full attribute
    reassignment (rather than in-place dict mutation) is required here so
    SQLAlchemy's change tracking picks it up without needing MutableDict.
    """
    with get_session() as session:
        match_result = session.get(MatchResult, match_result_id)
        if match_result is None:
            return None
        merged = dict(match_result.result_json or {})
        merged["recruiter_evaluation"] = recruiter_evaluation
        match_result.result_json = merged
        return _commit_and_refresh(session, match_result)


def save_question_set(
    *,
    user_id: uuid.UUID,
    resume_id: uuid.UUID | None,
    job_description_id: uuid.UUID,
    match_result_id: uuid.UUID | None,
    difficulty: str,
    questions: list[dict[str, Any]],
) -> tuple[QuestionSet, list[Question]]:
    with get_session() as session:
        question_set = QuestionSet(
            user_id=user_id,
            resume_id=resume_id,
            job_description_id=job_description_id,
            match_result_id=match_result_id,
            difficulty=difficulty,
            question_count=len(questions),
        )
        session.add(question_set)
        session.flush()

        question_records = [
            Question(
                question_set_id=question_set.id,
                question_text=q.get("question", ""),
                category=q.get("category"),
                difficulty=q.get("difficulty"),
                reason=q.get("reason"),
                order_index=index,
            )
            for index, q in enumerate(questions)
        ]
        session.add_all(question_records)
        session.commit()
        session.refresh(question_set)
        for question in question_records:
            session.refresh(question)
        return question_set, question_records


def create_interview_session(
    *,
    user_id: uuid.UUID,
    question_set_id: uuid.UUID | None,
    resume_id: uuid.UUID | None,
    job_description_id: uuid.UUID | None,
    role_context: str | None,
) -> InterviewSession:
    with get_session() as session:
        interview_session = InterviewSession(
            user_id=user_id,
            question_set_id=question_set_id,
            resume_id=resume_id,
            job_description_id=job_description_id,
            role_context=role_context,
            status="started",
        )
        return _commit_and_refresh(session, interview_session)


def complete_interview_session(interview_session_id: uuid.UUID) -> None:
    with get_session() as session:
        interview_session = session.get(InterviewSession, interview_session_id)
        if interview_session is None:
            return
        interview_session.status = "completed"
        interview_session.completed_at = datetime.now(UTC)
        session.commit()


def save_answer(
    *,
    interview_session_id: uuid.UUID,
    question_id: uuid.UUID | None,
    question_text: str,
    answer_text: str,
    transcript_text: str | None,
) -> Answer:
    with get_session() as session:
        answer = Answer(
            interview_session_id=interview_session_id,
            question_id=question_id,
            question_text=question_text,
            answer_text=answer_text,
            transcript_text=transcript_text,
        )
        return _commit_and_refresh(session, answer)


def save_evaluation(
    *,
    answer_id: uuid.UUID,
    evaluation_json: dict[str, Any],
) -> Evaluation:
    with get_session() as session:
        evaluation = Evaluation(
            answer_id=answer_id,
            overall_score=float(evaluation_json.get("overall_score", 0)),
            correctness=_optional_float(evaluation_json.get("correctness")),
            keyword_coverage=_optional_float(evaluation_json.get("keyword_coverage")),
            clarity=_optional_float(evaluation_json.get("clarity")),
            communication=_optional_float(evaluation_json.get("communication")),
            completeness=_optional_float(evaluation_json.get("completeness")),
            strengths_json=evaluation_json.get("strengths"),
            improvements_json=evaluation_json.get("improvements"),
            feedback=evaluation_json.get("feedback"),
            ideal_answer=evaluation_json.get("ideal_answer"),
            evaluation_json=evaluation_json,
        )
        return _commit_and_refresh(session, evaluation)


def save_report(
    *,
    interview_session_id: uuid.UUID,
    overall_score: float,
    summary_json: dict[str, Any],
    recommendation: str | None,
) -> Report:
    with get_session() as session:
        report = Report(
            interview_session_id=interview_session_id,
            overall_score=overall_score,
            summary_json=summary_json,
            recommendation=recommendation,
        )
        return _commit_and_refresh(session, report)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


# ── Read-back queries (history / reporting) ────────────────────────────────
#
# Everything above this line only ever writes. The functions below read data
# back, so the database is genuinely round-tripped (used for history and
# reporting) rather than being a write-only audit log nobody ever queries.


def list_recent_reports(*, user_id: uuid.UUID, limit: int = 5) -> list[dict[str, Any]]:
    """
    Return the user's most recent completed interview reports, newest first.

    Each entry summarizes one interview session: overall score, role
    context, and when it happened — enough to render a "Previous Reports"
    list without pulling every joined row's full detail.
    """
    with get_session() as session:
        rows = session.execute(
            select(Report, InterviewSession)
            .join(
                InterviewSession,
                Report.interview_session_id == InterviewSession.id,
            )
            .where(InterviewSession.user_id == user_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
        ).all()

        return [
            {
                "interview_session_id": str(interview_session.id),
                "role_context": interview_session.role_context,
                "overall_score": report.overall_score,
                "recommendation": report.recommendation,
                "created_at": report.created_at.isoformat(),
            }
            for report, interview_session in rows
        ]


def list_recent_candidate_screenings(
    *, user_id: uuid.UUID, limit: int = 5
) -> list[dict[str, Any]]:
    """
    Return the recruiter's most recently screened candidates, newest first.

    Each entry summarizes one resume-vs-JD match: candidate name, role
    screened for, match score, and when it happened. This is the
    recruiter-side counterpart to `list_recent_reports` — that function is
    scoped to a user's own completed *practice interviews*, which isn't
    the right shape for a recruiter (recruiters screen candidates, they
    don't take practice interviews themselves).
    """
    with get_session() as session:
        rows = session.execute(
            select(MatchResult, Resume, JobDescription)
            .join(Resume, MatchResult.resume_id == Resume.id)
            .join(JobDescription, MatchResult.job_description_id == JobDescription.id)
            .where(Resume.user_id == user_id)
            .order_by(MatchResult.created_at.desc())
            .limit(limit)
        ).all()

        return [
            {
                "match_result_id": str(match_result.id),
                "candidate_name": resume.parsed_resume_json.get("name") or "Candidate",
                "role_context": job_description.parsed_jd_json.get("role") or "General Role",
                "score": match_result.score,
                "created_at": match_result.created_at.isoformat(),
            }
            for match_result, resume, job_description in rows
        ]


def get_report_detail(*, interview_session_id: uuid.UUID) -> dict[str, Any] | None:
    """
    Return the full report + per-answer evaluation breakdown for one
    interview session, for a "view full report" drill-down.
    """
    with get_session() as session:
        report = session.scalar(
            select(Report).where(
                Report.interview_session_id == interview_session_id
            )
        )
        if report is None:
            return None

        answer_rows = session.execute(
            select(Answer, Evaluation)
            .join(Evaluation, Evaluation.answer_id == Answer.id, isouter=True)
            .where(Answer.interview_session_id == interview_session_id)
            .order_by(Answer.created_at.asc())
        ).all()

        return {
            "overall_score": report.overall_score,
            "recommendation": report.recommendation,
            "summary_json": report.summary_json,
            "created_at": report.created_at.isoformat(),
            "answers": [
                {
                    "question_text": answer.question_text,
                    "answer_text": answer.answer_text,
                    "overall_score": evaluation.overall_score if evaluation else None,
                    "strengths": evaluation.strengths_json if evaluation else [],
                    "improvements": evaluation.improvements_json if evaluation else [],
                    "feedback": evaluation.feedback if evaluation else None,
                    "ideal_answer": evaluation.ideal_answer if evaluation else None,
                }
                for answer, evaluation in answer_rows
            ],
        }

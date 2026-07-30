"""
AI Interview Intelligence Platform
----------------------------------

This file contains the complete UI for the platform, wired to the real
backend modules and to PostgreSQL persistence:

    Auth            -> Google Sign-In (Streamlit native OIDC, see auth_ui.py)
                       + database.repositories (get_user_by_email /
                       get_or_create_oauth_user)
    Resume upload   -> resume_processing.process_resume.process_resume_with_raw_text
    JD upload/paste -> jd_parsing.parse_jd
    Match score     -> recruiter_intelligence (extract_requirements ->
                       evaluate_hard_requirements -> evaluate_evidence -> aggregate)
    Question gen    -> question_generation.generate_questions.generate_questions
    Voice answer    -> speech_to_text.transcribe_audio_bytes
    Answer scoring  -> answer_evaluation.evaluate_answer
    Persistence     -> database.repositories (best-effort via database.safe.safe_call)

Run with:
    streamlit run app.py

Requires a .env file (see .env.example) with your GLM API credentials, and
a `.streamlit/secrets.toml` with an `[auth]` section (Google OAuth client)
for sign-in — see the README for setup steps. Signing in requires
DATABASE_URL to be configured (accounts have to live somewhere) —
everything else in the app degrades gracefully without a database, but
auth is the one hard dependency on it.
"""

import html
import tempfile
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

import auth_ui
import auth_validation
import email_service
from resume_processing.docx_extractor import extract_text_from_docx
from resume_processing.exceptions import ResumeProcessingError
from resume_processing.pdf_extractor import extract_text_from_pdf
from resume_processing.process_resume import process_resume_with_raw_text
from resume_processing.schema import ParsedResume

from jd_parsing import parse_jd
from jd_parsing.exceptions import JDProcessingError
from jd_parsing.schema import ParsedJD
from recruiter_intelligence import aggregate as run_recruiter_aggregation
from recruiter_intelligence import evaluate_evidence, evaluate_hard_requirements, extract_requirements
from recruiter_intelligence.exceptions import RecruiterIntelligenceError
from answer_evaluation import evaluate_answer
from answer_evaluation.exceptions import AnswerEvaluationProcessingError
from speech_to_text import transcribe_audio_bytes, TranscriptionError

from question_generation.generate_questions import generate_questions
from question_generation.exceptions import QuestionGenerationError

from database import repositories as db_repo
from database.connection import DatabaseNotConfigured, get_database_url
from database.safe import safe_call

# Resume uploads accept these extensions — must stay in sync with
# resume_processing.process_resume._SUPPORTED_EXTENSIONS.
_SUPPORTED_RESUME_EXTENSIONS = (".pdf", ".docx")

# Pages that require a logged-in user.
_PROTECTED_PAGES = {"student", "recruiter", "interview", "report", "settings", "candidates"}


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="AI Interview Intelligence Platform",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# SESSION STATE INITIALIZATION
# =========================================================

if "page" not in st.session_state:
    st.session_state.page = "home"

if "current_question_index" not in st.session_state:
    st.session_state.current_question_index = 0

if "is_recording" not in st.session_state:
    st.session_state.is_recording = False

if "role" not in st.session_state:
    st.session_state.role = None

# --- Auth ---
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None            # dict: id, name, email, phone_number, role,
                                                   # is_verified, has_password

if "pending_role" not in st.session_state:
    st.session_state.pending_role = None          # "student" or "recruiter" — which portal was clicked

if "auth_role_mismatch" not in st.session_state:
    st.session_state.auth_role_mismatch = None    # existing account's role, if it != target_role
                                                   # (shared by both the Google and email login paths)

if "google_auth_error" not in st.session_state:
    st.session_state.google_auth_error = None     # friendly message if the DB lookup/create fails

if "google_sync_checked" not in st.session_state:
    st.session_state.google_sync_checked = False  # guards _sync_google_login() from re-running

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"          # "login" | "signup" | "forgot_password" | "reset_password"

if "pending_reset_token" not in st.session_state:
    st.session_state.pending_reset_token = None   # raw token, set when a reset link is opened

if "dev_email_preview" not in st.session_state:
    st.session_state.dev_email_preview = None     # {"to", "link"} — dev-stub verify/reset email preview

if "last_activity_at" not in st.session_state:
    st.session_state.last_activity_at = None      # time.time() of last activity, for idle-timeout

if "auth_flash" not in st.session_state:
    st.session_state.auth_flash = None            # (kind, message) tuple shown once, then cleared

# --- Backend data, populated as the user moves through the flow ---
if "parsed_resume" not in st.session_state:
    st.session_state.parsed_resume = None          # dict from resume_processing

if "resume_raw_text" not in st.session_state:
    st.session_state.resume_raw_text = None        # raw extracted text, for DB storage

if "parsed_jd" not in st.session_state:
    st.session_state.parsed_jd = None               # dict from jd_parsing

if "jd_raw_text" not in st.session_state:
    st.session_state.jd_raw_text = None              # raw JD text, for DB storage

if "recruiter_match_result" not in st.session_state:
    st.session_state.recruiter_match_result = None   # dict from recruiter_intelligence.aggregate

if "recruiter_match_error" not in st.session_state:
    st.session_state.recruiter_match_error = None    # friendly message when the pipeline failed

if "questions" not in st.session_state:
    st.session_state.questions = None                # list[dict] from question_generation

if "answers" not in st.session_state:
    st.session_state.answers = {}                    # {question_index: candidate answer text}

if "evaluations" not in st.session_state:
    st.session_state.evaluations = {}                # {question_index: evaluation dict}

# --- Database row IDs, populated as records are persisted ---
if "db_user_id" not in st.session_state:
    st.session_state.db_user_id = None

if "resume_db_id" not in st.session_state:
    st.session_state.resume_db_id = None

if "jd_db_id" not in st.session_state:
    st.session_state.jd_db_id = None

if "match_db_id" not in st.session_state:
    st.session_state.match_db_id = None

if "question_set_db_id" not in st.session_state:
    st.session_state.question_set_db_id = None

if "question_db_ids" not in st.session_state:
    st.session_state.question_db_ids = []            # index-aligned with st.session_state.questions

if "interview_session_db_id" not in st.session_state:
    st.session_state.interview_session_db_id = None

if "report_saved" not in st.session_state:
    st.session_state.report_saved = False

# --- File-uploader widget "reset" counters ---------------------------------
# Streamlit retains a widget's value under its key across reruns. Bumping
# these (rather than reusing a fixed key) forces a fresh, empty uploader
# after "Change" / logout, instead of showing the previously-selected file.
if "resume_uploader_version" not in st.session_state:
    st.session_state.resume_uploader_version = 0

if "jd_uploader_version" not in st.session_state:
    st.session_state.jd_uploader_version = 0


def go_to(page_name):
    """Central navigation helper. Updates session_state.page."""
    st.session_state.page = page_name
    st.rerun()


# =========================================================
# DATABASE HELPERS (best-effort — app works fine without a DB)
# =========================================================

def _db_configured() -> bool:
    """Check whether DATABASE_URL is set, without attempting a connection."""
    try:
        get_database_url()
        return True
    except DatabaseNotConfigured:
        return False


def _current_user_id():
    """Return the logged-in user's DB id, or None if not logged in."""
    return st.session_state.db_user_id


def _log_in_user(user) -> None:
    """Populate session_state from a freshly authenticated/created User row."""
    st.session_state.auth_user = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role,
        "is_verified": user.is_verified,
        "has_password": user.password_hash is not None,
    }
    st.session_state.db_user_id = user.id
    st.session_state.role = user.role
    st.session_state.last_activity_at = time.time()
    safe_call(db_repo.touch_last_login, user_id=user.id)

    redirect_page = st.session_state.pending_role or user.role
    st.session_state.pending_role = None
    go_to(redirect_page)


def _log_out_user() -> None:
    """Clear auth + all in-progress session work, and return to Home."""
    st.logout()
    for key in (
        "auth_user", "role", "parsed_resume", "resume_raw_text", "parsed_jd",
        "jd_raw_text", "recruiter_match_result", "recruiter_match_error",
        "questions", "auth_role_mismatch", "google_auth_error",
    ):
        st.session_state[key] = None
    st.session_state.google_sync_checked = False
    st.session_state.auth_mode = "login"
    st.session_state.pending_reset_token = None
    st.session_state.dev_email_preview = None
    st.session_state.last_activity_at = None
    st.session_state.answers = {}
    st.session_state.evaluations = {}
    for key in (
        "db_user_id", "resume_db_id", "jd_db_id", "match_db_id",
        "question_set_db_id", "interview_session_db_id",
    ):
        st.session_state[key] = None
    st.session_state.question_db_ids = []
    st.session_state.report_saved = False
    st.session_state.current_question_index = 0
    st.session_state.resume_uploader_version += 1
    st.session_state.jd_uploader_version += 1
    go_to("home")


def _sync_google_login() -> None:
    """
    Populate session_state.auth_user from a completed Google sign-in.

    st.session_state (including pending_role) does NOT survive the OAuth
    redirect round-trip to Google and back — Streamlit starts a fresh
    session on the callback. To recover which portal the user intended,
    this relies on st.user["provider"]: show_auth_page() calls
    st.login(target_role) using a *named* provider ("student"/"recruiter",
    both configured in secrets.toml against the same real Google client),
    and that provider name survives in Streamlit's own auth cookie into
    st.user["provider"] after the redirect — immune to the session reset.

    Runs once per app rerun, as the first line of main(), since a
    just-completed redirect may land on page="home" before routing.
    """
    if st.session_state.auth_user is not None:
        return
    if not st.user.get("is_logged_in", False):
        st.session_state.google_sync_checked = False
        return
    if st.session_state.google_sync_checked:
        return  # already resolved this Google session; avoid a mismatch-redirect loop
    st.session_state.google_sync_checked = True

    target_role = st.user.get("provider")
    if target_role not in ("student", "recruiter"):
        target_role = st.session_state.pending_role or st.session_state.page
        if target_role not in ("student", "recruiter"):
            target_role = "student"

    email = st.user.get("email")
    if not email:
        return

    st.session_state.auth_role_mismatch = None
    st.session_state.google_auth_error = None
    try:
        existing = db_repo.get_user_by_email(email)
        if existing is not None:
            if existing.role != target_role:
                st.session_state.auth_role_mismatch = existing.role
                go_to(target_role)
                return
            _log_in_user(existing)
        else:
            new_user = db_repo.get_or_create_oauth_user(
                email=email,
                name=st.user.get("name") or email,
                role=target_role,
                google_id=st.user.get("sub"),
            )
            _log_in_user(new_user)
    except DatabaseNotConfigured:
        st.session_state.google_auth_error = (
            "Signed in with Google, but your account couldn't be loaded — "
            "a database connection is required. Set DATABASE_URL in your "
            ".env file, then try again."
        )
        go_to(target_role)
    except SQLAlchemyError:
        st.session_state.google_auth_error = (
            "Signed in with Google, but couldn't reach the database. Check "
            "that PostgreSQL is running and try again."
        )
        go_to(target_role)


def _handle_auth_token_query_params() -> None:
    """
    Resolve a ?verify_token=...  or ?reset_token=... opened fresh (e.g. from
    the dev-stub email preview, or a real emailed link once a provider is
    configured). Runs before anything else in main() — a fresh link-open
    may land on page="home" before routing, same reason _sync_google_login()
    also runs first.

    Google's own OAuth callback params (code/state) are fully consumed by
    Streamlit's auth machinery before this script ever executes, so there's
    no shared-namespace collision with these two params.
    """
    params = st.query_params
    verify_token = params.get("verify_token")
    reset_token = params.get("reset_token")
    if not verify_token and not reset_token:
        return
    st.query_params.clear()  # drop from the URL immediately so a refresh can't re-trigger this

    if verify_token:
        try:
            user = db_repo.consume_email_verification_token(raw_token=verify_token)
        except (DatabaseNotConfigured, SQLAlchemyError):
            st.session_state.auth_flash = (
                "error",
                "Could not verify your email — the database is unavailable. "
                "Please try again shortly.",
            )
            return
        if user is None:
            st.session_state.auth_flash = (
                "error", "This verification link is invalid or has expired.",
            )
            return
        st.session_state.auth_flash = ("success", "Your email has been verified.")
        if st.session_state.auth_user is not None and st.session_state.auth_user["id"] == user.id:
            st.session_state.auth_user["is_verified"] = True
            st.session_state.dev_email_preview = None
        return

    # reset_token: validate only here — it gets marked used at the actual
    # "set new password" submit, not just for opening the link.
    try:
        user = db_repo.validate_token(
            raw_token=reset_token, kind=db_repo.TOKEN_KIND_RESET_PASSWORD,
        )
    except (DatabaseNotConfigured, SQLAlchemyError):
        st.session_state.auth_flash = (
            "error",
            "Could not validate this link — the database is unavailable. "
            "Please try again shortly.",
        )
        return
    if user is None:
        st.session_state.auth_flash = (
            "error", "This password reset link is invalid or has expired.",
        )
        return

    # Force a clean slate for this browser tab — a reset link shouldn't
    # resolve against whatever session happens to already be active.
    # Deliberately NOT calling the full _log_out_user(): it ends in
    # go_to() -> st.rerun(), which raises immediately and would discard
    # the state set just below on the very next line — and by now
    # st.query_params.clear() has already run, so the token couldn't be
    # recovered on a subsequent pass either. Nothing has rendered yet this
    # run, so mutating session_state here and falling through to the rest
    # of main() is safe.
    if st.session_state.auth_user is not None:
        st.session_state.auth_user = None
        st.session_state.db_user_id = None
        st.session_state.role = None

    st.session_state.pending_reset_token = reset_token
    st.session_state.auth_mode = "reset_password"
    if user.role in ("student", "recruiter"):
        st.session_state.pending_role = user.role
        st.session_state.page = user.role


_SESSION_IDLE_TIMEOUT_SECONDS = 30 * 60


def _enforce_session_idle_timeout() -> None:
    """
    Log out a logged-in session that's been idle too long.

    Only fires on the next user-triggered rerun, not a true background
    timer — an idle tab won't visibly "expire" until the user comes back
    and interacts, at which point this immediately logs them out before
    showing the protected page. Meaningful protection against someone else
    continuing an unattended, already-open session; not a substitute for a
    real push-based expiry.
    """
    if st.session_state.auth_user is None:
        return
    last_seen = st.session_state.last_activity_at
    now = time.time()
    if last_seen is not None and (now - last_seen) > _SESSION_IDLE_TIMEOUT_SECONDS:
        st.session_state.auth_flash = (
            "error", "Your session expired due to inactivity. Please sign in again.",
        )
        _log_out_user()
        return
    st.session_state.last_activity_at = now


def _render_auth_flash() -> None:
    """Show a one-time flash message set by the token/idle-timeout handlers above."""
    flash = st.session_state.auth_flash
    if not flash:
        return
    st.session_state.auth_flash = None
    kind, message = flash
    if kind == "success":
        st.success(message)
    else:
        st.error(message)


def _ensure_interview_session_db_id():
    """Lazily create an interview_sessions row the first time it's needed."""
    if st.session_state.interview_session_db_id is not None:
        return st.session_state.interview_session_db_id

    user_id = _current_user_id()
    if user_id is None:
        return None

    role_context = None
    if st.session_state.parsed_jd:
        role_context = st.session_state.parsed_jd.get("role")

    session_record = safe_call(
        db_repo.create_interview_session,
        user_id=user_id,
        question_set_id=st.session_state.question_set_db_id,
        resume_id=st.session_state.resume_db_id,
        job_description_id=st.session_state.jd_db_id,
        role_context=role_context,
    )
    if session_record is not None:
        st.session_state.interview_session_db_id = session_record.id
    return st.session_state.interview_session_db_id


# =========================================================
# BACKEND HELPER FUNCTIONS
# =========================================================

def _save_upload_to_temp(uploaded_file) -> Path:
    """Persist a Streamlit UploadedFile to a temp path and return it."""
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return Path(tmp.name)


def _extract_text_from_upload(uploaded_file) -> str:
    """
    Extract raw text from an uploaded JD file (.txt, .pdf, or .docx).
    Raises ValueError with a user-facing message on failure.
    """
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix == ".txt":
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")

    if suffix == ".pdf":
        tmp_path = _save_upload_to_temp(uploaded_file)
        try:
            return extract_text_from_pdf(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    if suffix == ".docx":
        tmp_path = _save_upload_to_temp(uploaded_file)
        try:
            return extract_text_from_docx(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    raise ValueError(f"Unsupported file type: {suffix}")


def _process_resume_upload(uploaded_file):
    """Run the resume upload (PDF or DOCX) through the resume_processing pipeline."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in _SUPPORTED_RESUME_EXTENSIONS:
        st.warning(
            "The resume parser supports PDF and DOCX files. "
            "Please upload a .pdf or .docx version of your resume."
        )
        return

    tmp_path = _save_upload_to_temp(uploaded_file)
    try:
        with st.spinner("Parsing resume..."):
            raw_text, parsed = process_resume_with_raw_text(tmp_path)
        st.session_state.parsed_resume = parsed.model_dump()
        st.session_state.resume_raw_text = raw_text
        st.session_state.resume_db_id = None
        # A new resume invalidates any match result computed against the
        # previous one — force a fresh evaluation.
        st.session_state.recruiter_match_result = None
        st.session_state.recruiter_match_error = None
        st.session_state.match_db_id = None
        st.success(f"Resume parsed — found {len(parsed.skills)} skills.")

        user_id = _current_user_id()
        if user_id is not None:
            saved = safe_call(
                db_repo.save_resume,
                user_id=user_id,
                original_file_name=uploaded_file.name,
                file_type=suffix.lstrip("."),
                raw_text=raw_text,
                parsed_resume_json=st.session_state.parsed_resume,
            )
            if saved is not None:
                st.session_state.resume_db_id = saved.id
                st.caption("💾 Saved to database.")
    except ResumeProcessingError as exc:
        st.error(f"Could not parse resume: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)


def _parse_jd_text(jd_text: str, *, original_file_name: str | None = None, file_type: str = "txt"):
    """Run raw JD text through the JD parser and persist it."""
    if not jd_text or not jd_text.strip():
        st.warning("Please upload a job description file or paste JD text first.")
        return

    try:
        with st.spinner("Parsing job description..."):
            parsed = parse_jd(jd_text).model_dump()
        st.session_state.parsed_jd = parsed
        st.session_state.jd_raw_text = jd_text
        st.session_state.jd_db_id = None
        # A new JD invalidates the previous match result and any question
        # set generated against the old JD.
        st.session_state.recruiter_match_result = None
        st.session_state.recruiter_match_error = None
        st.session_state.match_db_id = None
        st.session_state.questions = None
        st.session_state.question_set_db_id = None
        st.session_state.question_db_ids = []
        st.success(f"Job description parsed — role: {parsed.get('role') or 'N/A'}")

        user_id = _current_user_id()
        if user_id is not None:
            saved = safe_call(
                db_repo.save_job_description,
                user_id=user_id,
                original_file_name=original_file_name,
                file_type=file_type,
                raw_text=jd_text,
                parsed_jd_json=parsed,
            )
            if saved is not None:
                st.session_state.jd_db_id = saved.id
                st.caption("💾 Saved to database.")
    except JDProcessingError as exc:
        st.error(f"Could not parse job description: {exc}")


def _run_skill_gap():
    """
    Run the Recruiter Match pipeline against the currently stored resume +
    JD, and persist the result. This is the only scoring system in the UI
    (see the approved "One Recruiter Match Score" plan) — matching_engine
    and semantic_matching are no longer called here; they remain importable
    internally (benchmark comparison, migration safety net) but are not
    part of the live scoring path.
    """
    resume_json = st.session_state.parsed_resume
    jd_json = st.session_state.parsed_jd

    if not resume_json or not jd_json:
        st.info("Upload and parse both a resume and a job description first.")
        return

    st.session_state.recruiter_match_result = None
    st.session_state.recruiter_match_error = None
    st.session_state.match_db_id = None

    recruiter_json = None
    try:
        with st.spinner("Evaluating candidate match..."):
            parsed_jd = ParsedJD.model_validate(jd_json)
            parsed_resume = ParsedResume.model_validate(resume_json)
            stage_a = extract_requirements(parsed_jd)
            hard_gate = evaluate_hard_requirements(parsed_jd, parsed_resume)
            stage_c = evaluate_evidence(stage_a, parsed_resume)
            recruiter_result = run_recruiter_aggregation(stage_a, stage_c, hard_gate, parsed_resume)
        recruiter_json = recruiter_result.model_dump()
        st.session_state.recruiter_match_result = recruiter_json
    except RecruiterIntelligenceError as exc:
        st.session_state.recruiter_match_error = f"Match evaluation is unavailable right now. ({exc})"
        return

    resume_db_id = st.session_state.resume_db_id
    jd_db_id = st.session_state.jd_db_id
    if resume_db_id is not None and jd_db_id is not None:
        saved = safe_call(
            db_repo.save_match_result,
            resume_id=resume_db_id,
            job_description_id=jd_db_id,
            score=recruiter_json["recruiter_match_score"],
            result_json=recruiter_json,
        )
        if saved is not None:
            st.session_state.match_db_id = saved.id


def _question_generation_context() -> dict:
    """
    Derive question_generation's match-result input from the unified
    Recruiter Match Score result (see the approved "One Recruiter Match
    Score" plan, section 9) -- no parallel scoring logic here, every field
    reads directly off recruiter_match_result's already-computed values.
    Returns {} if the recruiter evaluation isn't available for this session
    (e.g. the GLM call failed) so question generation can still proceed
    with less context rather than block entirely.
    """
    recruiter_result = st.session_state.get("recruiter_match_result")
    if not recruiter_result:
        return {}
    return {
        "score": recruiter_result.get("recruiter_match_score"),
        "recommendation": recruiter_result.get("recommendation"),
        "critical_missing_skills": recruiter_result.get("critical_missing_skills", []),
        "minor_missing_skills": recruiter_result.get("minor_missing_skills", []),
        "nice_to_have_missing_skills": recruiter_result.get("nice_to_have_missing_skills", []),
        "requirement_notes": [
            {"skill": item["text"], "score": item["score"], "reasoning": item["reasoning"]}
            for item in recruiter_result.get("requirement_breakdown", [])
        ],
    }


def _generate_questions(difficulty: str, question_count: int, use_resume: bool):
    """Call the question generation module, store the result, and persist it."""
    jd_json = st.session_state.parsed_jd
    if not jd_json:
        st.info("Upload and parse a job description first.")
        return

    resume_json = st.session_state.parsed_resume if use_resume else None
    resume_json = resume_json or {}
    match_result_json = _question_generation_context()

    try:
        with st.spinner("Generating interview questions..."):
            generated = generate_questions(
                resume_json=resume_json,
                jd_json=jd_json,
                match_result_json=match_result_json,
                difficulty=difficulty,
                question_count=question_count,
            )
        st.session_state.questions = [q.model_dump() for q in generated.questions]
        st.session_state.current_question_index = 0
        st.session_state.answers = {}
        st.session_state.evaluations = {}
        # A fresh question set means any previous interview session is done.
        st.session_state.interview_session_db_id = None
        st.session_state.report_saved = False
        st.session_state.question_set_db_id = None
        st.session_state.question_db_ids = []
        st.success(f"Generated {len(st.session_state.questions)} questions.")

        user_id = _current_user_id()
        jd_db_id = st.session_state.jd_db_id
        if user_id is not None and jd_db_id is not None:
            saved = safe_call(
                db_repo.save_question_set,
                user_id=user_id,
                resume_id=st.session_state.resume_db_id,
                job_description_id=jd_db_id,
                match_result_id=st.session_state.match_db_id,
                difficulty=difficulty,
                questions=st.session_state.questions,
            )
            if saved is not None:
                question_set, question_records = saved
                st.session_state.question_set_db_id = question_set.id
                st.session_state.question_db_ids = [q.id for q in question_records]
                st.caption("💾 Question set saved to database.")
    except QuestionGenerationError as exc:
        st.error(f"Could not generate questions: {exc}")


def _match_recommendation(score: float):
    """Map a match score to a shortlist/reject style AI recommendation."""
    if score >= 80:
        return "✅ Strong Match – Recommend for Interview", "success"
    if score >= 60:
        return "🟡 Potential Match – Review Resume Manually", "warning"
    return "❌ Weak Match – Candidate can be filtered before interview", "error"


def _job_role_and_skills():
    """Best-effort (role, required_skills) for the answer evaluator."""
    jd_json = st.session_state.parsed_jd or {}
    role = jd_json.get("role") or "General Role"
    skills = jd_json.get("required_skills") or []
    return role, skills


# =========================================================
# GUIDED-FLOW STEP HELPERS
# ---------------------------------------------------------
# Both dashboards are a linear pipeline (upload -> upload ->
# generate). The current step is *derived* from what's already
# in session_state rather than tracked as its own counter, so
# it can never drift out of sync with the actual data.
# =========================================================

def _student_current_step() -> int:
    """1=resume, 2=job description, 3=generate questions, 4=ready to practice."""
    if not st.session_state.parsed_resume:
        return 1
    if not st.session_state.parsed_jd:
        return 2
    if not st.session_state.questions:
        return 3
    return 4


def _recruiter_current_step() -> int:
    """1=job description, 2=candidate resume, 3=match + generate questions."""
    if not st.session_state.parsed_jd:
        return 1
    if not st.session_state.parsed_resume:
        return 2
    return 3


def _render_stepper(labels: list[str], current_step: int) -> None:
    """
    Render a horizontal step indicator. current_step is 1-indexed.

    Includes a visually-hidden "Step X of N: <label>" summary, independent
    of the visible circles/labels — the mobile breakpoint hides step-label
    text visually via `display:none`, which also removes it from screen
    readers (not just sighted users), so the accessible summary can't rely
    on that markup still being present at every viewport width.
    """
    current_label = labels[current_step - 1] if 1 <= current_step <= len(labels) else ""
    parts = [
        f'<p class="sr-only">Step {current_step} of {len(labels)}: {current_label}</p>'
    ]
    for i, label in enumerate(labels, start=1):
        state = "done" if i < current_step else ("active" if i == current_step else "")
        circle = "&#10003;" if state == "done" else str(i)
        current_attr = ' aria-current="step"' if state == "active" else ""
        parts.append(
            f'<div class="step step-{state}"{current_attr}>'
            f'<span class="step-circle" aria-hidden="true">{circle}</span>'
            f'<span class="step-label" aria-hidden="true">{label}</span>'
            f"</div>"
        )
        if i < len(labels):
            parts.append('<div class="step-line" aria-hidden="true"></div>')
    st.markdown(f'<div class="stepper">{"".join(parts)}</div>', unsafe_allow_html=True)


def _render_completed_step(
    title: str, detail: str, change_label: str, clear_keys: list[str], button_key: str
) -> None:
    """Compact confirmation row for a finished step, with a way to redo it."""
    col_text, col_btn = st.columns([5, 1])
    with col_text:
        # `title` is always a hardcoded caller literal ("Resume", "Job
        # description", ...), but `detail` carries the candidate's
        # AI-extracted resume name / the JD's extracted role — text an
        # attacker could try to steer via a crafted resume/JD, so it's
        # escaped here once rather than trusting every call site to do it.
        st.markdown(
            f'<div class="step-summary">&#9989; <strong>{html.escape(title)}</strong> '
            f'&mdash; {html.escape(detail)}</div>',
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button(change_label, key=button_key, use_container_width=True):
            for key in clear_keys:
                st.session_state[key] = [] if key == "question_db_ids" else None
            if "parsed_resume" in clear_keys:
                st.session_state.resume_uploader_version += 1
            if "parsed_jd" in clear_keys:
                st.session_state.jd_uploader_version += 1
            st.rerun()


def _render_resume_upload_step(
    *, heading: str, description: str, button_label: str, button_key: str, on_success=None,
) -> None:
    """
    Resume-upload step, shared by the student (own resume) and recruiter
    (candidate resume) dashboards — same widget, same parse call, only the
    copy/labels and the post-success follow-up action differ.
    """
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown(f"#### {heading}")
    st.markdown(description)
    resume_file = st.file_uploader(
        "Upload Resume", type=["pdf", "docx"],
        key=f"resume_upload_{st.session_state.resume_uploader_version}",
        label_visibility="collapsed",
    )
    if st.button(
        button_label, use_container_width=True, type="primary",
        key=button_key, disabled=resume_file is None,
    ):
        _process_resume_upload(resume_file)
        if st.session_state.parsed_resume:
            if on_success is not None:
                on_success()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def _render_jd_upload_step(*, heading: str, button_key: str, on_success=None) -> None:
    """
    JD paste/upload step, shared by both dashboards — same widgets, same
    parse call, only the heading, button key, and post-success follow-up
    action differ.
    """
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown(f"#### {heading}")
    st.markdown("Paste the text below, or upload a file.")
    jd_text = st.text_area(
        "Paste Job Description", height=140, key="jd_text_input",
        label_visibility="collapsed",
        placeholder="Paste the job description here...",
    )
    st.caption(f"{len(jd_text)} characters")
    jd_file = st.file_uploader(
        "Or upload a file (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"],
        key=f"jd_upload_{st.session_state.jd_uploader_version}",
    )
    # Not gated on `disabled=not jd_text.strip()` — st.text_area only
    # commits its value to session_state on blur or Ctrl/Cmd+Enter, so a
    # disabled-until-reactive button forced a "paste, then press
    # Ctrl+Enter, then click Continue" two-step flow. Validating inside
    # the click handler instead means pasting + a single click just works,
    # in both the student and recruiter portals (this step is shared).
    if st.button(
        "Continue", use_container_width=True, type="primary", key=button_key,
    ):
        if not jd_text.strip() and jd_file is None:
            st.warning("Paste the job description text or upload a file first.")
            st.markdown('</div>', unsafe_allow_html=True)
            return
        try:
            if jd_file is not None:
                text = _extract_text_from_upload(jd_file)
                _parse_jd_text(
                    text, original_file_name=jd_file.name,
                    file_type=Path(jd_file.name).suffix.lstrip(".").lower(),
                )
            else:
                _parse_jd_text(jd_text, original_file_name=None, file_type="txt")
        except ValueError as exc:
            st.error(str(exc))
        if st.session_state.parsed_jd:
            if on_success is not None:
                on_success()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def _render_recruiter_match_card(*, heading: str, show_recommendation: bool) -> None:
    """
    The single Recruiter Match Score card, shared by both dashboards (see
    the approved "One Recruiter Match Score" plan) — the deterministic
    matching_engine score and the freeform semantic_matching score that
    used to render as two additional, separate cards are gone; every number
    shown here is computed deterministically from Stage C's cited evidence
    (recruiter_intelligence.aggregation.aggregate) — the LLM never sets
    recruiter_match_score directly, and no second percentage exists
    anywhere on this card.

    Recruiters additionally see the recommendation callout (Strong Hire /
    Consider / Weak Match / Not Recommended), since that's a hiring
    decision — not something a student practicing on themselves needs to
    see framed that way.
    """
    result = st.session_state.get("recruiter_match_result")
    error = st.session_state.get("recruiter_match_error")

    if not result and not error:
        return

    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown(f"#### {heading}")
    st.caption(
        "Evidence-based evaluation — every point is traceable to a specific "
        "requirement and its cited resume evidence, not invented by the LLM."
    )

    if error:
        st.info(error)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    score = result["recruiter_match_score"]
    st.metric("Recruiter Match Score", f"{score:.0f} / 100")
    st.progress(min(score, 100) / 100)
    st.caption(f"Confidence: {result['confidence']} — {result['confidence_reason']}")

    if show_recommendation:
        recommendation_kind = {
            "Strong Hire": "success", "Consider": "warning",
            "Weak Match": "warning", "Not Recommended": "error",
        }.get(result["recommendation"], "info")
        getattr(st, recommendation_kind)(result["recommendation"])

    hard_gate = result.get("hard_gate") or {}
    if hard_gate.get("overall_status") == "fail":
        st.error("Disqualifying hard requirement(s) failed — see narrative below.")
    elif hard_gate.get("overall_status") == "needs_human_review":
        st.warning("At least one hard requirement needs human review (e.g. visa/clearance/location).")

    with st.expander("Critical Missing Skills", expanded=bool(result["critical_missing_skills"])):
        st.markdown(", ".join(result["critical_missing_skills"]) or "—")
    with st.expander("Minor / Nice-to-have Missing Skills"):
        combined = result["minor_missing_skills"] + result["nice_to_have_missing_skills"]
        st.markdown(", ".join(combined) or "—")
    with st.expander("Why this score", expanded=True):
        st.markdown(result.get("narrative") or "—")
    with st.expander("Per-requirement breakdown"):
        for item in result.get("requirement_breakdown", []):
            flag = "missing" if item["is_missing"] else "present"
            st.markdown(
                f"**{item['text']}** — {item['score']}/100 ({flag}, "
                f"weight {item['final_weight']:.2f}, contributed "
                f"{item.get('contribution', 0.0):.1f} pts) — {item['reasoning'] or '—'}"
            )
    st.markdown('</div>', unsafe_allow_html=True)


# =========================================================
# CHART HELPERS
# ---------------------------------------------------------
# Streamlit's native st.bar_chart / st.line_chart don't expose axis-title
# or tick-label-angle controls, which was leaving these charts with no
# axis labels and vertically-rotated x-tick text. Built directly on
# Altair (already a Streamlit dependency) for full control over both.
# =========================================================

def _labeled_bar_chart(df: pd.DataFrame, *, x: str, y: str, x_title: str, y_title: str, color: str) -> None:
    chart = (
        alt.Chart(df)
        .mark_bar(color=color, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X(f"{x}:N", title=x_title, sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{y}:Q", title=y_title),
            tooltip=[x, y],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)


def _labeled_line_chart(df: pd.DataFrame, *, x: str, y: str, x_title: str, y_title: str, color: str) -> None:
    chart = (
        alt.Chart(df)
        .mark_line(color=color, point=True, strokeWidth=3)
        .encode(
            x=alt.X(f"{x}:N", title=x_title, sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(domain=[0, 100])),
            tooltip=[x, y],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)


# =========================================================
# GLOBAL CSS
# ---------------------------------------------------------
# Uses Streamlit's built-in theme variables (--text-color,
# --background-color, --secondary-background-color) so that
# text and containers remain readable in both Light and Dark
# mode. No colors are hardcoded to plain white/black for text.
# =========================================================

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"]{
    font-family:'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

:root{
    --brand-1:#1D4ED8;
    --brand-2:#7C3AED;
    --accent-green:#16A34A;
    --accent-amber:#D97706;
    --accent-red:#DC2626;
}

/* General spacing */
.block-container{
    padding-top:2rem;
    padding-bottom:3rem;
}

/* Hero section */
.hero{
    background: linear-gradient(135deg, #1D4ED8, #2563EB);
    padding:48px;
    border-radius:16px;
    color:#FFFFFF;
    margin-bottom:32px;
    box-shadow:0 12px 28px -14px rgba(29,78,216,0.55);
}

.hero h1{
    font-size:2.4rem;
    font-weight:700;
    margin-bottom:8px;
    color:#FFFFFF;
}

.hero h2{
    /* Explicit size to preserve the original visual weight of this
       tagline — it was previously an <h3> with no font-size override
       (relying on the browser default), and h2's default is
       noticeably larger; changing the tag for correct heading order
       shouldn't also silently change how prominent it looks. */
    font-size:1.2rem;
    font-weight:500;
    color:#DBEAFE;
    margin-bottom:12px;
}

.hero p{
    color:#EFF6FF;
    font-size:1.05rem;
    max-width:700px;
}

/* Section headings */
.section-title{
    font-size:1.4rem;
    font-weight:700;
    margin:10px 0 18px 0;
    color:var(--text-color);
}

/* Feature / offer cards */
.offer-card{
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,0.25);
    border-radius:14px;
    padding:22px;
    height:100%;
    margin-bottom:16px;
    transition:transform .15s ease, box-shadow .15s ease;
}

.offer-card:hover{
    transform:translateY(-2px);
    box-shadow:0 10px 22px -14px rgba(29,78,216,0.35);
}

.offer-card .offer-icon{
    font-size:1.5rem;
    display:block;
    margin-bottom:6px;
}

.offer-card h4{
    color:var(--text-color);
    margin-bottom:6px;
    font-weight:700;
}

.offer-card p{
    color:var(--text-color);
    opacity:0.85;
    font-size:0.92rem;
    margin:0;
}

/* Portal cards */
.portal-card{
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,0.25);
    border-radius:16px;
    padding:28px;
    margin-bottom:16px;
}

.portal-card h3{
    color:var(--text-color);
    margin-bottom:14px;
    font-weight:700;
}

.portal-card ul{
    color:var(--text-color);
    opacity:0.9;
    padding-left:20px;
    margin-bottom:8px;
}

.portal-card li{
    margin-bottom:6px;
}

/* Dashboard cards */
.dash-card{
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,0.25);
    border-radius:14px;
    padding:20px;
    margin-bottom:16px;
}

/* Same visual language as .dash-card, but applied to a real
   st.container(key="set_password_card") rather than a hand-rolled <div> —
   this card holds a real st.form, and a raw <div> spanning multiple
   st.markdown/st.form calls never actually nests them in the real DOM
   (confirmed empirically while building the Google auth card earlier). */
.st-key-set_password_card{
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,0.25);
    border-radius:14px;
    padding:20px;
    margin-bottom:16px;
}

.dash-card h4{
    color:var(--text-color);
    margin-bottom:4px;
    font-weight:700;
}

.dash-card p{
    color:var(--text-color);
    opacity:0.8;
    font-size:0.9rem;
    margin-bottom:12px;
}

/* KPI snapshot cards — small analytics summary row used at the top of
   the dashboards and the candidates page. Purely presentational; the
   values passed in are read from existing session_state / DB data. */
.kpi-row{
    display:flex;
    gap:14px;
    margin-bottom:22px;
    flex-wrap:wrap;
}

.kpi-card{
    flex:1;
    min-width:150px;
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,0.25);
    border-left:4px solid var(--brand-1);
    border-radius:12px;
    padding:14px 16px;
}

.kpi-card .kpi-label{
    font-size:0.76rem;
    text-transform:uppercase;
    letter-spacing:0.04em;
    opacity:0.6;
    color:var(--text-color);
    margin-bottom:4px;
}

.kpi-card .kpi-value{
    font-size:1.3rem;
    font-weight:800;
    color:var(--text-color);
}

.kpi-card.green{ border-left-color:var(--accent-green); }
.kpi-card.amber{ border-left-color:var(--accent-amber); }
.kpi-card.purple{ border-left-color:var(--brand-2); }

/* Small status badges, used alongside the existing st.success/warning/
   error recommendation banners for a quicker-scan summary. */
.badge{
    display:inline-block;
    padding:3px 12px;
    border-radius:999px;
    font-size:0.78rem;
    font-weight:700;
}
.badge-success{ background:rgba(22,163,74,0.15); color:var(--accent-green); }
.badge-warning{ background:rgba(217,119,6,0.15); color:var(--accent-amber); }
.badge-danger{ background:rgba(220,38,38,0.15); color:var(--accent-red); }

/* Buttons - rounded, professional. Covers both st.button (rendered in a
   div.stButton wrapper) and st.form_submit_button (a *different* wrapper,
   div.stFormSubmitButton) — without the second selector, form-submit
   buttons (login, sign-up, Settings' Save Changes) silently fell back to
   Streamlit's plain defaults: 8px radius, 4px/12px padding, regular
   weight, instead of matching every other button in the app. */
div.stButton > button,
div.stFormSubmitButton > button{
    border-radius:10px;
    padding:0.5rem 1.2rem;
    font-weight:600;
    border:1px solid rgba(128,128,128,0.25);
    transition:border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

/* Only secondary-kind buttons get the blue hover treatment. Primary
   buttons (kind="primary"/"primaryFormSubmit") keep their own red
   identity from Streamlit's theme — this used to apply unconditionally
   to every button, which meant hovering a primary button tinted its
   text blue on top of its own red background. */
button[kind="secondary"]:hover,
button[kind="secondaryFormSubmit"]:hover{
    border-color:#2563EB;
    color:#2563EB;
}

/* Metric widgets — subtle card treatment so KPI/score numbers stand out
   consistently with the rest of the dashboard card language. */
div[data-testid="stMetric"]{
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,0.2);
    border-radius:12px;
    padding:10px 14px;
}

/* Progress bars — brand-colored fill instead of the default theme color,
   so match scores and evaluation metrics visually tie back to the hero. */
div[data-testid="stProgress"] > div > div{
    background:linear-gradient(90deg, var(--brand-1), var(--brand-2));
}

/* Recording status pill */
.status-pill{
    display:inline-block;
    padding:6px 16px;
    border-radius:999px;
    font-weight:600;
    font-size:0.85rem;
}

.status-recording{
    background:rgba(220,38,38,0.15);
    color:#DC2626;
}

.status-idle{
    background:rgba(107,114,128,0.15);
    color:#6B7280;
}

/* Sidebar branding */
.sidebar-brand{
    font-weight:800;
    font-size:1.05rem;
    background:linear-gradient(135deg, var(--brand-1), var(--brand-2));
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    margin-bottom:2px;
}

.sidebar-user-card{
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,0.25);
    border-radius:12px;
    padding:12px 14px;
    margin-bottom:8px;
}

/* Visually hidden, but still announced by screen readers — standard
   "sr-only" pattern (as opposed to display:none, which hides content
   from assistive tech too, not just sighted users). */
.sr-only{
    position:absolute;
    width:1px;
    height:1px;
    padding:0;
    margin:-1px;
    overflow:hidden;
    clip:rect(0,0,0,0);
    white-space:nowrap;
    border:0;
}

/* Step indicator */
.stepper{
    display:flex;
    align-items:center;
    margin-bottom:28px;
}
.step{
    display:flex;
    align-items:center;
    gap:8px;
    flex-shrink:0;
}
.step-circle{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width:26px;
    height:26px;
    border-radius:50%;
    font-size:0.8rem;
    font-weight:700;
    border:2px solid rgba(128,128,128,0.35);
    color:var(--text-color);
    opacity:0.55;
    flex-shrink:0;
}
.step-label{
    font-size:0.88rem;
    font-weight:600;
    color:var(--text-color);
    opacity:0.55;
    white-space:nowrap;
}
.step-active .step-circle{
    border-color:#2563EB;
    background:#2563EB;
    color:#FFFFFF;
    opacity:1;
}
.step-active .step-label{ opacity:1; }
.step-done .step-circle{
    border-color:#16A34A;
    background:#16A34A;
    color:#FFFFFF;
    opacity:1;
}
.step-done .step-label{ opacity:0.85; }
.step-line{
    flex:1;
    height:2px;
    background:rgba(128,128,128,0.25);
    margin:0 12px;
    min-width:16px;
}

/* Completed-step summary row */
.step-summary{
    padding:8px 0;
    font-size:0.95rem;
    color:var(--text-color);
}

/* Footer */
.footer{
    text-align:center;
    color:var(--text-color);
    opacity:0.6;
    margin-top:50px;
    font-size:0.85rem;
    border-top:1px solid rgba(128,128,128,0.2);
    padding-top:20px;
}

/* Responsive: phones (~<=600px, e.g. the 375px viewport of most phones
   in portrait). Streamlit's own st.columns already stacks vertically
   below its own breakpoint for free — these rules only cover the
   custom-HTML pieces above that Streamlit doesn't handle for us. */
@media (max-width: 600px){

    .hero{
        padding:28px 22px;
    }
    .hero h1{
        font-size:1.7rem;
    }
    .hero h2{
        font-size:1.05rem;
    }
    .hero p{
        font-size:0.95rem;
    }

    /* The stepper's text labels are redundant on a phone-width screen
       (the active step's name is already the card heading right below
       it, and a finished step's name reappears in its own completed-step
       summary row) — measured 502px of content trying to fit a 343px
       container at 375px viewport width, silently clipping step 3
       entirely. Dropping the label leaves just the connected circles,
       which comfortably fit any phone width. */
    .step-label{
        display:none;
    }
    .step-line{
        min-width:12px;
        margin:0 6px;
    }
    .step-circle{
        width:22px;
        height:22px;
        font-size:0.72rem;
    }

    .kpi-row{
        gap:10px;
    }
    .kpi-card{
        min-width:130px;
        padding:12px 14px;
    }
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

def show_sidebar():
    with st.sidebar:
        st.markdown('<div class="sidebar-brand">🎯 AI Interview Intelligence</div>', unsafe_allow_html=True)
        st.caption("Prepare Smarter. Hire Better.")

        if _db_configured():
            st.caption("💾 Database connected")
        else:
            st.caption("⚠️ Database not configured — log in/sign up won't work until DATABASE_URL is set.")

        st.write("")

        user = st.session_state.auth_user
        if user:
            # name/email are signup-form free text — a user could type
            # something like <img src=x onerror=...> as their own name.
            # This card is only ever shown to that same logged-in user (no
            # other page renders another user's name via unsafe_allow_html),
            # so the practical exposure is self-XSS, but html.escape() is
            # the correct fix regardless — never trust free text going into
            # unsafe_allow_html, no matter who ends up viewing it.
            safe_name = html.escape(user["name"])
            safe_email = html.escape(user["email"])
            st.markdown(
                f"""
                <div class="sidebar-user-card">
                    <div style="font-weight:700;">👤 {safe_name}</div>
                    <div style="font-size:0.82rem; opacity:0.7;">{safe_email}</div>
                    <span class="badge badge-success" style="margin-top:6px; display:inline-block;">
                        {user['role'].title()}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if user and not user.get("is_verified", True):
            st.warning("⚠️ Please verify your email address.")
            preview = st.session_state.dev_email_preview
            if preview:
                st.caption(f"Dev mode — link that would be emailed to {html.escape(preview['to'])}:")
                st.code(preview["link"])
            if st.button("Resend verification email", use_container_width=True, key="resend_verify"):
                raw_token = safe_call(db_repo.create_email_verification_token, user_id=user["id"])
                if raw_token is not None:
                    link = auth_ui.build_verify_link(raw_token)
                    sent = email_service.send_verification_email(to=user["email"], link=link)
                    st.session_state.dev_email_preview = {"to": sent.to, "link": sent.link}
                    st.rerun()
                else:
                    st.error("Could not resend — database not configured.")

        st.write("")

        if user:
            # A logged-in user's role is fixed (email is globally unique —
            # one account can never be both a student and a recruiter), so
            # there's no reason to keep showing the other portal's picker
            # once logged in. "Home" is dropped too: it does nothing but
            # bounce straight back to "Dashboard" for a logged-in user.
            if st.button("📊 Dashboard", use_container_width=True, key="nav_dashboard"):
                go_to(user["role"])

            # Practice Interviews / Previous Sessions are candidate-only
            # concepts — a recruiter never takes their own practice
            # interview, and a session history scoped to the logged-in
            # user's own completed sessions will never have any for a
            # recruiter. Recruiters get Candidates instead: their own
            # screening history.
            if user["role"] == "student":
                if st.button("🎙️ Practice Interviews", use_container_width=True, key="nav_interview"):
                    go_to("interview")
                if st.button("🗂️ Previous Sessions", use_container_width=True, key="nav_report"):
                    go_to("report")
            else:
                if st.button("🧑‍🤝‍🧑 Candidates", use_container_width=True, key="nav_candidates"):
                    go_to("candidates")
            if st.button("⚙️ Settings", use_container_width=True, key="nav_settings"):
                go_to("settings")
        else:
            if st.button("🏠 Home", use_container_width=True, key="nav_home"):
                go_to("home")
            if st.button("🧑‍💼 Recruiter", use_container_width=True, key="nav_recruiter"):
                st.session_state.pending_role = "recruiter"
                go_to("recruiter")
            if st.button("🎓 Student", use_container_width=True, key="nav_student"):
                st.session_state.pending_role = "student"
                go_to("student")

        st.write("")
        st.divider()
        if st.button("ℹ️ About", use_container_width=True, key="nav_about"):
            go_to("about")


# =========================================================
# HOME PAGE
# =========================================================

def show_home():

    # ---- Hero Section ----
    st.markdown("""
    <div class="hero">
        <h1>AI Interview Intelligence Platform</h1>
        <h2>Prepare Smarter. Hire Better.</h2>
        <p>AI-powered recruitment intelligence platform with interview preparation
        tools for candidates.</p>
    </div>
    """, unsafe_allow_html=True)

    # ---- Feature highlights ----
    f1, f2, f3, f4 = st.columns(4)
    features = [
        ("📄", "Resume Parsing", "Extract skills and experience instantly."),
        ("🎯", "Skill Gap Analysis", "See exactly where you match a role."),
        ("🎙️", "Voice Interviews", "Practice with realistic mock interviews."),
        ("📊", "AI Scoring", "Get detailed, data-driven feedback."),
    ]
    for col, (icon, title, desc) in zip((f1, f2, f3, f4), features):
        with col:
            st.markdown(f"""
            <div class="offer-card">
                <span class="offer-icon">{icon}</span>
                <h4>{title}</h4>
                <p>{desc}</p>
            </div>
            """, unsafe_allow_html=True)

    # ---- Portal Cards ----
    # h3, not the page-title h1 used elsewhere: this page already has its
    # own h1/h2 in the hero above, so this is a subsection heading, not
    # the page title.
    st.markdown('<h3 class="section-title">Choose Your Portal</h3>', unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.markdown("""
        <div class="portal-card">
            <h3>🧑‍💼 Recruiter Portal</h3>
            <ul>
                <li>Upload Job Description</li>
                <li>Resume Skill Matching</li>
                <li>AI Resume Screening</li>
                <li>Generate Interview Questions</li>
                <li>Candidate Reports</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Start as Recruiter", use_container_width=True, key="start_recruiter"):
            st.session_state.pending_role = "recruiter"
            go_to("recruiter")

    with right:
        st.markdown("""
        <div class="portal-card">
            <h3>🎓 Student Portal</h3>
            <ul>
                <li>Resume Upload</li>
                <li>Skill Gap Analysis</li>
                <li>Mock Interview</li>
                <li>Voice Interview Practice</li>
                <li>Performance Reports</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Start as Student", use_container_width=True, key="start_student"):
            st.session_state.pending_role = "student"
            go_to("student")


# =========================================================
# AUTH PAGE (Log In / Sign Up)
# =========================================================

def show_auth_page():
    target_role = st.session_state.pending_role or st.session_state.page
    if target_role not in ("student", "recruiter"):
        target_role = "student"
    user = auth_ui.render_auth_page(target_role, db_configured=_db_configured())
    if user is not None:
        _log_in_user(user)


# =========================================================
# SETTINGS PAGE (formerly "Profile" — same page, reframed:
# this is where Profile-editing and (eventually) any other
# account-level preferences live, instead of a bare standalone
# profile page with no clear place for anything else)
# =========================================================

def show_settings():
    user = st.session_state.auth_user
    if user is None:
        show_auth_page()
        return

    st.markdown('<h1 class="section-title">Settings</h1>', unsafe_allow_html=True)

    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    with st.form("profile_form"):
        name = st.text_input("Full Name", value=user["name"])
        st.text_input("Email", value=user["email"], disabled=True,
                       help="Email is your login identifier and can't be changed here.")
        phone_number = st.text_input("Phone Number", value=user.get("phone_number") or "")
        st.text_input("Account Type", value=user["role"].title(), disabled=True)
        save_clicked = st.form_submit_button(
            "Save Changes", use_container_width=True, type="primary"
        )

    if save_clicked:
        updated = safe_call(
            db_repo.update_user_profile,
            user_id=user["id"],
            name=name,
            phone_number=phone_number,
        )
        if updated is not None:
            st.session_state.auth_user["name"] = updated.name
            st.session_state.auth_user["phone_number"] = updated.phone_number
            st.success("Profile updated.")
        else:
            st.error("Could not update profile — database not configured.")
    st.markdown('</div>', unsafe_allow_html=True)

    if not user.get("has_password"):
        with st.container(key="set_password_card"):
            st.markdown("#### Security")
            st.caption(
                "Your account currently signs in with Google only. Add a "
                "password to also be able to sign in with your email."
            )
            with st.form("set_password_form"):
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                set_clicked = st.form_submit_button(
                    "Set Password", use_container_width=True, type="primary"
                )

            if set_clicked:
                if not auth_validation.passwords_match(new_password, confirm_password):
                    st.error("Passwords do not match.")
                else:
                    violations = auth_validation.validate_password_strength(new_password)
                    if violations:
                        st.error("Password must have: " + "; ".join(violations) + ".")
                    else:
                        updated = safe_call(
                            db_repo.set_password, user_id=user["id"], password=new_password,
                        )
                        if updated is not None:
                            st.session_state.auth_user["has_password"] = True
                            st.success(
                                "Password set. You can now log in with your "
                                "email and this password too."
                            )
                        else:
                            st.error("Could not set your password — database not configured.")

    st.write("")
    if st.button("Log Out", use_container_width=True):
        _log_out_user()
        st.rerun()


# =========================================================
# STUDENT DASHBOARD
# =========================================================

def show_student_dashboard():

    st.markdown('<h1 class="section-title">Dashboard</h1>', unsafe_allow_html=True)
    st.caption("Complete these steps to generate your personalized mock interview.")
    st.write("")

    # ---- KPI Snapshot ----
    resume_status = "Uploaded" if st.session_state.parsed_resume else "Not yet"
    jd_status = "Uploaded" if st.session_state.parsed_jd else "Not yet"
    match_score = (
        f"{st.session_state.recruiter_match_result['recruiter_match_score']:.0f}%"
        if st.session_state.recruiter_match_result else "—"
    )
    q_count = len(st.session_state.questions) if st.session_state.questions else 0

    st.markdown(f"""
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">Resume</div>
            <div class="kpi-value">{resume_status}</div>
        </div>
        <div class="kpi-card purple">
            <div class="kpi-label">Job Description</div>
            <div class="kpi-value">{jd_status}</div>
        </div>
        <div class="kpi-card green">
            <div class="kpi-label">Match Score</div>
            <div class="kpi-value">{match_score}</div>
        </div>
        <div class="kpi-card amber">
            <div class="kpi-label">Questions Ready</div>
            <div class="kpi-value">{q_count}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    step = _student_current_step()
    _render_stepper(["Resume", "Job Description", "Generate Questions"], min(step, 3))
    st.write("")

    # ---- Step 1: Resume ----
    if step == 1:
        _render_resume_upload_step(
            heading="Upload your resume",
            description="PDF or DOCX — we'll extract your skills, projects, and experience.",
            button_label="Parse Resume",
            button_key="parse_resume_btn",
        )
        return

    _render_completed_step(
        "Resume",
        f"{st.session_state.parsed_resume.get('name') or 'Candidate'} · "
        f"{len(st.session_state.parsed_resume.get('skills', []))} skills found",
        "Change",
        [
            "parsed_resume", "resume_raw_text", "resume_db_id",
            "match_db_id", "recruiter_match_result", "recruiter_match_error",
        ],
        "change_resume_btn",
    )

    # ---- Step 2: Job description ----
    if step == 2:
        _render_jd_upload_step(
            heading="Add the job description",
            button_key="parse_jd_student_btn",
            on_success=_run_skill_gap,
        )
        return

    _render_completed_step(
        "Job description",
        st.session_state.parsed_jd.get("role") or "Role parsed",
        "Change",
        [
            "parsed_jd", "jd_raw_text", "jd_db_id",
            "match_db_id", "recruiter_match_result", "recruiter_match_error",
            "questions", "question_set_db_id", "question_db_ids",
        ],
        "change_jd_btn",
    )

    # ---- Match result (auto-computed once resume + JD are both in) ----
    _render_recruiter_match_card(heading="Skill match", show_recommendation=False)

    # ---- Step 3: Generate questions ----
    if step == 3:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown("#### Generate your interview questions")
        difficulty = st.selectbox(
            "Difficulty", ["easy", "medium", "hard"], index=1, key="student_difficulty"
        )
        question_count = st.number_input(
            "Number of questions", min_value=1, max_value=20, value=5, key="student_q_count"
        )
        if st.button(
            "Generate Interview Questions", use_container_width=True,
            type="primary", key="student_gen_q_btn",
        ):
            _generate_questions(difficulty, int(question_count), use_resume=True)
            if st.session_state.questions:
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ---- Step 4: Ready to practice ----
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown(f"#### ✅ {len(st.session_state.questions)} questions ready")
    st.markdown("You're ready to start your mock interview.")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(
            "Start Practice Interview", use_container_width=True,
            type="primary", key="start_interview_btn",
        ):
            st.session_state.current_question_index = 0
            go_to("interview")
    with col_b:
        if st.button(
            "Generate a Different Set", use_container_width=True,
            key="regen_questions_btn",
        ):
            st.session_state.questions = None
            st.session_state.question_set_db_id = None
            st.session_state.question_db_ids = []
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    if st.button("View Previous Reports", key="view_reports_btn"):
        go_to("report")


# =========================================================
# RECRUITER DASHBOARD
# =========================================================

def show_recruiter_dashboard():

    st.markdown('<h1 class="section-title">Dashboard</h1>', unsafe_allow_html=True)
    st.caption("Screen a candidate against a job description and generate interview questions.")
    st.write("")

    # ---- KPI Snapshot ----
    jd_status = "Uploaded" if st.session_state.parsed_jd else "Not yet"
    resume_status = "Uploaded" if st.session_state.parsed_resume else "Not yet"
    match_score = (
        f"{st.session_state.recruiter_match_result['recruiter_match_score']:.0f}%"
        if st.session_state.recruiter_match_result else "—"
    )
    q_count = len(st.session_state.questions) if st.session_state.questions else 0

    st.markdown(f"""
    <div class="kpi-row">
        <div class="kpi-card purple">
            <div class="kpi-label">Job Description</div>
            <div class="kpi-value">{jd_status}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Candidate Resume</div>
            <div class="kpi-value">{resume_status}</div>
        </div>
        <div class="kpi-card green">
            <div class="kpi-label">Match Score</div>
            <div class="kpi-value">{match_score}</div>
        </div>
        <div class="kpi-card amber">
            <div class="kpi-label">Questions Ready</div>
            <div class="kpi-value">{q_count}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    step = _recruiter_current_step()
    _render_stepper(["Job Description", "Candidate Resume", "Match & Questions"], step)
    st.write("")

    # ---- Step 1: Job description ----
    if step == 1:
        _render_jd_upload_step(
            heading="Upload the job description",
            button_key="parse_jd_recruiter_btn",
        )
        return

    _render_completed_step(
        "Job description",
        st.session_state.parsed_jd.get("role") or "Role parsed",
        "Change",
        [
            "parsed_jd", "jd_raw_text", "jd_db_id",
            "match_db_id", "recruiter_match_result", "recruiter_match_error",
            "parsed_resume", "resume_raw_text", "resume_db_id",
            "questions", "question_set_db_id", "question_db_ids",
        ],
        "recruiter_change_jd_btn",
    )

    # ---- Step 2: Candidate resume ----
    if step == 2:
        _render_resume_upload_step(
            heading="Upload the candidate's resume",
            description="PDF or DOCX — we'll screen it against the job description above.",
            button_label="Screen Candidate",
            button_key="recruiter_parse_resume_btn",
            on_success=_run_skill_gap,
        )
        return

    _render_completed_step(
        "Candidate",
        st.session_state.parsed_resume.get("name") or "Candidate",
        "Screen a different candidate",
        [
            "parsed_resume", "resume_raw_text", "resume_db_id",
            "match_db_id", "recruiter_match_result", "recruiter_match_error",
            "questions", "question_set_db_id", "question_db_ids",
        ],
        "recruiter_change_resume_btn",
    )

    # ---- Step 3: Match + generate questions ----
    _render_recruiter_match_card(heading="Match result", show_recommendation=True)

    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    if not st.session_state.questions:
        st.markdown("#### Generate interview questions for this candidate")
        difficulty = st.selectbox(
            "Difficulty", ["easy", "medium", "hard"], index=1, key="recruiter_difficulty"
        )
        question_count = st.number_input(
            "Number of questions", min_value=1, max_value=20, value=5, key="recruiter_q_count"
        )
        if st.button(
            "Generate Questions", use_container_width=True,
            type="primary", key="recruiter_gen_q",
        ):
            # Personalized against this specific candidate's resume, now that
            # the guided flow guarantees one is already on hand at this point
            # (previously this was a parallel, order-independent action that
            # never had a resume to draw on).
            _generate_questions(difficulty, int(question_count), use_resume=True)
            if st.session_state.questions:
                st.rerun()
    else:
        st.markdown(f"#### ✅ {len(st.session_state.questions)} interview questions generated")
        for i, q in enumerate(st.session_state.questions, start=1):
            with st.expander(f"Q{i}. {q['question']}", expanded=False):
                st.caption(
                    f"Category: {q.get('category', '—')} · "
                    f"Difficulty: {q.get('difficulty', '—')}"
                )
                if q.get("reason"):
                    st.markdown(f"**Why this question:** {q['reason']}")
        st.write("")
        if st.button(
            "Screen Another Candidate", use_container_width=True,
            type="primary", key="recruiter_screen_another",
        ):
            for key in (
                "parsed_resume", "resume_raw_text", "resume_db_id",
                "match_db_id", "recruiter_match_result", "recruiter_match_error",
                "questions", "question_set_db_id",
            ):
                st.session_state[key] = None
            st.session_state.question_db_ids = []
            st.session_state.resume_uploader_version += 1
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    if st.button("View Candidate Reports", key="recruiter_view_reports_btn"):
        go_to("candidates")


# =========================================================
# CANDIDATES SCREEN (recruiter-only)
# ---------------------------------------------------------
# The recruiter-side counterpart to Interview/Report — those two screens
# are about a user taking their own practice interview, which is a
# candidate concept a recruiter never does themselves. This is a real
# history of the candidates *they've screened* (resume vs. JD match),
# not the same page repurposed.
# =========================================================

def show_candidates():
    st.markdown('<h1 class="section-title">Candidates</h1>', unsafe_allow_html=True)

    user_id = st.session_state.db_user_id
    screenings = (
        safe_call(db_repo.list_recent_candidate_screenings, user_id=user_id, limit=20)
        if user_id is not None else None
    )

    if not screenings:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown("#### No candidates screened yet")
        st.markdown(
            "Screen a candidate's resume against a job description from "
            "your Dashboard to see them listed here."
        )
        if st.button("Go to Dashboard", type="primary"):
            go_to("recruiter")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    st.caption(f"{len(screenings)} candidate(s) screened, most recent first.")
    st.write("")

    # ---- KPI Snapshot ----
    # Average Score intentionally removed: a single blended average across
    # candidates screened for different roles/JDs isn't a meaningful
    # number and risks misleading a recruiter about any one candidate.
    scores = [entry["score"] for entry in screenings]
    shortlisted = sum(1 for s in scores if s >= 60)

    st.markdown(f"""
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">Candidates Screened</div>
            <div class="kpi-value">{len(screenings)}</div>
        </div>
        <div class="kpi-card purple">
            <div class="kpi-label">Shortlisted</div>
            <div class="kpi-value">{shortlisted} / {len(screenings)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    trend_df = pd.DataFrame(
        {"Candidate": [f"#{i + 1}" for i in range(len(scores))],
         "Match Score": list(reversed(scores))}
    )
    _labeled_bar_chart(
        trend_df, x="Candidate", y="Match Score",
        x_title="Candidate (most recent screenings)", y_title="Match Score (/100)",
        color="#1D4ED8",
    )
    st.write("")

    for entry in screenings:
        when = (entry.get("created_at") or "")[:19].replace("T", " ")
        recommendation, kind = _match_recommendation(entry["score"])
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown(f"#### {entry['candidate_name']}")
        st.caption(f"{entry['role_context']} · {when}")
        st.progress(min(entry["score"], 100) / 100)
        st.markdown(f"**{entry['score']:.0f} / 100**")
        getattr(st, kind)(recommendation)
        st.markdown('</div>', unsafe_allow_html=True)


# =========================================================
# INTERVIEW SCREEN
# =========================================================

def show_interview():

    st.markdown('<h1 class="section-title">Practice Interview</h1>', unsafe_allow_html=True)

    if not st.session_state.questions:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown("#### No practice questions yet")
        st.markdown(
            "Generate a personalized set of interview questions from your "
            "Dashboard first, then come back here to practice."
        )
        if st.button("Go to Dashboard", type="primary"):
            go_to(st.session_state.auth_user["role"])
        st.markdown('</div>', unsafe_allow_html=True)
        return

    questions = [q["question"] for q in st.session_state.questions]

    # Lazily create the DB-backed interview session once, on first entry.
    _ensure_interview_session_db_id()

    total_questions = len(questions)
    q_index = st.session_state.current_question_index
    if q_index < 0 or q_index >= total_questions:
        # A stale index from a previous, longer question set (e.g. after
        # logout or a fresh/shorter question set) would otherwise index
        # past the end of `questions` below and crash the page.
        q_index = 0
        st.session_state.current_question_index = 0

    st.progress((q_index + 1) / total_questions if total_questions else 0)

    st.markdown('<div class="dash-card">', unsafe_allow_html=True)

    st.markdown(f"**Question {q_index + 1} of {total_questions}**")
    st.markdown(f"### {questions[q_index]}")

    meta = st.session_state.questions[q_index]
    st.caption(f"Category: {meta.get('category', '—')} · Difficulty: {meta.get('difficulty', '—')}")

    st.write("")

    # ---- Recording Status ----
    if st.session_state.is_recording:
        st.markdown('<span class="status-pill status-recording">Recording in progress</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill status-idle">Not recording</span>', unsafe_allow_html=True)

    st.write("")

    # ---- Voice Answer ----
    st.markdown("**Record Your Answer**")
    audio = st.audio_input("Record your answer", key=f"audio_{q_index}")

    if audio is not None:
        if st.button("Transcribe Recording", key=f"transcribe_{q_index}"):
            try:
                with st.spinner("Transcribing..."):
                    text = transcribe_audio_bytes(audio.getvalue())
                st.session_state.answers[q_index] = text
                st.success("Transcribed. You can edit the text below before submitting.")
            except TranscriptionError as exc:
                st.error(str(exc))

    st.write("")

    # ---- Transcript / Answer Area ----
    st.markdown("**Your Answer** (transcribed, or type directly)")
    answer_text = st.text_area(
        "Answer",
        value=st.session_state.answers.get(q_index, ""),
        height=120,
        key=f"answer_text_{q_index}"
    )
    st.session_state.answers[q_index] = answer_text

    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")

    # ---- Controls ----
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        if st.button("Start Recording", use_container_width=True):
            st.session_state.is_recording = True
            st.rerun()

    with c2:
        if st.button("Stop Recording", use_container_width=True):
            st.session_state.is_recording = False
            st.rerun()

    with c3:
        if st.button("Submit Answer", use_container_width=True):
            candidate_answer = st.session_state.answers.get(q_index, "").strip()

            # Speak-then-submit path: if a voice recording was made but
            # never manually transcribed (or was cleared), transcribe it
            # now via the speech_to_text module before evaluating — no
            # separate "Transcribe Recording" click required.
            if not candidate_answer and audio is not None:
                try:
                    with st.spinner("Transcribing your recording..."):
                        candidate_answer = transcribe_audio_bytes(audio.getvalue()).strip()
                    st.session_state.answers[q_index] = candidate_answer
                except TranscriptionError as exc:
                    st.error(f"Could not transcribe your recording: {exc}")
                    candidate_answer = ""

            if not candidate_answer:
                st.warning("Please record or type an answer before submitting.")
            else:
                job_role, required_skills = _job_role_and_skills()
                try:
                    with st.spinner("Evaluating answer..."):
                        evaluation = evaluate_answer(
                            question=questions[q_index],
                            candidate_answer=candidate_answer,
                            job_role=job_role,
                            required_skills=required_skills,
                        ).model_dump()
                    st.session_state.evaluations[q_index] = evaluation
                    st.success(
                        f"Answer submitted and evaluated — score: "
                        f"{evaluation.get('overall_score', 'N/A')}/100"
                    )

                    session_db_id = _ensure_interview_session_db_id()
                    if session_db_id is not None:
                        question_db_ids = st.session_state.question_db_ids
                        question_db_id = (
                            question_db_ids[q_index]
                            if q_index < len(question_db_ids)
                            else None
                        )
                        saved_answer = safe_call(
                            db_repo.save_answer,
                            interview_session_id=session_db_id,
                            question_id=question_db_id,
                            question_text=questions[q_index],
                            answer_text=candidate_answer,
                            transcript_text=st.session_state.answers.get(q_index),
                        )
                        if saved_answer is not None:
                            safe_call(
                                db_repo.save_evaluation,
                                answer_id=saved_answer.id,
                                evaluation_json=evaluation,
                            )
                except AnswerEvaluationProcessingError as exc:
                    st.error(f"Could not evaluate answer: {exc}")

    with c4:
        if st.button("Next Question", use_container_width=True):
            if q_index < total_questions - 1:
                st.session_state.current_question_index += 1
                st.session_state.is_recording = False
                st.rerun()
            else:
                go_to("report")

    if q_index in st.session_state.evaluations:
        with st.expander("Evaluation for this question"):
            ev = st.session_state.evaluations[q_index]
            st.write(ev)


# =========================================================
# REPORT SCREEN
# =========================================================

def _show_report_history():
    """Show past interview reports for this demo user, if the DB has any."""
    user_id = st.session_state.db_user_id
    if user_id is None:
        return

    reports = safe_call(db_repo.list_recent_reports, user_id=user_id, limit=5)
    if not reports:
        return

    st.write("")
    st.markdown("#### Report History")

    if len(reports) > 1:
        history_df = pd.DataFrame(
            {"Session": [f"Session {i + 1}" for i in range(len(reports))],
             "Score": [r["overall_score"] for r in reversed(reports)]}
        )
        _labeled_bar_chart(
            history_df, x="Session", y="Score",
            x_title="Practice session", y_title="Overall Score (/100)",
            color="#7C3AED",
        )

    for entry in reports:
        role = entry.get("role_context") or "General Role"
        when = (entry.get("created_at") or "")[:19].replace("T", " ")
        st.markdown(f"- **{role}** — {entry['overall_score']:.0f}/100 · {when}")


def show_report():

    st.markdown('<h1 class="section-title">Practice Result</h1>', unsafe_allow_html=True)

    evaluations = st.session_state.evaluations

    if not evaluations:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown("#### No completed practice interview yet")
        st.markdown(
            "Finish answering at least one question in a practice interview "
            "to see your AI-scored results here."
        )
        if st.session_state.auth_user is not None:
            if st.button("Go to Dashboard", type="primary"):
                go_to(st.session_state.auth_user["role"])
        st.markdown('</div>', unsafe_allow_html=True)
        _show_report_history()
        return

    # ---- Real evaluation data available ----
    st.caption("Scores generated by the AI evaluation module for this session.")
    st.write("")

    metric_keys = ["correctness", "keyword_coverage", "clarity", "communication", "completeness"]
    n = len(evaluations)
    overall_avg = sum(ev.get("overall_score", 0) for ev in evaluations.values()) / n

    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.metric("Overall Score (avg)", f"{overall_avg:.0f} / 100")
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")

    st.markdown("#### Evaluation Metrics (average)")
    max_map = {"correctness": 30, "keyword_coverage": 25, "clarity": 20,
               "communication": 15, "completeness": 10}
    average_scores = {}
    for key in metric_keys:
        avg_val = sum(ev.get(key, 0) for ev in evaluations.values()) / n
        average_scores[key] = avg_val
        max_val = max_map[key]
        pct = (avg_val / max_val) if max_val else 0
        st.markdown(f"**{key.replace('_', ' ').title()}** — {avg_val:.1f}/{max_val}")
        st.progress(min(max(pct, 0), 1))

    st.write("")
    st.markdown("#### Score Trend Across Questions")
    trend_df = pd.DataFrame(
        {"Question": [f"Q{i + 1}" for i in sorted(evaluations.keys())],
         "Score": [evaluations[i].get("overall_score", 0) for i in sorted(evaluations.keys())]}
    )
    _labeled_line_chart(
        trend_df, x="Question", y="Score",
        x_title="Question", y_title="Overall Score (/100)",
        color="#1D4ED8",
    )

    recommendation, kind = _match_recommendation(overall_avg)
    badge_class = {"success": "badge-success", "warning": "badge-warning", "error": "badge-danger"}[kind]
    st.markdown(f'<span class="badge {badge_class}">{recommendation}</span>', unsafe_allow_html=True)

    st.write("")
    st.markdown("#### Per-Question Breakdown")
    for q_index in sorted(evaluations.keys()):
        ev = evaluations[q_index]
        with st.expander(f"Question {q_index + 1} — score {ev.get('overall_score', 'N/A')}/100"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Strengths**")
                for s in ev.get("strengths", []):
                    st.markdown(f"- {s}")
            with col2:
                st.markdown("**Improvements**")
                for imp in ev.get("improvements", []):
                    st.markdown(f"- {imp}")
            st.markdown("**Feedback**")
            st.write(ev.get("feedback", ""))
            st.markdown("**Ideal Answer**")
            st.write(ev.get("ideal_answer", ""))

    # Persist the report once per interview session.
    if not st.session_state.report_saved and st.session_state.interview_session_db_id:
        recommendation, _ = _match_recommendation(overall_avg)
        saved_report = safe_call(
            db_repo.save_report,
            interview_session_id=st.session_state.interview_session_db_id,
            overall_score=overall_avg,
            summary_json={"question_count": n, "average_scores": average_scores},
            recommendation=recommendation,
        )
        if saved_report is not None:
            safe_call(
                db_repo.complete_interview_session,
                st.session_state.interview_session_db_id,
            )
            st.session_state.report_saved = True

    st.write("")
    if st.button("Download Report", use_container_width=True):
        import json
        report_json = json.dumps(evaluations, indent=2)
        st.download_button(
            "Download JSON Report", data=report_json,
            file_name="interview_report.json", mime="application/json"
        )

    _show_report_history()


# =========================================================
# ABOUT PAGE
# =========================================================

def show_about():
    st.markdown('<h1 class="section-title">About</h1>', unsafe_allow_html=True)
    st.markdown("""
    <div class="dash-card">
        <p>
        The AI Interview Intelligence Platform helps students prepare for
        technical and HR interviews using AI-generated questions, voice-based
        mock interviews, and detailed performance evaluation. Recruiters can
        use the same intelligence to generate role-specific questions,
        conduct candidate interviews, and evaluate results consistently.
        </p>
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# FOOTER
# =========================================================

def show_footer():
    st.markdown("""
    <div class="footer">
    Built with Python, Streamlit, AI, and Speech Recognition.
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# MAIN ROUTER
# =========================================================

def main():
    _handle_auth_token_query_params()
    _sync_google_login()
    _enforce_session_idle_timeout()
    show_sidebar()
    _render_auth_flash()

    page = st.session_state.page
    logged_in = st.session_state.auth_user is not None

    if page in _PROTECTED_PAGES and not logged_in:
        show_auth_page()
    elif page == "home":
        # A logged-in user has already picked a portal — send them straight
        # to their workspace instead of back through the marketing landing.
        if logged_in:
            go_to(st.session_state.auth_user["role"])
        else:
            show_home()
    elif page == "student":
        # `logged_in` is always True here — the `_PROTECTED_PAGES` branch
        # above already handles the not-logged-in case for this page.
        if st.session_state.auth_user["role"] != "student":
            st.warning(
                "This dashboard is for student accounts. "
                "Log in with a student account below."
            )
            st.session_state.pending_role = "student"
            show_auth_page()
        else:
            show_student_dashboard()
    elif page == "recruiter":
        # `logged_in` is always True here — the `_PROTECTED_PAGES` branch
        # above already handles the not-logged-in case for this page.
        if st.session_state.auth_user["role"] != "recruiter":
            st.warning(
                "This dashboard is for recruiter accounts. "
                "Log in with a recruiter account below."
            )
            st.session_state.pending_role = "recruiter"
            show_auth_page()
        else:
            show_recruiter_dashboard()
    elif page == "interview":
        # Practice Interview is a candidate-only concept — a recruiter
        # reaching this page (e.g. stale session state) gets sent back to
        # their own dashboard rather than shown someone else's workflow.
        if st.session_state.auth_user["role"] != "student":
            go_to(st.session_state.auth_user["role"])
        else:
            show_interview()
    elif page == "report":
        if st.session_state.auth_user["role"] != "student":
            go_to(st.session_state.auth_user["role"])
        else:
            show_report()
    elif page == "candidates":
        if st.session_state.auth_user["role"] != "recruiter":
            go_to(st.session_state.auth_user["role"])
        else:
            show_candidates()
    elif page == "settings":
        show_settings()
    elif page == "about":
        show_about()
    else:
        show_home()

    show_footer()


if __name__ == "__main__":
    main()

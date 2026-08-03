"""
Authentication page: Google Sign-In plus email/password login, signup,
forgot-password, and reset-password — a single centered card, one mode at
a time, switched via st.session_state.auth_mode ("login" | "signup" |
"forgot_password" | "reset_password"). Built entirely in Streamlit +
injected CSS — no other framework. Reuses the same --text-color /
--secondary-background-color theme variables and brand tokens
(--brand-1, --brand-2) as app.py's own CSS block.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

import auth_validation
import email_service
import rate_limiter
from database import repositories as db_repo
from database.connection import DatabaseNotConfigured
from database.exceptions import UserAlreadyExistsError
from database.models import User

try:
    from streamlit.errors import StreamlitAuthError
except ImportError:  # pragma: no cover - only relevant on Streamlit < 1.42
    class StreamlitAuthError(Exception):
        """Fallback so render_auth_page still works without OIDC support."""


def _inject_auth_css() -> None:
    st.markdown(
        """
<style>
/* Targets the real Streamlit container wrapper (st.container(key="auth_card")),
   not a hand-rolled div — Streamlit renders each separate st.markdown call
   as an isolated HTML fragment, so an unclosed <div> spanning multiple
   calls would never actually nest the widgets in between; only a real
   Streamlit container guarantees true nesting for a multi-widget card. */
.st-key-auth_card{
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,0.25);
    border-top:5px solid var(--auth-accent, var(--brand-1));
    border-radius:24px;
    padding:0 40px 40px;
    max-width:480px;
    box-shadow:0 24px 60px -30px rgba(29,78,216,0.35);
    /* Streamlit's own header bar overlays the page (position:absolute,
       z-index far above content, ~60px tall) rather than pushing content
       down — .block-container's own padding-top isn't enough clearance on
       this page since the card is the very first element, so give it
       explicit room here rather than relying on that. */
    margin:32px auto 0;
    animation: auth-fade-in 0.5s ease both;
}

.auth-role-banner{
    margin:0 -40px 24px;
    padding:22px 40px 18px;
    background:linear-gradient(135deg, var(--auth-accent, var(--brand-1)), var(--auth-accent-2, var(--brand-2)));
    border-radius:19px 19px 0 0;
    color:#FFFFFF;
}
.auth-role-banner .auth-logo-mark{
    width:44px; height:44px;
    border-radius:12px;
    display:flex;
    align-items:center;
    justify-content:center;
    background:rgba(255,255,255,0.18);
    font-size:1.3rem;
    margin-bottom:14px;
}
.auth-role-banner .auth-role-name{
    font-size:0.78rem;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:0.06em;
    opacity:0.85;
    margin-bottom:2px;
}
.auth-role-tagline{
    font-size:0.92rem;
    opacity:0.92;
}

.auth-title{
    font-size:1.5rem;
    font-weight:800;
    color:var(--text-color);
    margin:20px 0 18px;
}

.auth-divider{
    display:flex;
    align-items:center;
    gap:12px;
    margin:20px 0;
    color:var(--text-color);
    opacity:0.5;
    font-size:0.78rem;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:0.05em;
}
.auth-divider::before, .auth-divider::after{
    content:"";
    flex:1;
    height:1px;
    background:rgba(128,128,128,0.3);
}

/* Scope button styling to just this page's Google button via Streamlit's
   key -> .st-key-<key> class, instead of the app-wide div.stButton rule. */
.st-key-google_login_btn button{
    display:flex;
    align-items:center;
    justify-content:center;
    gap:10px;
    height:48px;
    font-size:0.95rem;
    border-radius:12px !important;
    background:var(--background-color) !important;
    border:1px solid rgba(128,128,128,0.35) !important;
    color:var(--text-color) !important;
    transition:transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.st-key-google_login_btn button:hover{
    transform:translateY(-1px);
    box-shadow:0 10px 24px -14px rgba(29,78,216,0.45);
    border-color:var(--brand-1) !important;
}
.st-key-google_login_btn button:active{
    transform:translateY(0);
    box-shadow:none;
}
.st-key-google_login_btn button:focus-visible{
    outline:2px solid var(--brand-1);
    outline-offset:2px;
}

/* Mode-switch links (Forgot Password? / Create Account / Login / Back to
   Login) — styled as understated text links, not full buttons. Safe to
   share one rule across these three keys since only one mode's buttons
   are ever mounted at a time. */
.st-key-goto_signup button, .st-key-goto_login button, .st-key-goto_forgot button{
    background:transparent !important;
    border:none !important;
    box-shadow:none !important;
    color:var(--brand-1) !important;
    font-weight:600;
    padding:0 !important;
    height:auto !important;
}
.st-key-goto_signup button:hover, .st-key-goto_login button:hover, .st-key-goto_forgot button:hover{
    text-decoration:underline;
    color:var(--brand-1) !important;
}

.auth-footnote{
    margin-top:20px;
    font-size:0.8rem;
    color:var(--text-color);
    opacity:0.55;
    text-align:center;
}

@keyframes auth-fade-in{
    from{ opacity:0; transform:translateY(10px); }
    to{ opacity:1; transform:translateY(0); }
}

@media (prefers-reduced-motion: reduce){
    .st-key-auth_card{ animation:none; }
    .st-key-google_login_btn button{ transition:none; }
}

@media (max-width: 600px){
    .st-key-auth_card{
        padding:28px 22px;
        border-radius:18px;
    }
}
</style>
""",
        unsafe_allow_html=True,
    )


def _google_auth_configured() -> bool:
    """
    Whether a `[auth]` section exists in `.streamlit/secrets.toml`.

    Streamlit only adds the `is_logged_in` key to `st.user` when an `[auth]`
    section is present at all — on a fresh clone with no secrets configured,
    `st.user.is_logged_in` raises AttributeError, so this must be checked
    via the Mapping `in` protocol, never a bare attribute access.
    """
    return "is_logged_in" in st.user


def _base_url() -> str:
    url = getattr(st.context, "url", None) or "http://localhost:8501"
    return url.split("?")[0]


def build_verify_link(raw_token: str) -> str:
    return f"{_base_url()}?verify_token={raw_token}"


def build_reset_link(raw_token: str) -> str:
    return f"{_base_url()}?reset_token={raw_token}"


def _render_google_section(target_role: str) -> None:
    auth_error = st.session_state.get("google_auth_error")
    if auth_error:
        st.error(auth_error)

    mismatch_role = st.session_state.get("auth_role_mismatch")
    if mismatch_role:
        st.warning(
            f"This account is registered as a {mismatch_role}. "
            f"Use the {mismatch_role.title()} portal to log in."
        )

    if not _google_auth_configured():
        st.info(
            "Google sign-in isn't configured yet. Add a "
            "`.streamlit/secrets.toml` with an `[auth]` section "
            "(see README) to enable it."
        )
        return

    clicked = st.button(
        "Continue with Google",
        key="google_login_btn",
        type="primary",
        use_container_width=True,
    )
    if clicked:
        st.session_state.auth_role_mismatch = None
        st.session_state.google_auth_error = None
        try:
            st.login(target_role)
        except StreamlitAuthError:
            st.error(
                "Google sign-in is temporarily unavailable. "
                "Please try again shortly."
            )


def _render_or_divider() -> None:
    st.markdown('<div class="auth-divider">OR</div>', unsafe_allow_html=True)


def _handle_login_submit(
    email: str, password: str, target_role: str, *, db_configured: bool,
) -> User | None:
    if not email or not password:
        st.error("Enter your email and password.")
        return None
    if not db_configured:
        st.error(
            "Signing in requires a database connection. Set DATABASE_URL "
            "in your .env file, then try again."
        )
        return None

    normalized_email = email.strip().lower()
    if rate_limiter.is_login_blocked(normalized_email):
        st.error("Too many failed attempts. Please try again in a few minutes.")
        return None

    try:
        user = db_repo.authenticate_user(email=email, password=password)
    except DatabaseNotConfigured:
        st.error(
            "Signing in requires a database connection. Set DATABASE_URL "
            "in your .env file, then try again."
        )
        return None
    except SQLAlchemyError:
        st.error(
            "Could not log in — the database is unreachable. Check "
            "DATABASE_URL and that PostgreSQL is running, then try again."
        )
        return None

    if user is None:
        rate_limiter.record_failed_login(normalized_email)
        st.error("Invalid email or password.")
        return None

    if user.role != target_role:
        st.error(
            f"This account is registered as a {user.role}. "
            f"Use the {user.role.title()} portal to log in."
        )
        return None

    rate_limiter.record_successful_login(normalized_email)
    return user


def _render_login_form(target_role: str, *, db_configured: bool) -> User | None:
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

    if st.button("Forgot Password?", key="goto_forgot"):
        st.session_state.auth_mode = "forgot_password"
        st.rerun()

    result_user = None
    if submitted:
        result_user = _handle_login_submit(
            email, password, target_role, db_configured=db_configured,
        )

    st.write("")
    left, right = st.columns([0.62, 0.38])
    with left:
        st.caption("Don't have an account?")
    with right:
        if st.button("Create Account", key="goto_signup", use_container_width=True):
            st.session_state.auth_mode = "signup"
            st.rerun()

    return result_user


def _handle_signup_submit(
    *, name: str, email: str, phone_number: str, password: str, confirm_password: str,
    role: str, terms_accepted: bool, db_configured: bool,
) -> User | None:
    if not name.strip() or not email.strip() or not phone_number.strip() or not password:
        st.error("Full name, email, phone number, and password are required.")
        return None
    if not auth_validation.is_valid_email(email):
        st.error("Enter a valid email address.")
        return None
    if not auth_validation.is_valid_phone(phone_number):
        st.error("Enter a valid phone number (digits only, 7-20 characters).")
        return None
    if not auth_validation.passwords_match(password, confirm_password):
        st.error("Passwords do not match.")
        return None
    violations = auth_validation.validate_password_strength(password)
    if violations:
        st.error("Password must have: " + "; ".join(violations) + ".")
        return None
    if not terms_accepted:
        st.error("Please accept the Terms of Service and Privacy Policy to continue.")
        return None
    if not db_configured:
        st.error(
            "Creating an account requires a database connection. Set "
            "DATABASE_URL in your .env file, then try again."
        )
        return None

    try:
        user = db_repo.create_user(
            name=name, email=email, password=password, role=role,
            phone_number=phone_number.strip(),
        )
    except UserAlreadyExistsError:
        st.error("An account with this email already exists. Please log in instead.")
        return None
    except DatabaseNotConfigured:
        st.error(
            "Creating an account requires a database connection. Set "
            "DATABASE_URL in your .env file, then try again."
        )
        return None
    except SQLAlchemyError:
        st.error(
            "Could not create your account — the database is unreachable. "
            "Check DATABASE_URL and that PostgreSQL is running, then try again."
        )
        return None

    raw_token = db_repo.create_email_verification_token(user_id=user.id)
    link = build_verify_link(raw_token)
    sent = email_service.send_verification_email(to=user.email, link=link)
    # Persisted in session_state (not just rendered inline) because the
    # caller logs this user in immediately after signup, which ends in a
    # rerun that would otherwise discard anything shown in this same pass
    # — the sidebar's "please verify" banner picks this up instead.
    st.session_state.dev_email_preview = {"to": sent.to, "link": sent.link}
    return user


def _render_signup_form(target_role: str, *, db_configured: bool) -> User | None:
    with st.form("signup_form"):
        name = st.text_input("Full Name", placeholder="Jane Doe")
        col_email, col_phone = st.columns(2)
        with col_email:
            email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
        with col_phone:
            phone_number = st.text_input(
                "Phone Number", key="signup_phone", placeholder="+1 555 123 4567",
            )
        col_pw, col_pw2 = st.columns(2)
        with col_pw:
            password = st.text_input("Password", type="password", key="signup_password")
        with col_pw2:
            confirm_password = st.text_input(
                "Confirm Password", type="password", key="signup_confirm_password",
            )
        st.caption("Min. 8 characters, with an uppercase letter, a number, and a symbol.")
        role = st.radio(
            "I'm signing up as a",
            options=["student", "recruiter"],
            format_func=lambda r: "🎓 Student" if r == "student" else "🧑‍💼 Recruiter",
            index=0 if target_role == "student" else 1,
            horizontal=True,
        )
        terms_accepted = st.checkbox(
            "I agree to the Terms of Service and Privacy Policy",
            key="signup_terms",
        )
        submitted = st.form_submit_button(
            "Create Account", use_container_width=True, type="primary",
        )

    result_user = None
    if submitted:
        result_user = _handle_signup_submit(
            name=name, email=email, phone_number=phone_number, password=password,
            confirm_password=confirm_password, role=role,
            terms_accepted=terms_accepted, db_configured=db_configured,
        )

    st.write("")
    left, right = st.columns([0.62, 0.38])
    with left:
        st.caption("Already have an account?")
    with right:
        if st.button("Login", key="goto_login", use_container_width=True):
            st.session_state.auth_mode = "login"
            st.rerun()

    return result_user


def _handle_forgot_password_submit(email: str) -> email_service.SentEmail | None:
    if not email.strip() or not auth_validation.is_valid_email(email):
        st.error("Enter a valid email address.")
        return None

    normalized_email = email.strip().lower()
    if rate_limiter.is_password_reset_blocked(normalized_email):
        st.error("Too many reset requests. Please try again later.")
        return None
    rate_limiter.record_password_reset_request(normalized_email)

    try:
        raw_token = db_repo.create_password_reset_token(email=email)
    except (DatabaseNotConfigured, SQLAlchemyError):
        st.error(
            "Could not process this request — the database is unavailable. "
            "Please try again shortly."
        )
        return None

    # Same message regardless of whether the account exists / has a
    # password yet, to avoid leaking which emails are registered.
    st.success("If that email is registered, a password reset link has been created.")
    if raw_token is None:
        return None

    link = build_reset_link(raw_token)
    return email_service.send_password_reset_email(to=normalized_email, link=link)


def _render_forgot_password_form() -> None:
    st.caption("Enter your email and we'll create a password reset link.")
    with st.form("forgot_password_form"):
        email = st.text_input("Email")
        submitted = st.form_submit_button(
            "Send Reset Link", use_container_width=True, type="primary",
        )

    if submitted:
        sent = _handle_forgot_password_submit(email)
        if sent is not None:
            st.info(
                "Dev mode: no real email provider is configured yet — "
                f"here's the link that would be sent to {sent.to}:"
            )
            st.code(sent.link)

    if st.button("Back to Login", key="goto_login"):
        st.session_state.auth_mode = "login"
        st.rerun()


def _handle_reset_password_submit(
    raw_token: str, new_password: str, confirm_password: str,
) -> bool:
    """Returns True if the password was successfully reset."""
    if not auth_validation.passwords_match(new_password, confirm_password):
        st.error("Passwords do not match.")
        return False
    violations = auth_validation.validate_password_strength(new_password)
    if violations:
        st.error("Password must have: " + "; ".join(violations) + ".")
        return False
    try:
        user = db_repo.consume_password_reset_token(
            raw_token=raw_token, new_password=new_password,
        )
    except (DatabaseNotConfigured, SQLAlchemyError):
        st.error(
            "Could not reset your password — the database is unavailable. "
            "Please try again shortly."
        )
        return False
    if user is None:
        st.error("This password reset link is invalid or has expired.")
        return False
    return True


def _render_reset_password_form() -> None:
    raw_token = st.session_state.get("pending_reset_token")
    if not raw_token:
        st.error("This password reset link is invalid or has expired.")
        if st.button("Back to Login", key="goto_login"):
            st.session_state.auth_mode = "login"
            st.rerun()
        return

    st.caption("Choose a new password for your account.")
    with st.form("reset_password_form"):
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button(
            "Set New Password", use_container_width=True, type="primary",
        )

    if submitted and _handle_reset_password_submit(raw_token, new_password, confirm_password):
        st.session_state.pending_reset_token = None
        st.session_state.auth_mode = "login"
        # A flash (read+cleared by app.py's _render_auth_flash on the next
        # run), not a direct st.success() here — st.rerun() on the next
        # line raises immediately, so a message shown in this same pass
        # would never actually be visible to the user.
        st.session_state.auth_flash = ("success", "Your password has been reset. Please log in.")
        st.rerun()


_ROLE_THEME = {
    "student": {
        "accent": "#1D4ED8",
        "accent_2": "#2563EB",
        "icon": "🎓",
        "label": "Student Portal",
        "tagline": "AI-personalized mock interviews, tailored to your resume and target role.",
    },
    "recruiter": {
        "accent": "#7C3AED",
        "accent_2": "#9333EA",
        "icon": "🧑‍💼",
        "label": "Recruiter Portal",
        "tagline": "Evidence-based candidate screening and role-specific interview questions.",
    },
}


def _render_role_banner(target_role: str) -> None:
    theme = _ROLE_THEME.get(target_role, _ROLE_THEME["student"])
    # Sets --auth-accent / --auth-accent-2 as inline CSS custom properties
    # on the card container itself, so the top border + banner gradient
    # (defined once in _inject_auth_css) pick up the right color per role
    # without duplicating the whole card's CSS for each role.
    st.markdown(
        f'<style>.st-key-auth_card{{ --auth-accent:{theme["accent"]}; '
        f'--auth-accent-2:{theme["accent_2"]}; }}</style>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="auth-role-banner">
            <div class="auth-logo-mark">{theme['icon']}</div>
            <div class="auth-role-name">{theme['label']}</div>
            <div class="auth-role-tagline">{theme['tagline']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_auth_card(target_role: str, *, db_configured: bool) -> User | None:
    mode = st.session_state.get("auth_mode", "login")
    titles = {
        "login": "Welcome Back",
        "signup": "Create your Account",
        "forgot_password": "Reset your Password",
        "reset_password": "Choose a New Password",
    }

    with st.container(key="auth_card"):
        _render_role_banner(target_role)
        st.markdown(
            f'<h1 class="auth-title">{titles.get(mode, "Welcome Back")}</h1>',
            unsafe_allow_html=True,
        )

        if not db_configured:
            st.warning(
                "Signing in requires a database connection. Set DATABASE_URL "
                "in your .env file (see .env.example), then run "
                "`python -m database.init_db`."
            )

        result_user = None
        if mode == "signup":
            _render_google_section(target_role)
            _render_or_divider()
            result_user = _render_signup_form(target_role, db_configured=db_configured)
        elif mode == "forgot_password":
            _render_forgot_password_form()
        elif mode == "reset_password":
            _render_reset_password_form()
        else:
            _render_google_section(target_role)
            _render_or_divider()
            result_user = _render_login_form(target_role, db_configured=db_configured)

        st.markdown(
            '<p class="auth-footnote">By continuing, you agree to our Terms '
            'of Service and Privacy Policy.</p>',
            unsafe_allow_html=True,
        )

    return result_user


def render_auth_page(target_role: str, *, db_configured: bool) -> User | None:
    """
    Render the auth page for `target_role` ("student" or "recruiter") —
    Google Sign-In plus email/password login, signup, forgot-password, and
    reset-password, one mode at a time via st.session_state.auth_mode. A
    single centered card. Returns the just-authenticated User on a
    successful login/signup, else None.
    """
    _inject_auth_css()
    return _render_auth_card(target_role, db_configured=db_configured)

"""
Email delivery for auth flows (verification, password reset).

Dev-mode stub: no real email provider is configured anywhere in this
project yet (no SMTP/SendGrid/SES/etc.). Instead of sending anything over
the network, this module builds the message and returns it so the calling
UI can show the link directly — this keeps the verification/reset flows
fully working and testable without a real inbox.

Swapping in a real provider later is a one-function change: replace
`send_email`'s body with an actual SMTP/API call. Every caller (and every
other module in this app) stays the same.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str
    link: str


def send_email(*, to: str, subject: str, body: str, link: str) -> SentEmail:
    """
    Dev-mode stub — does not actually send anything.

    Real delivery (SMTP/SendGrid/SES/etc.) replaces this function's body
    with an actual provider call; every caller below is unaffected.
    """
    return SentEmail(to=to, subject=subject, body=body, link=link)


def send_verification_email(*, to: str, link: str) -> SentEmail:
    subject = "Verify your email — AI Interview Intelligence"
    body = (
        f"Click the link below to verify your email address:\n\n{link}\n\n"
        "This link expires in 24 hours."
    )
    return send_email(to=to, subject=subject, body=body, link=link)


def send_password_reset_email(*, to: str, link: str) -> SentEmail:
    subject = "Reset your password — AI Interview Intelligence"
    body = (
        f"Click the link below to choose a new password:\n\n{link}\n\n"
        "This link expires in 1 hour. If you didn't request this, you can "
        "safely ignore this email."
    )
    return send_email(to=to, subject=subject, body=body, link=link)

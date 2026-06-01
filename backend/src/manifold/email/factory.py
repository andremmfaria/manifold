from __future__ import annotations

from .base import EmailTransport


def get_transport(provider: str, config: dict) -> EmailTransport:
    if provider == "smtp":
        from manifold.email.adapters.smtp import SMTPTransport

        return SMTPTransport(config)
    if provider == "ses":
        from manifold.email.adapters.ses import SESTransport

        return SESTransport(config)
    if provider == "resend":
        from manifold.email.adapters.resend import ResendTransport

        return ResendTransport(config)
    if provider == "postmark":
        from manifold.email.adapters.postmark import PostmarkTransport

        return PostmarkTransport(config)
    if provider == "mailgun":
        from manifold.email.adapters.mailgun import MailgunTransport

        return MailgunTransport(config)
    if provider == "brevo":
        from manifold.email.adapters.brevo import BrevoTransport

        return BrevoTransport(config)
    raise ValueError(f"unknown provider: {provider}")


__all__ = ["get_transport"]

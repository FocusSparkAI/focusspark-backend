import logging
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from html import escape

from app.core.config import (
    EMAIL_LOGO_URL,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_USE_TLS,
)

logger = logging.getLogger(__name__)

TEXT_EMAIL_FOOTER = (
    "FocusSpark\n"
    "This is an automated security email. If you did not request this action, "
    "you can safely ignore this message.\n"
    f"Need help? Contact {SMTP_FROM_EMAIL}\n"
    "(c) FocusSpark AI"
)


def _email_shell(preheader: str, title: str, content_html: str) -> str:
    logo_html = ""
    if EMAIL_LOGO_URL:
        logo_url = escape(EMAIL_LOGO_URL, quote=True)
        logo_html = (
            f'<img src="{logo_url}" alt="FocusSpark" width="44" height="44" '
            'style="display:block;width:44px;height:44px;margin:0;border:0;outline:none;text-decoration:none;">'
        )
    logo_cell = f'<td style="padding:0 10px 0 0;vertical-align:middle;">{logo_html}</td>' if logo_html else ""

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
  </head>
  <body style="margin:0;background:#f6f8fb;color:#172033;font-family:Arial,Helvetica,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f8fb;padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border:1px solid #e5eaf2;border-radius:16px;overflow:hidden;box-shadow:0 12px 32px rgba(15,23,42,0.08);">
            <tr>
              <td style="padding:28px 28px 18px;background:linear-gradient(135deg,#2563eb,#7c3aed);color:#ffffff;">
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:0;border-collapse:collapse;">
                  <tr>
                    {logo_cell}
                    <td style="padding:0;vertical-align:middle;font-size:15px;font-weight:700;color:#ffffff;">FocusSpark</td>
                  </tr>
                </table>
                <h1 style="margin:12px 0 0;font-size:26px;line-height:1.25;font-weight:700;">{title}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;">
                {content_html}
              </td>
            </tr>
            <tr>
              <td style="padding:18px 28px;background:#f8fafc;border-top:1px solid #e5eaf2;color:#64748b;font-size:12px;line-height:1.6;">
                <strong>FocusSpark</strong><br>
                This is an automated security email. If you did not request this action, you can safely ignore this message.<br>
                Need help? Contact <a href="mailto:{SMTP_FROM_EMAIL}" style="color:#2563eb;text-decoration:none;">{SMTP_FROM_EMAIL}</a><br>
                &copy; FocusSpark AI
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _code_block(code: str) -> str:
    return (
        '<div style="margin:24px 0;padding:18px 20px;background:#eff6ff;border:1px solid #bfdbfe;'
        'border-radius:12px;text-align:center;">'
        f'<div style="font-size:32px;line-height:1;letter-spacing:0.22em;font-weight:800;color:#1d4ed8;">{code}</div>'
        "</div>"
    )


def _send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    if not SMTP_HOST:
        logger.info("Email delivery is not configured. To %s | %s | %s", to_email, subject, text_body)
        return

    message = EmailMessage()
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=SMTP_FROM_EMAIL.split("@")[-1])
    message["Reply-To"] = SMTP_FROM_EMAIL
    message["X-Mailer"] = "FocusSpark"
    message.set_content(f"{text_body}\n\n--\n{TEXT_EMAIL_FOOTER}")
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception:
        logger.exception("Failed to send email to %s with subject %s", to_email, subject)


def send_verification_otp_email(to_email: str, full_name: str, otp: str, expires_minutes: int) -> None:
    text_body = (
        f"Hi {full_name},\n\n"
        f"Your FocusSpark verification code is {otp}.\n"
        f"This code expires in {expires_minutes} minutes.\n\n"
        "If you did not create a FocusSpark account, you can ignore this email."
    )
    html_body = _email_shell(
        "Use this code to verify your FocusSpark email.",
        "Verify your email",
        (
            f'<p style="margin:0 0 14px;font-size:16px;line-height:1.6;">Hi {full_name},</p>'
            '<p style="margin:0;color:#334155;font-size:15px;line-height:1.7;">'
            "Welcome to FocusSpark. Enter this code to verify your email and finish creating your account."
            "</p>"
            f"{_code_block(otp)}"
            f'<p style="margin:0;color:#475569;font-size:14px;line-height:1.7;">This code expires in <strong>{expires_minutes} minutes</strong>.</p>'
        ),
    )
    _send_email(to_email, "Verify your FocusSpark email", text_body, html_body)


def send_welcome_email(to_email: str, full_name: str) -> None:
    text_body = (
        f"Hi {full_name},\n\n"
        "Welcome to FocusSpark. Your email is verified and your account is ready.\n\n"
        "FocusSpark brings your study workspace into one place: goals, focus sessions, Pomodoro timing, "
        "analytics, flashcards, quizzes, AI tutor chat, achievements, notifications, and progress reports.\n\n"
        "Start with onboarding so we can personalize your dashboard around your academic focus, preferred "
        "study rhythm, and learning goals. From there, you can plan today's study targets, track deep-work "
        "minutes, review practice material, and see where your focus is improving over time.\n\n"
        "Thanks for joining FocusSpark. We're glad you're here."
    )
    html_body = _email_shell(
        "Your FocusSpark account is ready. Plan, focus, practice, and track your learning from one workspace.",
        "Welcome to FocusSpark",
        (
            f'<p style="margin:0 0 14px;font-size:16px;line-height:1.6;">Hi {full_name},</p>'
            '<p style="margin:0 0 16px;color:#334155;font-size:15px;line-height:1.7;">'
            "Your email is verified and your account is ready. FocusSpark is built to help you turn study plans "
            "into consistent, measurable learning momentum."
            "</p>"
            '<div style="margin:22px 0;padding:18px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;">'
            '<p style="margin:0 0 10px;color:#172033;font-size:15px;line-height:1.7;font-weight:700;">What you can do with FocusSpark</p>'
            '<ul style="margin:0;padding-left:20px;color:#475569;font-size:14px;line-height:1.8;">'
            "<li>Set daily study goals and keep your dashboard organized around what matters next.</li>"
            "<li>Run focused Pomodoro sessions and track deep-work minutes over time.</li>"
            "<li>Use flashcards, quizzes, and AI tutor chat to practice and review more actively.</li>"
            "<li>Follow reports, analytics, achievements, and notifications that show your progress clearly.</li>"
            "</ul></div>"
            '<div style="margin:0 0 20px;padding:18px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;">'
            '<p style="margin:0;color:#172033;font-size:15px;line-height:1.7;font-weight:700;">Next step</p>'
            '<p style="margin:6px 0 0;color:#475569;font-size:14px;line-height:1.7;">'
            "Complete onboarding so FocusSpark can personalize your workspace around your academic focus and study rhythm."
            "</p></div>"
            '<p style="margin:0;color:#475569;font-size:14px;line-height:1.7;">Thanks for joining FocusSpark. We are glad you are here.</p>'
        ),
    )
    _send_email(to_email, "Welcome to FocusSpark", text_body, html_body)


def send_password_reset_otp_email(to_email: str, full_name: str, otp: str, expires_minutes: int) -> None:
    text_body = (
        f"Hi {full_name},\n\n"
        f"Your FocusSpark password reset code is {otp}.\n"
        f"This code expires in {expires_minutes} minutes.\n\n"
        "If you did not request a password reset, you can ignore this email."
    )
    html_body = _email_shell(
        "Use this code to reset your FocusSpark password.",
        "Reset your password",
        (
            f'<p style="margin:0 0 14px;font-size:16px;line-height:1.6;">Hi {full_name},</p>'
            '<p style="margin:0;color:#334155;font-size:15px;line-height:1.7;">'
            "We received a request to reset your FocusSpark password. Enter this code in the app to continue."
            "</p>"
            f"{_code_block(otp)}"
            f'<p style="margin:0;color:#475569;font-size:14px;line-height:1.7;">This code expires in <strong>{expires_minutes} minutes</strong>.</p>'
        ),
    )
    _send_email(to_email, "Reset your FocusSpark password", text_body, html_body)


def send_password_changed_email(to_email: str, full_name: str) -> None:
    text_body = (
        f"Hi {full_name},\n\n"
        "Your FocusSpark password was changed successfully.\n\n"
        "If this was you, no action is needed. If you did not make this change, contact support immediately."
    )
    html_body = _email_shell(
        "Your FocusSpark password was changed.",
        "Password changed",
        (
            f'<p style="margin:0 0 14px;font-size:16px;line-height:1.6;">Hi {full_name},</p>'
            '<p style="margin:0 0 16px;color:#334155;font-size:15px;line-height:1.7;">'
            "Your FocusSpark password was changed successfully."
            "</p>"
            '<div style="margin:22px 0;padding:16px;background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;color:#9a3412;font-size:14px;line-height:1.7;">'
            "<strong>Security notice:</strong> If this was you, no action is needed. If you did not make this change, contact support immediately."
            "</div>"
        ),
    )
    _send_email(to_email, "Your FocusSpark password was changed", text_body, html_body)

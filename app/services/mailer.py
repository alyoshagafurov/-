"""Отправка email-уведомлений (заявки на оплату).

Если SMTP не настроен (smtp_host/owner_email пусты) — функция тихо ничего
не делает, заявка всё равно остаётся в админке. Ошибки отправки не валят запрос.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from ..config import settings


def send_payment_request_email(tariff_name: str, email: str, phone: str) -> bool:
    if not settings.mail_enabled:
        return False

    msg = EmailMessage()
    msg["Subject"] = "Pixeloff — новая заявка на оплату"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.owner_email
    msg.set_content(
        "Новая заявка на оплату тарифа:\n\n"
        f"Тариф: {tariff_name or '—'}\n"
        f"Email клиента: {email}\n"
        f"Телефон: {phone}\n"
    )

    try:
        ctx = ssl.create_default_context()
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=15) as s:
                s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
                s.starttls(context=ctx)
                s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 — письмо не критично, заявка уже в БД
        return False

"""Optional SMTP delivery. No secrets or token values are logged."""
import logging
import os
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
import smtplib
import ssl
from time import sleep
from urllib.parse import quote

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class MailService:
    def __init__(self):
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.host = os.getenv("SMTP_HOST", "")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.sender = os.getenv("SMTP_FROM", "")
        self.username = os.getenv("SMTP_USERNAME", "")
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.ssl_enabled = os.getenv("SMTP_SSL", "false").lower() == "true"

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.sender)

    def send(self, to_email: str, subject: str, body: str) -> None:
        if not self.enabled:
            logger.warning("SMTP chưa cấu hình: email không được gửi")
            return
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        for attempt in range(2):
            try:
                if self.ssl_enabled:
                    with smtplib.SMTP_SSL(self.host, self.port, timeout=8,
                                          context=ssl.create_default_context()) as smtp:
                        self._deliver(smtp, msg)
                else:
                    with smtplib.SMTP(self.host, self.port, timeout=8) as smtp:
                        smtp.starttls(context=ssl.create_default_context())
                        self._deliver(smtp, msg)
                return
            except (OSError, smtplib.SMTPException):
                logger.exception("Không gửi được email thông báo")
                if attempt == 0:
                    sleep(1)

    def _deliver(self, smtp, message) -> None:
        if self.username:
            smtp.login(self.username, self.password)
        smtp.send_message(message)

    def welcome(self, email: str, username: str) -> None:
        self.send(email, "Chào mừng bạn đến với Algo_web",
                  f"Xin chào {username},\nTài khoản Algo_web đã được tạo thành công.\n")

    def reset_link(self, email: str, raw_token: str) -> None:
        base_url = os.getenv("FRONTEND_RESET_PASSWORD_URL", "").strip()
        if not base_url:
            logger.warning("Chưa có FRONTEND_RESET_PASSWORD_URL: không thể gửi liên kết")
            return
        separator = "&" if "?" in base_url else "?"
        link = f"{base_url}{separator}token={quote(raw_token, safe='')}"
        self.send(email, "Đặt lại mật khẩu Algo_web",
                  f"Bạn đã yêu cầu đặt lại mật khẩu. Liên kết chỉ dùng một lần, hết hạn sau 20 phút:\n{link}\n\nNếu không yêu cầu, hãy bỏ qua email này.\n")

    def password_changed(self, email: str) -> None:
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        self.send(email, "Mật khẩu Algo_web đã thay đổi",
                  f"Mật khẩu tài khoản của bạn vừa được thay đổi lúc {now}. Nếu không phải bạn, hãy liên hệ quản trị viên.\n")

"""SMTP and reset-link tests without external network calls."""
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from Services.MailService import MailService


def test_welcome_and_reset_email_templates_with_sandbox_settings(monkeypatch):
    monkeypatch.setenv('SMTP_HOST', 'sandbox.smtp.mailtrap.io')
    monkeypatch.setenv('SMTP_PORT', '587')
    monkeypatch.setenv('SMTP_SSL', 'false')
    monkeypatch.setenv('SMTP_FROM', 'algoweb2026@gmail.com')
    monkeypatch.setenv('SMTP_USERNAME', 'test-sandbox-login')
    monkeypatch.setenv('SMTP_PASSWORD', 'test-sandbox-secret')
    monkeypatch.setenv('FRONTEND_RESET_PASSWORD_URL', 'http://localhost:5173/reset-password')
    smtp=MagicMock()
    # The context manager returns our fake SMTP session; never uses Internet.
    smtp.__enter__.return_value=smtp
    with patch('Services.MailService.smtplib.SMTP',return_value=smtp) as sender:
        mail=MailService()
        assert mail.enabled
        mail.welcome('demo@example.com','demo2026')
        mail.reset_link('demo@example.com','test-only-token')
        mail.password_changed('demo@example.com')
        assert sender.call_count==3
        assert smtp.starttls.call_count==3
        assert smtp.login.call_count==3
        assert smtp.send_message.call_count==3
        args=[x.args[0] for x in smtp.send_message.call_args_list]
        assert 'Chào mừng bạn' in args[0]['Subject']
        assert 'token=test-only-token' in args[1].get_content()
        assert '20 phút' in args[1].get_content()
        assert 'Mật khẩu' in args[2]['Subject']
        assert all('test-sandbox-secret' not in msg.get_content() for msg in args)


def test_forgot_password_does_not_expose_token_in_http_response():
    with TestClient(app) as client:
        result=client.post('/auth/forgot-password',json={'email':'not-registered@example.com'})
        assert result.status_code==200
        assert list(result.json())==['message']
        assert 'token' not in result.text.lower()

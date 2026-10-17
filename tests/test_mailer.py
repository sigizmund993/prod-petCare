import smtplib
from typing import ClassVar

import pytest

from src import config, mailer


class FakeSMTP:
    instances: ClassVar[list["FakeSMTP"]] = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.calls, self.sent = host, port, [], []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, msg):
        self.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_USER", "bot@example.com")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "pw")
    monkeypatch.setattr(config, "SMTP_FROM", "bot@example.com")
    return FakeSMTP


def test_without_smtp_host_mail_goes_to_log(monkeypatch, caplog):
    monkeypatch.setattr(config, "SMTP_HOST", "")
    mailer.send_mail("a@example.com", "Тема", "Код 123456")
    assert "123456" in caplog.text


def test_starttls_login_and_send(smtp, monkeypatch):
    monkeypatch.setattr(config, "SMTP_TLS", "starttls")
    mailer.send_mail("a@example.com", "Тема", "Текст")
    s = smtp.instances[0]
    assert s.calls == ["starttls", ("login", "bot@example.com", "pw")]
    assert s.sent[0]["To"] == "a@example.com" and s.sent[0]["Subject"] == "Тема"


def test_ssl_mode_skips_starttls(smtp, monkeypatch):
    monkeypatch.setattr(config, "SMTP_TLS", "ssl")
    mailer.send_mail("a@example.com", "Тема", "Текст")
    assert "starttls" not in smtp.instances[0].calls


def test_smtp_failure_does_not_raise(smtp, monkeypatch, caplog):
    def boom(self, msg):
        raise smtplib.SMTPException("down")

    monkeypatch.setattr(FakeSMTP, "send_message", boom)
    mailer.send_mail("a@example.com", "Тема", "Текст")
    assert "a@example.com" in caplog.text

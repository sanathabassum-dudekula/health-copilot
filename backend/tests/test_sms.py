import base64
from urllib.parse import parse_qs

import pytest

from app import sms
from app.sms import SmsConfigurationError, SmsDeliveryError


class _Response:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def test_twilio_sms_uses_configured_messaging_service(monkeypatch):
    monkeypatch.setattr(sms.settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(sms.settings, "TWILIO_AUTH_TOKEN", "test-secret")
    monkeypatch.setattr(sms.settings, "TWILIO_MESSAGING_SERVICE_SID", "MG123")
    monkeypatch.setattr(sms.settings, "TWILIO_FROM_NUMBER", "")
    requests = []
    monkeypatch.setattr(sms, "urlopen", lambda request, timeout: (
        requests.append((request, timeout)) or _Response()
    ))

    sms.send_twilio_sms("+1 (555) 123-4567", "Invitation link")

    request, timeout = requests[0]
    assert timeout == 10
    assert request.full_url.endswith("/Accounts/AC123/Messages.json")
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == (
        "Basic " + base64.b64encode(b"AC123:test-secret").decode("ascii")
    )
    assert parse_qs(request.data.decode("utf-8")) == {
        "To": ["+15551234567"],
        "Body": ["Invitation link"],
        "MessagingServiceSid": ["MG123"],
    }


def test_twilio_sms_requires_credentials(monkeypatch):
    monkeypatch.setattr(sms.settings, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(sms.settings, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(sms.settings, "TWILIO_MESSAGING_SERVICE_SID", "")
    monkeypatch.setattr(sms.settings, "TWILIO_FROM_NUMBER", "")

    with pytest.raises(SmsConfigurationError):
        sms.send_twilio_sms("+15551234567", "Invitation link")


def test_twilio_sms_requires_international_number(monkeypatch):
    monkeypatch.setattr(sms.settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(sms.settings, "TWILIO_AUTH_TOKEN", "test-secret")
    monkeypatch.setattr(sms.settings, "TWILIO_MESSAGING_SERVICE_SID", "MG123")
    monkeypatch.setattr(sms.settings, "TWILIO_FROM_NUMBER", "")

    with pytest.raises(SmsDeliveryError, match="international"):
        sms.send_twilio_sms("5551234567", "Invitation link")

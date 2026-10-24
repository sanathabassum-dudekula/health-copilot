import base64
from datetime import datetime, timedelta, timezone
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers import reminders


def _vapid_keys() -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_bytes = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    private_key_text = base64.urlsafe_b64encode(private_bytes).decode().rstrip("=")
    public_key_text = base64.urlsafe_b64encode(public_bytes).decode().rstrip("=")
    return public_key_text, private_key_text


def _subscription_keys() -> dict[str, str]:
    public_key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    auth_secret = b"test-auth-secret"
    return {
        "p256dh": base64.urlsafe_b64encode(public_key).decode().rstrip("="),
        "auth": base64.urlsafe_b64encode(auth_secret).decode().rstrip("="),
    }


def test_due_reminders_are_sent_privately_and_only_once(monkeypatch):
    public_key, private_key = _vapid_keys()
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", public_key)
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", private_key)
    monkeypatch.setattr(settings, "VAPID_SUBJECT", "https://health-copilot.example")
    monkeypatch.setattr(settings, "CRON_SECRET", "test-cron-secret")
    sent = []
    monkeypatch.setattr(reminders, "webpush", lambda **kwargs: sent.append(kwargs))

    with TestClient(app) as client:
        registered = client.post(
            "/auth/register",
            json={
                "email": f"{uuid.uuid4()}@example.com",
                "password": "correct-horse-battery",
                "name": "Push test",
            },
        )
        assert registered.status_code == 200, registered.text

        due_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        created = client.post(
            "/reminders",
            json={
                "title": "Private medicine name",
                "due_at": due_at,
                "category": "medication",
            },
        )
        assert created.status_code == 201, created.text

        subscription = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/test-token",
            "keys": _subscription_keys(),
        }
        saved = client.post("/reminders/push/subscriptions", json=subscription)
        assert saved.status_code == 201, saved.text
        config = client.get("/reminders/push/config")
        assert config.json() == {"enabled": True, "public_key": public_key}

        assert client.get("/reminders/dispatch").status_code == 401
        dispatched = client.get(
            "/reminders/dispatch",
            headers={"Authorization": "Bearer test-cron-secret"},
        )
        assert dispatched.status_code == 200, dispatched.text
        assert dispatched.json() == {
            "attempted": 1,
            "delivered": 1,
            "expired_subscriptions": 0,
            "failed": 0,
        }
        payload = sent[0]["data"]
        assert "Private medicine name" not in payload
        assert "scheduled reminder is due" in payload

        repeated = client.get(
            "/reminders/dispatch",
            headers={"Authorization": "Bearer test-cron-secret"},
        )
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["attempted"] == 0
        assert len(sent) == 1

        removed = client.request(
            "DELETE", "/reminders/push/subscriptions", json={"endpoint": subscription["endpoint"]}
        )
        assert removed.status_code == 204


def test_push_subscriptions_reject_non_push_urls(monkeypatch):
    public_key, private_key = _vapid_keys()
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", public_key)
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", private_key)
    monkeypatch.setattr(settings, "VAPID_SUBJECT", "https://health-copilot.example")
    with TestClient(app) as client:
        registered = client.post(
            "/auth/register",
            json={
                "email": f"{uuid.uuid4()}@example.com",
                "password": "correct-horse-battery",
                "name": "Push validation test",
            },
        )
        assert registered.status_code == 200, registered.text
        response = client.post(
            "/reminders/push/subscriptions",
            json={
                "endpoint": "https://127.0.0.1/internal",
                "keys": _subscription_keys(),
            },
        )
        assert response.status_code == 422

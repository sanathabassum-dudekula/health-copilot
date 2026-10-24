import base64
from datetime import datetime, timedelta, timezone
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models import Document, FamilyLink, Medication, Profile, User, Visit
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


def test_family_reminders_require_both_profiles_to_opt_in(monkeypatch):
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
                "name": "Family reminder owner",
            },
        )
        assert registered.status_code == 200, registered.text
        assert client.put(
            "/profile", json={"family_reminders_enabled": True}
        ).json()["family_reminders_enabled"] is True

        member_response = client.post(
            "/family",
            json={"name": "Family member", "pin": "123456"},
        )
        assert member_response.status_code == 201, member_response.text
        member = member_response.json()
        assert member["family_reminders_enabled"] is False
        assert client.post(
            f"/family/{member['oid']}/unlock", json={"pin": "123456"}
        ).status_code == 200
        assert client.get("/reminders/family").status_code == 403

        subscription = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/family-token",
            "keys": _subscription_keys(),
        }
        assert client.post(
            "/reminders/push/subscriptions", json=subscription
        ).status_code == 201
        assert client.post("/family/switch-to-owner").status_code == 200

        due_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        created = client.post(
            "/reminders",
            json={"title": "Family visit", "due_at": due_at, "category": "appointment"},
        )
        assert created.status_code == 201, created.text
        own_subscription = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/owner-token",
            "keys": _subscription_keys(),
        }
        assert client.post(
            "/reminders/push/subscriptions", json=own_subscription
        ).status_code == 201

        dispatch_url = "/reminders/dispatch"
        auth_headers = {"Authorization": f"Bearer {settings.CRON_SECRET}"}
        first_dispatch = client.get(dispatch_url, headers=auth_headers)
        assert first_dispatch.status_code == 200, first_dispatch.text
        assert first_dispatch.json()["delivered"] == 1

        assert client.post(
            f"/family/{member['oid']}/unlock", json={"pin": "123456"}
        ).status_code == 200
        enabled = client.put("/profile", json={"family_reminders_enabled": True})
        assert enabled.status_code == 200, enabled.text

        shared = client.get("/reminders/family")
        assert shared.status_code == 200, shared.text
        assert shared.json()[0]["profile_name"] == "Family reminder owner"
        assert shared.json()[0]["title"] == "Family visit"
        assert client.post("/family/switch-to-owner").status_code == 200
        assert client.get("/reminders/family").json() == []

        next_due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        second = client.post(
            "/reminders",
            json={"title": "Second family visit", "due_at": next_due},
        )
        assert second.status_code == 201, second.text
        second_dispatch = client.get(dispatch_url, headers=auth_headers)
        assert second_dispatch.status_code == 200, second_dispatch.text
        assert second_dispatch.json()["delivered"] == 3
        assert any("family=1" in item["data"] for item in sent)
        assert all(
            "Family visit" not in item["data"]
            and "Second family visit" not in item["data"]
            for item in sent
        )


def test_family_profile_lookup_includes_all_linked_groups():
    with SessionLocal() as db:
        owner_a = User(profile=Profile(name="Owner A"))
        member = User(profile=Profile(name="Shared member"))
        owner_b = User(profile=Profile(name="Owner B"))
        member_a = User(profile=Profile(name="Member A"))
        member_b = User(profile=Profile(name="Member B"))
        db.add_all([owner_a, member, owner_b, member_a, member_b])
        db.flush()
        db.add_all([
            FamilyLink(owner_user_id=owner_a.id, member_user_id=member.id),
            FamilyLink(owner_user_id=owner_a.id, member_user_id=member_a.id),
            FamilyLink(owner_user_id=owner_b.id, member_user_id=member.id),
            FamilyLink(owner_user_id=owner_b.id, member_user_id=member_b.id),
        ])
        db.flush()

        group = reminders._family_profiles(member.profile, db)

        assert {profile.name for profile in group} == {
            "Owner A",
            "Shared member",
            "Owner B",
            "Member A",
            "Member B",
        }
        db.rollback()


def test_routine_suggestions_use_confirmed_prescriptions_only(monkeypatch):
    captured_context = []

    class FakeRunnable:
        pass

    def fake_invoke(_model, messages):
        captured_context.append(messages[0]["content"])
        return reminders.RoutinePlan(
            suggestions=[], note="General routine suggestions."
        )

    monkeypatch.setattr(reminders, "structured", lambda *_: FakeRunnable())
    monkeypatch.setattr(reminders, "invoke_with_retry", fake_invoke)
    visit_id = str(uuid.uuid4())

    with TestClient(app, headers={"X-Visit": visit_id}) as client:
        profile_response = client.get("/profile")
        assert profile_response.status_code == 200, profile_response.text
        response = client.post(
            "/reminders/suggestions",
            json={"written_language": "en", "voice_language": "en"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["routine_basis"] == "general"
        assert response.json()["confirmed_prescription_count"] == 0

        with SessionLocal() as db:
            profile = (
                db.query(Profile)
                .join(User, Profile.user_id == User.id)
                .join(Visit, Visit.user_id == User.id)
                .filter(Visit.token == visit_id)
                .one()
            )
            confirmed = Document(
                profile_id=profile.id,
                status="done",
                review_status="confirmed",
                source="upload",
            )
            unconfirmed = Document(
                profile_id=profile.id,
                status="done",
                review_status="pending",
                source="upload",
            )
            db.add_all([confirmed, unconfirmed])
            db.flush()
            db.add_all([
                Medication(
                    profile_id=profile.id,
                    document_id=confirmed.id,
                    brand_name="Confirmed medicine",
                    timing="with breakfast",
                ),
                Medication(
                    profile_id=profile.id,
                    document_id=unconfirmed.id,
                    brand_name="Unconfirmed medicine",
                    timing="at bedtime",
                ),
            ])
            db.commit()

        response = client.post(
            "/reminders/suggestions",
            json={"written_language": "en", "voice_language": "en"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["routine_basis"] == "confirmed_prescriptions"
        assert response.json()["confirmed_prescription_count"] == 1
        assert "Confirmed medicine" in captured_context[1]
        assert "Unconfirmed medicine" not in captured_context[1]
        assert "Never recommend a medication, dose, frequency, or medication time" in captured_context[1]

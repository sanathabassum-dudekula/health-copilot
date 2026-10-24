from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import (
    AuthSession,
    Document,
    FamilyInvitation,
    FamilyLink,
    Profile,
    User,
)


def _register(client: TestClient) -> str:
    email = f"{uuid.uuid4()}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "correct-horse-battery", "name": "Owner"},
    )
    assert response.status_code == 200, response.text
    return email


def test_family_profile_pin_and_invitation_flows():
    with TestClient(app) as client:
        _register(client)
        created = client.post(
            "/family",
            json={
                "name": "Family member",
                "dob": "1990-02-01",
                "blood_group": "O+",
                "pin": "123456",
            },
        )
        assert created.status_code == 201, created.text
        member = created.json()
        assert member["has_pin"] is True
        assert member["dob"] == "1990-02-01"

        assert client.get("/family").json()["members"] == [member]
        assert client.get(f"/family/{member['oid']}").json() == member
        updated = client.put(
            f"/family/{member['oid']}",
            json={"name": "Updated member", "allergies_text": "Pollen"},
        )
        assert updated.status_code == 200
        assert updated.json()["allergies_text"] == "Pollen"

        assert client.post(
            f"/family/{member['oid']}/unlock", json={"pin": "000000"}
        ).status_code == 401
        unlocked = client.post(
            f"/family/{member['oid']}/unlock", json={"pin": "123456"}
        )
        assert unlocked.status_code == 200, unlocked.text
        assert client.get("/family/active").json()["type"] == "family"

        switched = client.post("/family/switch-to-owner")
        assert switched.status_code == 200
        assert client.get("/family/active").json()["type"] == "owner"

        assert client.post(
            f"/family/{member['oid']}/reset-pin",
            json={"account_password": "wrong-password", "new_pin": "654321"},
        ).status_code == 401
        reset = client.post(
            f"/family/{member['oid']}/reset-pin",
            json={
                "account_password": "correct-horse-battery",
                "new_pin": "654321",
            },
        )
        assert reset.status_code == 200, reset.text
        assert client.post(
            f"/family/{member['oid']}/unlock", json={"pin": "123456"}
        ).status_code == 401
        assert client.post(
            f"/family/{member['oid']}/unlock", json={"pin": "654321"}
        ).status_code == 200

        invitation = client.post(
            "/family/invitations",
            json={
                "phone_number": "+1 (555) 123-4567",
                "relationship_label": "Sibling",
            },
        )
        assert invitation.status_code == 201, invitation.text
        invitation_data = invitation.json()
        assert invitation_data["status"] == "pending"
        assert "No SMS was sent" in invitation_data["message"]
        listed_invitations = client.get("/family/invitations")
        assert listed_invitations.status_code == 200
        assert listed_invitations.json()[0]["id"] == invitation_data["id"]

        cancelled = client.delete(
            f"/family/invitations/{invitation_data['id']}"
        )
        assert cancelled.json() == {
            "ok": True,
            "id": invitation_data["id"],
            "status": "cancelled",
        }

        assert client.delete(f"/family/{member['oid']}").status_code == 204
        assert client.get("/family").json()["members"] == []


def test_family_pin_lockout_and_owner_isolation():
    with TestClient(app) as owner_client:
        _register(owner_client)
        created = owner_client.post(
            "/family",
            json={"name": "Protected member", "pin": "123456"},
        )
        assert created.status_code == 201, created.text
        oid = created.json()["oid"]

        for _ in range(4):
            assert owner_client.post(
                f"/family/{oid}/unlock", json={"pin": "000000"}
            ).status_code == 401
        assert owner_client.post(
            f"/family/{oid}/unlock", json={"pin": "000000"}
        ).status_code == 429
        assert owner_client.post(
            f"/family/{oid}/unlock", json={"pin": "123456"}
        ).status_code == 429

        with SessionLocal() as db:
            member = db.scalar(select(Profile).where(Profile.oid == oid))
            member.pin_locked_until = (
                datetime.now(timezone.utc).replace(tzinfo=None)
                - timedelta(seconds=1)
            )
            db.commit()

        assert owner_client.post(
            f"/family/{oid}/unlock", json={"pin": "123456"}
        ).status_code == 200

        with TestClient(app) as other_client:
            _register(other_client)
            assert other_client.get(f"/family/{oid}").status_code == 404
            assert other_client.delete(f"/family/{oid}").status_code == 404


def test_profile_and_document_routes_follow_active_family_profile():
    with TestClient(app) as client:
        email = _register(client)
        created = client.post(
            "/family",
            json={"name": "Member profile", "pin": "123456"},
        )
        assert created.status_code == 201, created.text
        member_oid = created.json()["oid"]

        with SessionLocal() as db:
            owner = db.scalar(
                select(Profile)
                .join(User, User.id == Profile.user_id)
                .where(User.email == email)
            )
            member = db.scalar(select(Profile).where(Profile.oid == member_oid))
            owner_document = Document(
                profile_id=owner.id, status="done", source="upload"
            )
            member_document = Document(
                profile_id=member.id, status="done", source="upload"
            )
            db.add_all([owner_document, member_document])
            db.commit()
            db.refresh(owner_document)
            db.refresh(member_document)
            owner_document_id = owner_document.id
            member_document_id = member_document.id
            owner_oid = owner.oid or f"owner-{owner.id}"

        owner_profile = client.get("/profile").json()
        assert owner_profile["name"] == "Owner"
        assert owner_profile["oid"] == owner_oid
        assert client.get("/insights").json()["profile"]["oid"] == owner_oid
        owner_docs = client.get(f"/documents?profile_oid={owner_oid}")
        assert owner_docs.status_code == 200
        assert [doc["id"] for doc in owner_docs.json()] == [owner_document_id]
        owner_reminder = client.post(
            f"/reminders?profile_oid={owner_oid}",
            json={"title": "Check in", "due_at": "2030-01-01T09:00:00+00:00"},
        )
        assert owner_reminder.status_code == 201, owner_reminder.text
        assert owner_reminder.json()["profile_oid"] == owner_oid

        unlocked = client.post(
            f"/family/{member_oid}/unlock", json={"pin": "123456"}
        )
        assert unlocked.status_code == 200
        assert client.get("/profile").json()["name"] == "Member profile"
        member_docs = client.get(f"/documents?profile_oid={member_oid}")
        assert member_docs.status_code == 200
        assert [doc["id"] for doc in member_docs.json()] == [member_document_id]
        assert client.get(f"/documents?profile_oid={owner_oid}").status_code == 404

        updated = client.put(
            "/profile",
            json={
                "name": "Updated member",
                "preferred_language": "hi",
                "preferred_voice_language": "te",
                "voice_reminders_enabled": True,
                "allergies_text": "Pollen",
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["name"] == "Updated member"
        assert updated.json()["language"] == "hi"
        assert updated.json()["voice_language"] == "te"
        assert updated.json()["voice_reminders_enabled"] is True
        assert updated.json()["allergies_text"] == "Pollen"

        abha = client.post("/abha/link", json={"abha": "12-3456-7890-1234"})
        assert abha.status_code == 200, abha.text
        with SessionLocal() as db:
            assert db.scalar(
                select(Profile.abha_number).where(Profile.oid == member_oid)
            ) == "12-3456-7890-1234"
            assert db.scalar(
                select(Profile.abha_number).where(Profile.id == owner.id)
            ) is None


def test_account_deletion_revokes_sessions_and_removes_family_links():
    with TestClient(app) as client:
        owner_email = _register(client)
        member = client.post(
            "/family",
            json={"name": "Linked member", "pin": "123456"},
        )
        assert member.status_code == 201, member.text
        member_oid = member.json()["oid"]
        invitation = client.post(
            "/family/invitations",
            json={"phone_number": "+1 (555) 123-4567"},
        )
        assert invitation.status_code == 201, invitation.text

        with SessionLocal() as db:
            owner_id = db.scalar(
                select(User.id).where(User.email == owner_email)
            )
            assert db.scalar(
                select(AuthSession.id).where(AuthSession.user_id == owner_id)
            )
            assert db.scalar(
                select(FamilyLink.id).where(FamilyLink.owner_user_id == owner_id)
            )
            assert db.scalar(
                select(FamilyInvitation.id).where(
                    FamilyInvitation.owner_user_id == owner_id
                )
            )

        assert client.delete("/profile").status_code == 204
        assert client.get("/auth/me").status_code == 401

        with SessionLocal() as db:
            assert db.get(User, owner_id) is None
            assert db.scalar(
                select(AuthSession.id).where(AuthSession.user_id == owner_id)
            ) is None
            assert db.scalar(
                select(FamilyLink.id).where(FamilyLink.owner_user_id == owner_id)
            ) is None
            assert db.scalar(
                select(FamilyInvitation.id).where(
                    FamilyInvitation.owner_user_id == owner_id
                )
            ) is None
            assert db.scalar(select(Profile.id).where(Profile.oid == member_oid))

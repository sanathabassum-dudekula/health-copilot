from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Profile


def _register(client: TestClient) -> None:
    email = f"{uuid.uuid4()}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "correct-horse-battery", "name": "Owner"},
    )
    assert response.status_code == 200, response.text


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

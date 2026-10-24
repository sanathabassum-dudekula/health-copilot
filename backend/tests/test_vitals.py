import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.main import app
from app.routers import assistant


def test_bluetooth_reading_is_saved_listed_in_timeline_and_shared_with_lumi(monkeypatch):
    captured = {}

    monkeypatch.setattr(assistant, "chat_model", lambda *_: object())

    def respond(_model, messages):
        captured["system"] = messages[0].content
        return AIMessage(content="I can review your saved measurements.")

    monkeypatch.setattr(assistant, "invoke_with_retry", respond)
    visit_id = str(uuid.uuid4())
    captured_at = datetime.now(timezone.utc).isoformat()

    with TestClient(app, headers={"X-Visit": visit_id}) as client:
        client.get("/profile")
        response = client.post(
            "/vitals",
            json={
                "metric": "heart_rate",
                "value": 82,
                "source": "bluetooth",
                "device_name": "Synthetic BLE monitor",
                "captured_at": captured_at,
            },
        )
        assert response.status_code == 201
        assert response.json()["unit"] == "bpm"

        old_response = client.post(
            "/vitals",
            json={
                "metric": "oxygen_saturation",
                "value": 98,
                "source": "manual",
                "captured_at": "2020-01-01T10:00:00+00:00",
            },
        )
        assert old_response.status_code == 201

        readings = client.get("/vitals").json()
        assert len(readings) == 2
        timeline = client.get("/profile/timeline?types=vitals").json()
        bluetooth_event = next(item for item in timeline if item["source"] == "bluetooth")
        assert bluetooth_event["type"] == "vital_sign"
        assert bluetooth_event["title"] == "heart_rate"
        assert bluetooth_event["detail"] == "82 bpm"
        assert bluetooth_event["device_name"] == "Synthetic BLE monitor"
        assert bluetooth_event["captured_at"].startswith(captured_at[:19])

        chat = client.post(
            "/assistant/chat",
            json={"message": "Please review my recent readings.", "language": "en"},
        )
        assert chat.status_code == 200

    assert '"recent_vital_readings":' in captured["system"]
    assert "Synthetic BLE monitor" in captured["system"]
    assert '"source": "bluetooth"' in captured["system"]
    assert "2020-01-01" not in captured["system"]


def test_vital_units_validation_and_profile_scoping():
    first_visit = str(uuid.uuid4())
    second_visit = str(uuid.uuid4())

    with TestClient(app, headers={"X-Visit": first_visit}) as first, TestClient(
        app, headers={"X-Visit": second_visit}
    ) as second:
        first_profile = first.get("/profile").json()
        second.get("/profile")

        temperature = first.post(
            "/vitals",
            json={
                "metric": "body_temperature",
                "value": 37.2,
                "source": "bluetooth",
                "device_name": "Thermometer",
            },
        )
        assert temperature.status_code == 201
        assert temperature.json()["unit"] == "°C"
        assert first.get("/vitals").json()[0]["device_name"] == "Thermometer"
        assert second.get("/vitals").json() == []
        assert second.get(
            f"/vitals?profile_oid={first_profile['oid']}"
        ).status_code == 404

        invalid = first.post(
            "/vitals",
            json={
                "metric": "oxygen_saturation",
                "value": 120,
                "source": "bluetooth",
            },
        )
        assert invalid.status_code == 422

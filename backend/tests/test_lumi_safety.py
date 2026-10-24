from types import SimpleNamespace
import uuid

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy import select

from app.db import SessionLocal
from app.ingestion import summarize
from app.ingestion.schemas import Summary
from app.main import app
from app.models import Document, Observation, Profile, Visit
from app.routers import assistant


class FakeSummaryModel:
    def invoke(self, prompt):
        self.prompt = prompt
        return Summary(headline="Report summary", key_points=[]).model_copy(
            update={"urgent_actions": ["model-generated advice"]}
        )


def _record(interpretation):
    return {
        "doc_type": "lab_report",
        "doc_date": "2026-10-24",
        "impression": None,
        "follow_up": None,
        "observations": [{
            "display_name": "Potassium",
            "value_num": 6.9,
            "unit": "mmol/L",
            "interpretation": interpretation,
            "ref_low": 3.5,
            "ref_high": 5.1,
            "explainer": "Potassium is an electrolyte.",
        }],
        "medications": [],
        "conditions": [],
        "fractures_or_injuries": [],
        "womens_health": None,
    }


def test_critical_summary_replaces_model_advice_with_deterministic_guidance(monkeypatch):
    model = FakeSummaryModel()
    monkeypatch.setattr(summarize, "structured", lambda *_: model)

    summary = summarize.build_summary(_record("HH"))

    assert "6.9" not in model.prompt
    assert len(summary["urgent_actions"]) == 2
    assert "original report" in summary["urgent_actions"][0]
    assert "date" in summary["urgent_actions"][0]
    assert "ordering clinician" in summary["urgent_actions"][0]
    assert "local emergency services" in summary["urgent_actions"][1]
    assert summary["urgent_actions"] != ["model-generated advice"]


def test_noncritical_summary_does_not_show_urgent_actions(monkeypatch):
    monkeypatch.setattr(summarize, "structured", lambda *_: FakeSummaryModel())

    summary = summarize.build_summary(_record("H"))

    assert summary["urgent_actions"] == []


def test_template_summary_keeps_critical_guidance_when_model_is_unavailable(monkeypatch):
    def unavailable(*_):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(summarize, "structured", unavailable)

    summary = summarize.build_summary(_record("LL"))

    assert len(summary["urgent_actions"]) == 2
    assert "ordering clinician" in summary["urgent_actions"][0]


def test_critical_summary_translation_uses_reviewed_safety_text(monkeypatch):
    monkeypatch.setattr(summarize, "structured", lambda *_: FakeSummaryModel())

    for language in ("hi", "te", "ta"):
        translated = summarize.translate_summary(
            {"urgent_actions": summarize.CRITICAL_ACTIONS},
            language,
        )
        assert translated["urgent_actions"] == summarize.CRITICAL_ACTIONS_TRANSLATED[language]
        assert translated["urgent_actions"] != ["model-generated advice"]


def test_report_chat_context_uses_only_computed_critical_flags():
    document = SimpleNamespace(
        doc_type="lab_report",
        doc_date="2026-10-24",
        facility=None,
        practitioner=None,
        review_status="pending",
        extraction={"lab_results": []},
        observations=[
            SimpleNamespace(
                display_name="Potassium",
                value_num=6.9,
                value_text=None,
                unit="mmol/L",
                interpretation="HH",
            ),
            SimpleNamespace(
                display_name="Sodium",
                value_num=148,
                value_text=None,
                unit="mmol/L",
                interpretation="H",
            ),
        ],
    )

    context = assistant._document_context(document)
    notice = assistant._critical_report_notice(document, "en")
    hindi_notice = assistant._critical_report_notice(document, "hi")

    assert '"software_critical_results": [{"test": "Potassium"' in context
    assert "Sodium" not in context
    assert "Potassium: 6.9 mmol/L (critically high)" in notice
    assert "original report and date" in notice
    assert "स्थानीय आपातकालीन सेवा" in hindi_notice


def test_report_chat_does_not_create_notice_for_noncritical_or_missing_report():
    document = SimpleNamespace(
        observations=[
            SimpleNamespace(
                display_name="Sodium",
                value_num=148,
                value_text=None,
                unit="mmol/L",
                interpretation="H",
            ),
        ],
    )

    assert assistant._critical_report_notice(document, "en") is None
    assert assistant._critical_report_notice(None, "en") is None


def test_chat_includes_and_saves_critical_report_guidance(monkeypatch):
    monkeypatch.setattr(assistant, "chat_model", lambda *_: object())
    captured = {}

    def respond(model, messages):
        assert model is not None
        captured["messages"] = messages
        return AIMessage(content="I can explain this result.")

    monkeypatch.setattr(assistant, "invoke_with_retry", respond)
    visit_id = str(uuid.uuid4())

    with TestClient(app, headers={"X-Visit": visit_id}) as client:
        client.get("/profile")
        vital_response = client.post(
            "/vitals",
            json={
                "metric": "body_temperature",
                "value": 37.5,
                "source": "bluetooth",
                "device_name": "Synthetic thermometer",
                "captured_at": "2026-10-24T10:00:00+00:00",
            },
        )
        assert vital_response.status_code == 201
        timeline = client.get("/profile/timeline?types=reports,vitals")
        assert timeline.status_code == 200
        assert {item["type"] for item in timeline.json()} == {"vital_sign"}

        with SessionLocal() as db:
            visit = db.scalar(select(Visit).where(Visit.token == visit_id))
            assert visit is not None
            profile = visit.user.profile
            assert profile is not None
            document = Document(
                profile_id=profile.id,
                status="done",
                doc_type="lab_report",
                extraction={"doc_type": "lab_report", "lab_results": []},
            )
            db.add(document)
            db.flush()
            db.add(Observation(
                profile_id=profile.id,
                document_id=document.id,
                display_name="Potassium",
                value_num=6.9,
                unit="mmol/L",
                interpretation="HH",
            ))
            db.commit()
            document_id = document.id

        response = client.post(
            "/assistant/chat",
            json={
                "message": "What does this result mean?",
                "language": "en",
                "document_id": document_id,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert "Potassium: 6.9 mmol/L (critically high)" in payload["answer"]
    assert "ordering clinician" in payload["answer"]
    assert payload["messages"][-1]["content"] == payload["answer"]
    assert "local emergency services" in payload["spoken_answer"]
    system_context = captured["messages"][0].content
    assert '"recent_vital_readings":' in system_context
    assert "Synthetic thermometer" in system_context
    assert '"source": "bluetooth"' in system_context

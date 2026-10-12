from datetime import date

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import current_profile, delete_profile_data
from ..db import get_db
from ..fhir.serialize import to_bundle
from ..models import Allergy, Condition, Document, Medication, Observation, Profile

router = APIRouter(tags=["profile"])
ABNORMAL = ("L", "H", "LL", "HH")


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    dob: date | None = None
    sex: str | None = Field(default=None, max_length=40)
    age: int | None = Field(default=None, ge=0, le=130)
    blood_group: str | None = Field(default=None, max_length=10)
    allergies_text: str | None = None
    conditions_text: str | None = None
    medicines_text: str | None = None
    previous_records: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: str | None = Field(default=None, max_length=40)
    preferred_language: str | None = None


def _q(db: Session, p: Profile, model, *where):
    return db.scalars(
        select(model).where(model.profile_id == p.id, *where)
    )


def _age(dob: date | None) -> int | None:
    if not dob:
        return None

    today = date.today()
    return today.year - dob.year - (
        (today.month, today.day) < (dob.month, dob.day)
    )


def _profile_json(p: Profile, db: Session) -> dict:
    today = date.today()

    meds = _q(
        db,
        p,
        Medication,
        or_(
            Medication.end_date.is_(None),
            Medication.end_date >= today,
        ),
    )

    latest: dict[str, Observation] = {}

    for observation in sorted(
        _q(
            db,
            p,
            Observation,
            Observation.interpretation.in_(ABNORMAL),
        ),
        key=lambda item: item.effective_at or date.min,
    ):
        latest[observation.display_name] = observation

    return {
        "name": p.name,
        "dob": p.dob,
        "age": _age(p.dob) if p.dob else p.age,
        "sex": p.sex,
        "blood_group": p.blood_group,
        "allergies_text": p.allergies_text,
        "conditions_text": p.conditions_text,
        "medicines_text": p.medicines_text,
        "previous_records": p.previous_records,
        "emergency_contact_name": p.emergency_contact_name,
        "emergency_contact_phone": p.emergency_contact_phone,
        "language": p.user.preferred_language,
        "abha": {
            "number": p.abha_number,
            "address": p.abha_address,
            "linked": bool(p.abha_linked_at),
        },
        # These lists remain based on extracted medical records.
        # They are intentionally separate from the profile form's text fields.
        "conditions": sorted({
            condition.name for condition in _q(db, p, Condition)
        }),
        "allergies": sorted({
            allergy.substance for allergy in _q(db, p, Allergy)
        }),
        "current_medicines": [
            {
                "name": medicine.brand_name,
                "salt": medicine.salt,
                "dose_pattern": medicine.dose_pattern,
                "document_id": medicine.document_id,
            }
            for medicine in meds
        ],
        "latest_abnormal": [
            {
                "test": observation.display_name,
                "value": (
                    observation.value_num
                    if observation.value_num is not None
                    else observation.value_text
                ),
                "unit": observation.unit,
                "interpretation": observation.interpretation,
                "date": observation.effective_at,
                "ref_low": observation.ref_low,
                "ref_high": observation.ref_high,
                "document_id": observation.document_id,
            }
            for observation in latest.values()
        ],
    }


@router.get("/profile")
def get_profile(
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    return _profile_json(p, db)


@router.put("/profile")
def put_profile(
    body: ProfileUpdate,
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    # Only update fields the client actually supplied.
    # Explicit null values can clear optional fields.
    changes = body.model_dump(exclude_unset=True)

    for field, value in changes.items():
        if field == "preferred_language":
            if value is not None and value.strip():
                p.user.preferred_language = value.strip()
            continue

        if field == "name":
            if value is None or not value.strip():
                continue
            value = value.strip()

        elif field in {
            "blood_group",
            "allergies_text",
            "conditions_text",
            "medicines_text",
            "previous_records",
            "emergency_contact_name",
            "emergency_contact_phone",
            "sex",
        }:
            if isinstance(value, str):
                value = value.strip() or None

        setattr(p, field, value)

    db.commit()
    db.refresh(p)

    return _profile_json(p, db)


@router.delete("/profile", status_code=204)
def delete_profile(
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    delete_profile_data(db, p)
    return Response(status_code=204)


@router.get("/profile/timeline")
def timeline(
    types: str = "reports,medicines,diagnoses",
    p: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    want = set(types.split(","))
    items = []

    docs = {
        document.id: document
        for document in _q(db, p, Document)
    }

    if "reports" in want:
        for document in docs.values():
            if document.status == "done":
                items.append({
                    "type": "document",
                    "date": document.doc_date or document.created_at.date(),
                    "document_id": document.id,
                    "title": (document.doc_type or "document").replace("_", " "),
                    "detail": document.facility,
                    "source": document.source,
                })

        for observation in _q(
            db,
            p,
            Observation,
            Observation.interpretation.in_(ABNORMAL),
        ):
            source_document = docs.get(observation.document_id)
            items.append({
                "type": "abnormal_result",
                "date": observation.effective_at,
                "document_id": observation.document_id,
                "title": observation.display_name,
                "detail": f"{observation.value_num} {observation.unit or ''}".strip(),
                "interpretation": observation.interpretation,
                "source": source_document.source if source_document else None,
            })

    if "medicines" in want:
        for medicine in _q(db, p, Medication):
            source_document = docs.get(medicine.document_id)
            base = {
                "document_id": medicine.document_id,
                "title": medicine.brand_name,
                "source": source_document.source if source_document else None,
            }

            items.append({
                **base,
                "type": "medicine_started",
                "date": medicine.start_date,
                "detail": medicine.dose_pattern,
            })

            if medicine.end_date:
                items.append({
                    **base,
                    "type": "medicine_ended",
                    "date": medicine.end_date,
                    "detail": None,
                })

    if "diagnoses" in want:
        for condition in _q(db, p, Condition):
            source_document = docs.get(condition.document_id)
            items.append({
                "type": "diagnosis",
                "date": condition.recorded_at,
                "document_id": condition.document_id,
                "title": condition.name,
                "detail": None,
                "source": source_document.source if source_document else None,
            })

    # Injury events are derived from stored document extraction.
    # Pregnancy and reproductive-health fields are not exposed here.
    if "injuries" in want:
        for document in docs.values():
            if document.status != "done" or not isinstance(document.extraction, dict):
                continue

            injuries = document.extraction.get("fractures_or_injuries") or []
            if not isinstance(injuries, list):
                continue

            for injury in injuries:
                if not isinstance(injury, dict):
                    continue

                body_site = injury.get("body_site")
                injury_type = injury.get("injury_type")
                findings = injury.get("reported_findings")

                if not any(
                    isinstance(value, str) and value.strip()
                    for value in (body_site, injury_type, findings)
                ):
                    continue

                event_date = None

                for raw_date in (
                    injury.get("date_of_injury"),
                    injury.get("date_of_report"),
                ):
                    if not isinstance(raw_date, str) or not raw_date.strip():
                        continue

                    try:
                        event_date = date.fromisoformat(raw_date.strip())
                        break
                    except ValueError:
                        continue

                event_date = event_date or document.doc_date
                if event_date is None:
                    continue

                side = injury.get("side")
                title_parts = [
                    value.strip()
                    for value in (side, body_site, injury_type)
                    if isinstance(value, str)
                    and value.strip()
                    and value.strip().lower() != "not_stated"
                ]

                items.append({
                    "type": "fracture_injury",
                    "date": event_date,
                    "document_id": document.id,
                    "title": " — ".join(title_parts) or "Reported injury",
                    "detail": (
                        findings
                        if isinstance(findings, str) and findings.strip()
                        else None
                    ),
                    "needs_clinician_review": True,
                    "source": document.source,
                })

    return sorted(
        (item for item in items if item["date"]),
        key=lambda item: item["date"],
        reverse=True,
    )


@router.get("/profile/fhir")
def fhir_export(p: Profile = Depends(current_profile)):
    return to_bundle(p)

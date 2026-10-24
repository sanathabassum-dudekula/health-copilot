from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..access import profile_oid_for
from ..auth import active_profile, current_profile, delete_profile_data
from ..db import get_db
from ..fhir.serialize import to_bundle
from ..models import Allergy, Condition, Document, Medication, Observation, Profile, VitalSign

router = APIRouter(tags=["profile"])
ABNORMAL = ("L", "H", "LL", "HH")


def _q(db: Session, p: Profile, m, *where):
    return db.scalars(select(m).where(m.profile_id == p.id, *where))


class WomensHealthProfile(BaseModel):
    cycle_tracker_enabled: bool = False
    pregnancy_tracker_enabled: bool = False
    menopause_fertility_enabled: bool = False
    screening_enabled: bool = False
    last_period_date: date | None = None
    period_start_dates: list[date] = Field(default_factory=list, max_length=60)
    cycle_length_days: int | None = Field(default=None, ge=1, le=366)
    pregnancy_status: Literal["unknown", "pregnant", "not_pregnant", "postpartum"] = "unknown"
    estimated_due_date: date | None = None
    pregnancy_notes: str | None = Field(default=None, max_length=2000)
    menopause_notes: str | None = Field(default=None, max_length=2000)
    fertility_notes: str | None = Field(default=None, max_length=2000)
    cervical_screening_notes: str | None = Field(default=None, max_length=2000)
    breast_health_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("last_period_date")
    @classmethod
    def last_period_cannot_be_in_the_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("last_period_date cannot be in the future.")
        return value

    @field_validator("period_start_dates")
    @classmethod
    def period_dates_must_be_unique_and_not_future(
        cls, value: list[date]
    ) -> list[date]:
        if len(set(value)) != len(value):
            raise ValueError("period_start_dates must not contain duplicates.")
        if any(day > date.today() for day in value):
            raise ValueError("period_start_dates cannot include future dates.")
        return sorted(value)

    @model_validator(mode="after")
    def clear_disabled_feature_data(self):
        if "cycle_tracker_enabled" in self.model_fields_set and not self.cycle_tracker_enabled:
            self.last_period_date = None
            self.period_start_dates = []
            self.cycle_length_days = None
        elif self.cycle_tracker_enabled:
            if self.last_period_date and self.last_period_date not in self.period_start_dates:
                self.period_start_dates.append(self.last_period_date)
                self.period_start_dates.sort()
            if self.period_start_dates:
                self.last_period_date = self.period_start_dates[-1]
        if "pregnancy_tracker_enabled" in self.model_fields_set and not self.pregnancy_tracker_enabled:
            self.pregnancy_status = "unknown"
            self.estimated_due_date = None
            self.pregnancy_notes = None
        if "menopause_fertility_enabled" in self.model_fields_set and not self.menopause_fertility_enabled:
            self.menopause_notes = None
            self.fertility_notes = None
        if "screening_enabled" in self.model_fields_set and not self.screening_enabled:
            self.cervical_screening_notes = None
            self.breast_health_notes = None
        return self


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    dob: date | None = None
    sex: str | None = Field(default=None, max_length=40)
    age: int | None = Field(default=None, ge=0, le=130)
    blood_group: str | None = Field(default=None, max_length=10)
    allergies_text: str | None = Field(default=None, max_length=5000)
    conditions_text: str | None = Field(default=None, max_length=5000)
    medicines_text: str | None = Field(default=None, max_length=5000)
    previous_records: str | None = Field(default=None, max_length=5000)
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: str | None = Field(default=None, max_length=40)
    preferred_language: Literal["en", "hi", "te", "ta"] | None = None
    preferred_voice_language: Literal["en", "hi", "te", "ta"] | None = None
    voice_reminders_enabled: bool | None = None
    family_reminders_enabled: bool | None = None
    womens_health_profile: WomensHealthProfile | None = None


def _age(dob: date | None) -> int | None:
    if not dob:
        return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def _profile_json(p: Profile, db: Session) -> dict:
    today = date.today()
    meds = _q(db, p, Medication, or_(Medication.end_date.is_(None), Medication.end_date >= today))  # "current" is computed
    latest: dict[str, Observation] = {}
    for o in sorted(_q(db, p, Observation, Observation.interpretation.in_(ABNORMAL)), key=lambda o: o.effective_at or date.min):
        latest[o.display_name] = o
    return {
        "oid": profile_oid_for(p),
        "name": p.name, "dob": p.dob, "age": _age(p.dob) if p.dob else p.age, "sex": p.sex, "language": p.user.preferred_language,
        "voice_language": p.user.preferred_voice_language,
        "voice_reminders_enabled": p.user.voice_reminders_enabled,
        "family_reminders_enabled": p.family_reminders_enabled,
        "womens_health_profile": WomensHealthProfile.model_validate(
            p.womens_health_profile or {}
        ).model_dump(mode="json"),
        "blood_group": p.blood_group,
        "allergies_text": p.allergies_text,
        "conditions_text": p.conditions_text,
        "medicines_text": p.medicines_text,
        "previous_records": p.previous_records,
        "emergency_contact_name": p.emergency_contact_name,
        "emergency_contact_phone": p.emergency_contact_phone,
        "abha": {"number": p.abha_number, "address": p.abha_address, "linked": bool(p.abha_linked_at)},
        "conditions": sorted({c.name for c in _q(db, p, Condition)}),
        "allergies": sorted({a.substance for a in _q(db, p, Allergy)}),
        "current_medicines": [{"name": m.brand_name, "salt": m.salt, "dose_pattern": m.dose_pattern,
                               "document_id": m.document_id} for m in meds],
        "latest_abnormal": [{"test": o.display_name, "value": o.value_num if o.value_num is not None else o.value_text,
                             "unit": o.unit, "interpretation": o.interpretation, "date": o.effective_at,
                             "ref_low": o.ref_low, "ref_high": o.ref_high,
                             "document_id": o.document_id} for o in latest.values()],
    }


@router.get("/profile")
def get_profile(p: Profile = Depends(active_profile), db: Session = Depends(get_db)):
    return _profile_json(p, db)


@router.put("/profile")
def put_profile(body: ProfileUpdate, p: Profile = Depends(active_profile), db: Session = Depends(get_db)):
    if "name" in body.model_fields_set and (body.name is None or not body.name.strip()):
        raise HTTPException(status_code=422, detail="Name cannot be blank.")

    user_fields = {
        "preferred_language",
        "preferred_voice_language",
        "voice_reminders_enabled",
    }
    changes = body.model_dump(exclude_unset=True)
    changes.pop("womens_health_profile", None)
    womens_health = body.womens_health_profile
    if "womens_health_profile" in body.model_fields_set and womens_health is None:
        raise HTTPException(status_code=422, detail="womens_health_profile cannot be blank.")
    for field in user_fields & changes.keys():
        value = changes[field]
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be blank.")
        setattr(p.user, field, value)
    for field in changes.keys() - user_fields:
        value = changes[field]
        if field == "name":
            value = value.strip()
        setattr(p, field, value)
    if womens_health is not None:
        merged_womens_health = WomensHealthProfile.model_validate(
            p.womens_health_profile or {}
        ).model_dump(mode="python")
        merged_womens_health.update(womens_health.model_dump(exclude_unset=True))
        p.womens_health_profile = WomensHealthProfile.model_validate(
            merged_womens_health
        ).model_dump(mode="json")
    db.commit()
    return _profile_json(p, db)


@router.delete("/profile", status_code=204)
def delete_profile(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    delete_profile_data(db, p)
    return Response(status_code=204)


@router.get("/profile/timeline")
def timeline(types: str = "reports,medicines,diagnoses,vitals", p: Profile = Depends(active_profile),
             db: Session = Depends(get_db)):
    want = set(types.split(","))
    items = []
    docs = {d.id: d for d in _q(db, p, Document)}  # one query, shared by every section
    if "reports" in want:
        for d in docs.values():
            if d.status == "done":
                items.append({"type": "document", "date": d.doc_date or d.created_at.date(), "document_id": d.id,
                              "title": (d.doc_type or "document").replace("_", " "), "detail": d.facility,
                              "source": d.source})
        for o in _q(db, p, Observation, Observation.interpretation.in_(ABNORMAL)):
            items.append({"type": "abnormal_result", "date": o.effective_at, "document_id": o.document_id,
                          "title": o.display_name, "detail": f"{o.value_num} {o.unit or ''}".strip(),
                          "interpretation": o.interpretation, "source": docs[o.document_id].source})
    if "medicines" in want:
        for m in _q(db, p, Medication):
            base = {"document_id": m.document_id, "title": m.brand_name, "source": docs[m.document_id].source}
            items.append({**base, "type": "medicine_started", "date": m.start_date, "detail": m.dose_pattern})
            if m.end_date:
                items.append({**base, "type": "medicine_ended", "date": m.end_date, "detail": None})
    if "diagnoses" in want:
        for c in _q(db, p, Condition):
            items.append({"type": "diagnosis", "date": c.recorded_at, "document_id": c.document_id,
                          "title": c.name, "detail": None, "source": docs[c.document_id].source})
    if "vitals" in want:
        for vital in db.scalars(
            select(VitalSign)
            .where(VitalSign.profile_id == p.id)
            .order_by(VitalSign.captured_at.desc(), VitalSign.id.desc())
            .limit(100)
        ):
            captured_at = vital.captured_at
            if captured_at.tzinfo is None:
                captured_at = captured_at.replace(tzinfo=timezone.utc)
            else:
                captured_at = captured_at.astimezone(timezone.utc)
            items.append({
                "type": "vital_sign",
                "date": captured_at,
                "captured_at": captured_at.isoformat(),
                "document_id": None,
                "title": vital.metric,
                "detail": f"{vital.value:g} {vital.unit}",
                "source": vital.source,
                "device_name": vital.device_name,
            })

    # Injury events are derived from the document's stored extraction.
    # Do not expose pregnancy or reproductive-health fields in this general timeline.
    if "injuries" in want:
        for d in docs.values():
            if d.status != "done" or not isinstance(d.extraction, dict):
                continue
            injuries = d.extraction.get("fractures_or_injuries") or []
            if not isinstance(injuries, list):
                continue

            for injury in injuries:
                if not isinstance(injury, dict):
                    continue

                body_site = injury.get("body_site")
                injury_type = injury.get("injury_type")
                findings = injury.get("reported_findings")
                if not any(isinstance(v, str) and v.strip()
                           for v in (body_site, injury_type, findings)):
                    continue

                event_date = None
                for raw_date in (injury.get("date_of_injury"), injury.get("date_of_report")):
                    if not isinstance(raw_date, str) or not raw_date.strip():
                        continue
                    try:
                        event_date = date.fromisoformat(raw_date.strip())
                        break
                    except ValueError:
                        continue
                event_date = event_date or d.doc_date
                if event_date is None:
                    continue

                side = injury.get("side")
                title_parts = [str(v).strip() for v in (side, body_site, injury_type)
                               if isinstance(v, str) and v.strip()
                               and v.strip().lower() != "not_stated"]
                items.append({
                    "type": "fracture_injury",
                    "date": event_date,
                    "document_id": d.id,
                    "title": " — ".join(title_parts) or "Reported injury",
                    "detail": findings if isinstance(findings, str) and findings.strip() else None,
                    "needs_clinician_review": True,
                    "source": d.source,
                })

    def sort_date(item: dict) -> datetime:
        value = item["date"]
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
        return datetime.combine(value, datetime.min.time())

    return sorted((i for i in items if i["date"]), key=sort_date, reverse=True)


@router.get("/profile/fhir")
def fhir_export(p: Profile = Depends(active_profile)):
    return to_bundle(p)

from datetime import date

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import current_profile, delete_profile_data
from ..db import get_db
from ..fhir.serialize import to_bundle
from ..models import Allergy, Condition, Document, Medication, Observation, Profile

router = APIRouter(tags=["profile"])
ABNORMAL = ("L", "H", "LL", "HH")


def _q(db: Session, p: Profile, m, *where):
    return db.scalars(select(m).where(m.profile_id == p.id, *where))


class ProfileUpdate(BaseModel):
    name: str | None = None
    dob: date | None = None
    sex: str | None = None
    preferred_language: str | None = None


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
        "name": p.name, "dob": p.dob, "age": _age(p.dob), "sex": p.sex, "language": p.user.preferred_language,
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
def get_profile(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    return _profile_json(p, db)


@router.put("/profile")
def put_profile(body: ProfileUpdate, p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    for k in ("name", "dob", "sex"):
        if (v := getattr(body, k)) is not None:
            setattr(p, k, v)
    if body.preferred_language:
        p.user.preferred_language = body.preferred_language
    db.commit()
    return _profile_json(p, db)


@router.delete("/profile", status_code=204)
def delete_profile(p: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    delete_profile_data(db, p)
    return Response(status_code=204)


@router.get("/profile/timeline")
def timeline(types: str = "reports,medicines,diagnoses", p: Profile = Depends(current_profile),
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

    return sorted((i for i in items if i["date"]), key=lambda i: i["date"], reverse=True)


@router.get("/profile/fhir")
def fhir_export(p: Profile = Depends(current_profile)):
    return to_bundle(p)

from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import confirmed_document_ids, is_requested_profile, profile_oid_for
from ..auth import active_profile
from ..db import get_db
from ..models import (
    Allergy,
    Condition,
    Document,
    Medication,
    Observation,
    Profile,
)

router = APIRouter(prefix="/insights", tags=["insights"])
ABNORMAL = {"L", "H", "LL", "HH"}


@router.get("")
def get_insights(
    profile_oid: str | None = None,
    profile: Profile = Depends(active_profile),
    db: Session = Depends(get_db),
):
    if not is_requested_profile(profile, profile_oid):
        raise HTTPException(status_code=404, detail="Profile not found")

    observations = db.scalars(
        select(Observation)
        .where(
            Observation.profile_id == profile.id,
            Observation.document_id.in_(confirmed_document_ids(profile.id)),
        )
        .order_by(Observation.effective_at, Observation.id)
    ).all()
    grouped: dict[tuple[str, str | None], list[Observation]] = defaultdict(list)
    for observation in observations:
        if observation.value_num is not None:
            grouped[(observation.display_name.casefold(), observation.unit)].append(
                observation
            )

    trends = []
    for history in grouped.values():
        if len(history) < 2:
            continue
        earlier, latest = history[-2:]
        if earlier.value_num == latest.value_num:
            direction = "stable"
        elif latest.value_num > earlier.value_num:
            direction = "increased"
        else:
            direction = "decreased"
        trends.append({
            "test": latest.display_name,
            "unit": latest.unit,
            "previous_value": earlier.value_num,
            "latest_value": latest.value_num,
            "previous_date": earlier.effective_at,
            "latest_date": latest.effective_at,
            "direction": direction,
            "latest_flag": latest.interpretation,
            "document_id": latest.document_id,
        })

    flagged_results = [
        {
            "test": item.display_name,
            "value": item.value_num if item.value_num is not None else item.value_text,
            "unit": item.unit,
            "flag": item.interpretation,
            "date": item.effective_at,
            "document_id": item.document_id,
        }
        for item in observations
        if item.interpretation in ABNORMAL
    ][-10:]

    follow_ups = []
    documents = db.scalars(
        select(Document)
        .where(
            Document.profile_id == profile.id,
            Document.status == "done",
            Document.review_status == "confirmed",
        )
        .order_by(Document.doc_date.desc(), Document.created_at.desc())
    ).all()
    for document in documents:
        extraction = document.extraction if isinstance(document.extraction, dict) else {}
        candidates = [extraction.get("follow_up")]
        candidates.extend(
            item.get("follow_up_plan")
            for item in extraction.get("fractures_or_injuries", [])
            if isinstance(item, dict)
        )
        candidates.extend((document.summary or {}).get("next_steps", []))
        for text in candidates:
            if isinstance(text, str) and text.strip() and text.strip() not in follow_ups:
                follow_ups.append(text.strip())
                if len(follow_ups) == 10:
                    break
        if len(follow_ups) == 10:
            break

    active_medicines = db.scalars(
        select(Medication).where(
            Medication.profile_id == profile.id,
            Medication.document_id.in_(confirmed_document_ids(profile.id)),
            (Medication.end_date.is_(None)) | (Medication.end_date >= date.today()),
        )
    ).all()
    medicine_reminder_suggestions = [
        {
            "name": medicine.brand_name,
            "dose_pattern": medicine.dose_pattern,
            "timing": medicine.timing,
            "document_id": medicine.document_id,
        }
        for medicine in active_medicines[:10]
    ]
    conditions = db.scalars(
        select(Condition.name).where(
            Condition.profile_id == profile.id,
            Condition.document_id.in_(confirmed_document_ids(profile.id)),
        )
    ).all()
    allergies = db.scalars(
        select(Allergy.substance).where(
            Allergy.profile_id == profile.id,
            Allergy.document_id.in_(confirmed_document_ids(profile.id)),
        )
    ).all()

    wellness = [
        {
            "kind": "general",
        }
    ]
    if conditions or allergies or active_medicines:
        wellness.insert(0, {"kind": "records"})
    if not observations and not documents:
        wellness.append({"kind": "add_records"})

    return {
        "profile": {"oid": profile_oid_for(profile), "name": profile.name},
        "flagged_results": flagged_results,
        "trends": trends[-20:],
        "follow_ups": follow_ups,
        "medicine_reminder_suggestions": medicine_reminder_suggestions,
        "wellness": wellness,
    }

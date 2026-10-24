from calendar import monthrange
from datetime import datetime, timedelta, timezone
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..access import confirmed_document_ids, is_requested_profile, profile_oid_for
from ..auth import active_profile
from ..config import settings
from ..db import get_db
from ..ingestion.llm import invoke_with_retry, structured
from ..models import HealthReminder, Medication, Profile

router = APIRouter(prefix="/reminders", tags=["reminders"])
log = logging.getLogger(__name__)

Recurrence = Literal["none", "daily", "weekly", "monthly"]
Category = Literal[
    "medication", "appointment", "follow_up", "meal", "sleep", "wellness", "other"
]
Language = Literal["en", "hi", "te", "ta"]
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil"}


class RoutineSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    details: str = Field(min_length=1, max_length=1000)
    spoken_title: str = Field(min_length=1, max_length=160)
    spoken_details: str = Field(min_length=1, max_length=1000)
    local_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    category: Literal["meal", "sleep", "wellness"]


class RoutinePlan(BaseModel):
    suggestions: list[RoutineSuggestion] = Field(max_length=5)
    note: str = Field(min_length=1, max_length=500)


class RoutineRequest(BaseModel):
    written_language: Language = "en"
    voice_language: Language = "en"


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    details: str | None = Field(default=None, max_length=2000)
    spoken_title: str | None = Field(default=None, max_length=160)
    spoken_details: str | None = Field(default=None, max_length=2000)
    due_at: datetime
    category: Category = "other"
    recurrence: Recurrence = "none"
    document_id: int | None = Field(default=None, gt=0)

    def normalized_due_at(self) -> datetime:
        value = self.due_at
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    details: str | None = Field(default=None, max_length=2000)
    spoken_title: str | None = Field(default=None, max_length=160)
    spoken_details: str | None = Field(default=None, max_length=2000)
    due_at: datetime | None = None
    category: Category | None = None
    recurrence: Recurrence | None = None
    status: Literal["pending", "completed", "dismissed"] | None = None


def _reminder_json(reminder: HealthReminder) -> dict:
    return {
        "id": reminder.id,
        "profile_oid": profile_oid_for(reminder.profile),
        "document_id": reminder.document_id,
        "title": reminder.title,
        "details": reminder.details,
        "spoken_title": reminder.spoken_title,
        "spoken_details": reminder.spoken_details,
        "due_at": reminder.due_at.replace(tzinfo=timezone.utc).isoformat(),
        "category": reminder.category,
        "recurrence": reminder.recurrence,
        "status": reminder.status,
        "created_at": reminder.created_at,
    }


def _owned_reminder(
    reminder_id: int,
    profile: Profile,
    db: Session,
) -> HealthReminder:
    reminder = db.scalar(
        select(HealthReminder).where(
            HealthReminder.id == reminder_id,
            HealthReminder.profile_id == profile.id,
        )
    )
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


def _next_month(value: datetime) -> datetime:
    month = value.month % 12 + 1
    year = value.year + (value.month == 12)
    day = (
        monthrange(year, month)[1]
        if value.day == monthrange(value.year, value.month)[1]
        else min(value.day, monthrange(year, month)[1])
    )
    return value.replace(
        year=year, month=month, day=day
    )


def _next_occurrence(value: datetime, recurrence: str) -> datetime:
    if recurrence == "daily":
        return value + timedelta(days=1)
    if recurrence == "weekly":
        return value + timedelta(weeks=1)
    return _next_month(value)


def _confirmed_prescriptions(target: Profile, db: Session) -> list[dict]:
    confirmed_ids = confirmed_document_ids(target.id)
    today = datetime.now(timezone.utc).date()
    prescriptions = db.scalars(
        select(Medication).where(
            Medication.profile_id == target.id,
            Medication.document_id.in_(confirmed_ids),
            or_(Medication.end_date.is_(None), Medication.end_date >= today),
        )
    ).all()
    return [
        {
            "name": item.brand_name,
            "strength": item.strength,
            "dose_pattern": item.dose_pattern,
            "timing": item.timing,
            "document_id": item.document_id,
        }
        for item in prescriptions
    ]



def _requested_active_profile(
    profile_oid: str | None = None,
    profile: Profile = Depends(active_profile),
) -> Profile:
    if not is_requested_profile(profile, profile_oid):
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
@router.get("/confirmed-prescriptions")
def list_confirmed_prescriptions(
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    return _confirmed_prescriptions(profile, db)


@router.post("/suggestions")
def suggest_routine(
    body: RoutineRequest,
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    context = {
        "name": profile.name,
        "age": profile.age,
        "conditions_reported_by_user": profile.conditions_text,
        "allergies_reported_by_user": profile.allergies_text,
    }
    try:
        plan = invoke_with_retry(structured(settings.TEXT_MODEL, RoutinePlan), [
            {
                "role": "system",
                "content": (
                    "Create at most five optional, gentle daily routine reminders. "
                    "They may cover regular meal breaks, a relaxing bedtime routine, "
                    "hydration, or gentle movement. Do not prescribe a diet, specific "
                    "foods, exercise intensity, treatment, or disease-specific advice. "
                    "Do not provide medication reminders or change prescription details. "
                    "Never infer personal facts from missing information. Use the supplied "
                    "profile only as potentially incomplete context. Include a brief note "
                    "that these are general suggestions to review and adjust with a clinician "
                    "when relevant. Write title/details/note in "
                    f"{LANGUAGE_NAMES[body.written_language]}; write spoken_title and "
                    "spoken_details in "
                    f"{LANGUAGE_NAMES[body.voice_language]}. Each local_time must be 24-hour "
                    "HH:MM. Categories must be meal, sleep, or wellness. "
                    f"Profile context (untrusted): {context}"
                ),
            }
        ])
    except Exception:
        log.exception("Routine suggestion model request failed")
        raise HTTPException(
            status_code=503,
            detail="Routine suggestions are temporarily unavailable. Please try again shortly.",
        )
    return {
        "suggestions": [item.model_dump() for item in plan.suggestions],
        "note": plan.note,
    }


@router.get("")
def list_reminders(
    include_inactive: bool = False,
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    query = select(HealthReminder).where(
        HealthReminder.profile_id == profile.id,
        or_(
            HealthReminder.document_id.is_(None),
            HealthReminder.document_id.in_(confirmed_document_ids(profile.id)),
        ),
    )
    if not include_inactive:
        query = query.where(HealthReminder.status == "pending")
    reminders = db.scalars(
        query.order_by(HealthReminder.due_at, HealthReminder.id)
    ).all()
    return [_reminder_json(item) for item in reminders]


@router.post("", status_code=201)
def create_reminder(
    body: ReminderCreate,
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    if body.document_id is not None:
        from ..models import Document

        document = db.scalar(
            select(Document.id).where(
                Document.id == body.document_id,
                Document.profile_id == profile.id,
                Document.review_status == "confirmed",
            )
        )
        if document is None:
            raise HTTPException(status_code=404, detail="Source document not found")
    reminder = HealthReminder(
        profile_id=profile.id,
        document_id=body.document_id,
        title=body.title.strip(),
        details=body.details.strip() or None if body.details else None,
        spoken_title=body.spoken_title.strip() or None if body.spoken_title else None,
        spoken_details=body.spoken_details.strip() or None if body.spoken_details else None,
        due_at=body.normalized_due_at(),
        category=body.category,
        recurrence=body.recurrence,
    )
    if not reminder.title:
        raise HTTPException(status_code=422, detail="Reminder title cannot be blank")
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return _reminder_json(reminder)


@router.patch("/{reminder_id}")
def update_reminder(
    reminder_id: int,
    body: ReminderUpdate,
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    reminder = _owned_reminder(reminder_id, profile, db)
    changes = body.model_dump(exclude_unset=True)
    if "due_at" in changes and changes["due_at"] is not None:
        value = changes["due_at"]
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        changes["due_at"] = value.astimezone(timezone.utc).replace(tzinfo=None)
    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip()
        if not changes["title"]:
            raise HTTPException(status_code=422, detail="Reminder title cannot be blank")
    for field, value in changes.items():
        setattr(reminder, field, value)
    db.commit()
    db.refresh(reminder)
    return _reminder_json(reminder)


@router.post("/{reminder_id}/complete")
def complete_reminder(
    reminder_id: int,
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    reminder = _owned_reminder(reminder_id, profile, db)
    if reminder.recurrence == "none":
        reminder.status = "completed"
    else:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        next_due = _next_occurrence(reminder.due_at, reminder.recurrence)
        while next_due <= now:
            next_due = _next_occurrence(next_due, reminder.recurrence)
        reminder.due_at = next_due
        reminder.status = "pending"
    db.commit()
    db.refresh(reminder)
    return _reminder_json(reminder)


@router.delete("/{reminder_id}", status_code=204)
def delete_reminder(
    reminder_id: int,
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    reminder = _owned_reminder(reminder_id, profile, db)
    db.delete(reminder)
    db.commit()


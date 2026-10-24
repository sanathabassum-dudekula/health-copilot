import base64
import binascii
from calendar import monthrange
from datetime import datetime, timedelta, timezone
import hmac
import json
import logging
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..access import confirmed_document_ids, is_requested_profile, profile_oid_for
from ..auth import active_profile
from ..config import settings
from ..db import get_db
from ..ingestion.llm import invoke_with_retry, structured
from ..models import (
    Document,
    FamilyLink,
    HealthReminder,
    Medication,
    Profile,
    PushDelivery,
    PushSubscription,
)
from pywebpush import WebPushException, webpush

router = APIRouter(prefix="/reminders", tags=["reminders"])
log = logging.getLogger(__name__)

Recurrence = Literal["none", "daily", "weekly", "monthly"]
Category = Literal[
    "medication", "appointment", "follow_up", "meal", "sleep", "wellness", "other"
]
Language = Literal["en", "hi", "te", "ta"]
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil"}
MAX_PUSH_ATTEMPTS_PER_RUN = 10
ALLOWED_PUSH_HOSTS = {
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "web.push.apple.com",
}


def _push_credentials_configured() -> bool:
    return all((
        settings.VAPID_PUBLIC_KEY.strip(),
        settings.VAPID_PRIVATE_KEY.strip(),
        settings.VAPID_SUBJECT.strip(),
    ))


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


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)
    keys: PushSubscriptionKeys


class PushSubscriptionDelete(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)


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


def _push_endpoint_is_allowed(endpoint: str) -> bool:
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and (
            host in ALLOWED_PUSH_HOSTS
            or host.endswith(".notify.windows.com")
        )
    )


def _decode_base64url(value: str) -> bytes:
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, binascii.Error) as error:
        raise ValueError("Invalid base64url value") from error


def _push_keys_are_valid(keys: PushSubscriptionKeys) -> bool:
    try:
        public_key = _decode_base64url(keys.p256dh)
        auth_secret = _decode_base64url(keys.auth)
    except ValueError:
        return False
    return len(public_key) == 65 and public_key[0] == 4 and len(auth_secret) == 16


def _vapid_private_key_pem() -> str:
    value = settings.VAPID_PRIVATE_KEY.strip()
    if value.startswith("-----BEGIN"):
        return value

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    try:
        decoded = _decode_base64url(value)
        try:
            private_key = serialization.load_der_private_key(decoded, password=None)
        except ValueError:
            if len(decoded) != 32:
                raise ValueError("VAPID private key must be PEM or a base64url P-256 key")
            private_key = ec.derive_private_key(
                int.from_bytes(decoded, "big"), ec.SECP256R1()
            )
    except (ValueError, TypeError) as error:
        raise ValueError("VAPID private key is not valid PEM or base64url") from error

    if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(
        private_key.curve, ec.SECP256R1
    ):
        raise ValueError("VAPID private key must use the P-256 curve")
    public_key = _decode_base64url(settings.VAPID_PUBLIC_KEY.strip())
    expected_public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    if not hmac.compare_digest(public_key, expected_public_key):
        raise ValueError("VAPID public and private keys do not match")
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


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


def _family_profiles(profile: Profile, db: Session) -> list[Profile]:
    owner_user_ids = set(
        db.scalars(
            select(FamilyLink.owner_user_id).where(
                FamilyLink.member_user_id == profile.user_id
            )
        ).all()
    )
    owner_user_ids.add(profile.user_id)
    member_user_ids = db.scalars(
        select(FamilyLink.member_user_id).where(
            FamilyLink.owner_user_id.in_(owner_user_ids)
        )
    ).all()
    user_ids = owner_user_ids.union(member_user_ids)
    return db.scalars(
        select(Profile).where(Profile.user_id.in_(user_ids))
    ).all()



def _requested_active_profile(
    profile_oid: str | None = None,
    profile: Profile = Depends(active_profile),
) -> Profile:
    if not is_requested_profile(profile, profile_oid):
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/push/config", dependencies=[Depends(_requested_active_profile)])
def get_push_config():
    enabled = _push_credentials_configured()
    if enabled:
        try:
            _vapid_private_key_pem()
        except ValueError as error:
            log.error("Reminder push credentials are invalid")
            raise HTTPException(
                status_code=503,
                detail="Push notifications are misconfigured",
            ) from error
    return {
        "enabled": enabled,
        "public_key": settings.VAPID_PUBLIC_KEY.strip() if enabled else None,
    }


@router.post("/push/subscriptions", status_code=201)
def save_push_subscription(
    body: PushSubscriptionCreate,
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    if not _push_credentials_configured():
        raise HTTPException(status_code=503, detail="Push notifications are not configured")
    if not _push_endpoint_is_allowed(body.endpoint):
        raise HTTPException(status_code=422, detail="Unsupported push service endpoint")
    if not _push_keys_are_valid(body.keys):
        raise HTTPException(status_code=422, detail="Invalid push subscription keys")

    subscription = db.scalar(
        select(PushSubscription).where(
            PushSubscription.profile_id == profile.id,
            PushSubscription.endpoint == body.endpoint,
        )
    )
    if subscription is None:
        subscription = PushSubscription(
            profile_id=profile.id,
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
        )
        db.add(subscription)
    else:
        subscription.p256dh = body.keys.p256dh
        subscription.auth = body.keys.auth
    db.commit()
    return {"subscribed": True}


@router.delete("/push/subscriptions", status_code=204)
def delete_push_subscription(
    body: PushSubscriptionDelete,
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    subscription = db.scalar(
        select(PushSubscription).where(
            PushSubscription.profile_id == profile.id,
            PushSubscription.endpoint == body.endpoint,
        )
    )
    if subscription is not None:
        db.delete(subscription)
        db.commit()


@router.get("/dispatch")
def dispatch_due_reminders(
    request: Request,
    db: Session = Depends(get_db),
):
    if not settings.CRON_SECRET:
        raise HTTPException(status_code=503, detail="Reminder scheduler is not configured")
    if not hmac.compare_digest(
        request.headers.get("authorization", ""),
        f"Bearer {settings.CRON_SECRET}",
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not _push_credentials_configured():
        raise HTTPException(status_code=503, detail="Push notifications are not configured")
    try:
        private_key = _vapid_private_key_pem()
    except ValueError as error:
        log.error("Reminder push credentials are invalid")
        raise HTTPException(status_code=503, detail="Push notifications are misconfigured") from error

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    due_reminders = db.scalars(
        select(HealthReminder)
        .where(
            HealthReminder.status == "pending",
            HealthReminder.due_at <= now,
        )
        .order_by(HealthReminder.due_at, HealthReminder.id)
        .limit(100)
        .with_for_update(skip_locked=True)
    ).all()

    attempted = delivered = expired = failed = 0
    stop = False
    for reminder in due_reminders:
        recipient_profile_ids = {reminder.profile_id}
        if reminder.profile.family_reminders_enabled:
            recipient_profile_ids.update(
                family_profile.id
                for family_profile in _family_profiles(reminder.profile, db)
                if family_profile.family_reminders_enabled
            )
        subscriptions = db.scalars(
            select(PushSubscription).where(
                PushSubscription.profile_id.in_(recipient_profile_ids)
            )
        ).all()
        for subscription in subscriptions:
            already_sent = db.scalar(
                select(PushDelivery.id).where(
                    PushDelivery.reminder_id == reminder.id,
                    PushDelivery.subscription_id == subscription.id,
                    PushDelivery.due_at == reminder.due_at,
                )
            )
            if already_sent is not None:
                continue
            if attempted >= MAX_PUSH_ATTEMPTS_PER_RUN:
                stop = True
                break
            attempted += 1
            try:
                webpush(
                    subscription_info={
                        "endpoint": subscription.endpoint,
                        "keys": {
                            "p256dh": subscription.p256dh,
                            "auth": subscription.auth,
                        },
                    },
                    data=json.dumps({
                        "title": "CuraMind reminder",
                        "body": (
                            "A family reminder is due. Open CuraMind to view it."
                            if subscription.profile_id != reminder.profile_id
                            else "A scheduled reminder is due. Open CuraMind to view it."
                        ),
                        "url": (
                            "/reminders?family=1"
                            if subscription.profile_id != reminder.profile_id
                            else "/reminders"
                        ),
                        "reminder_id": reminder.id,
                    }),
                    vapid_private_key=private_key,
                    vapid_claims={"sub": settings.VAPID_SUBJECT.strip()},
                    ttl=3600,
                    timeout=5,
                )
            except WebPushException as error:
                status_code = error.response.status_code if error.response else None
                if status_code in (404, 410):
                    db.delete(subscription)
                    expired += 1
                else:
                    log.warning(
                        "Web Push delivery failed for subscription %s with status %s",
                        subscription.id,
                        status_code,
                    )
                    failed += 1
            else:
                db.add(PushDelivery(
                    reminder_id=reminder.id,
                    subscription_id=subscription.id,
                    due_at=reminder.due_at,
                ))
                delivered += 1
        if stop:
            break

    db.commit()
    return {
        "attempted": attempted,
        "delivered": delivered,
        "expired_subscriptions": expired,
        "failed": failed,
    }


@router.get("/confirmed-prescriptions")
def list_confirmed_prescriptions(
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    return _confirmed_prescriptions(profile, db)


@router.get("/family")
def list_family_shared_reminders(
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    if not profile.family_reminders_enabled:
        raise HTTPException(
            status_code=403,
            detail="Enable family reminder sharing for this profile to view shared reminders.",
        )
    group_profiles = _family_profiles(profile, db)
    shared_profiles = [
        item for item in group_profiles if item.family_reminders_enabled
    ]
    if not shared_profiles:
        return []
    shared_profile_ids = [item.id for item in shared_profiles]
    confirmed_docs = select(Document.id).where(
        Document.profile_id.in_(shared_profile_ids),
        Document.review_status == "confirmed",
    )
    items = db.scalars(
        select(HealthReminder)
        .where(
            HealthReminder.profile_id.in_(shared_profile_ids),
            HealthReminder.profile_id != profile.id,
            HealthReminder.status == "pending",
            or_(
                HealthReminder.document_id.is_(None),
                HealthReminder.document_id.in_(confirmed_docs),
            ),
        )
        .order_by(HealthReminder.due_at, HealthReminder.id)
        .limit(100)
    ).all()
    return [
        {
            **_reminder_json(item),
            "profile_name": item.profile.name,
        }
        for item in items
    ]


@router.post("/suggestions")
def suggest_routine(
    body: RoutineRequest,
    profile: Profile = Depends(_requested_active_profile),
    db: Session = Depends(get_db),
):
    prescriptions = _confirmed_prescriptions(profile, db)
    context = {
        "name": profile.name,
        "age": profile.age,
        "conditions_reported_by_user": profile.conditions_text,
        "allergies_reported_by_user": profile.allergies_text,
        "confirmed_prescriptions": [
            {
                "name": item["name"],
                "strength": item["strength"],
                "dose_pattern": item["dose_pattern"],
                "timing": item["timing"],
            }
            for item in prescriptions
        ],
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
                    "Use confirmed prescription information only as context to avoid "
                    "conflicting with the clinician-provided routine. Never recommend a "
                    "medication, dose, frequency, or medication time. Medication reminders "
                    "must be separately reviewed and confirmed by the user. "
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
        "routine_basis": "confirmed_prescriptions" if prescriptions else "general",
        "confirmed_prescription_count": len(prescriptions),
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

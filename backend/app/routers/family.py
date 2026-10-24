import re
from datetime import date, datetime, timedelta, timezone
from secrets import token_hex, token_urlsafe
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import (
    SESSION_COOKIE,
    get_auth_session,
    hash_password,
    token_digest,
    verify_password,
)
from ..config import settings
from ..db import get_db
from ..models import AuthSession, FamilyInvitation, FamilyLink, Profile, User
from ..sms import SmsConfigurationError, SmsDeliveryError, send_twilio_sms

router = APIRouter(prefix="/family", tags=["family"])
PIN_ATTEMPT_LIMIT = 5
PIN_LOCK_DURATION = timedelta(minutes=1)
INVITATION_LIFETIME = timedelta(days=30)


class FamilyMemberFields(BaseModel):
    name: str = Field(min_length=1, max_length=120)
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


class FamilyMemberCreate(FamilyMemberFields):
    pin: str = Field(pattern=r"^\d{6}$")


class FamilyMemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
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


class PinBody(BaseModel):
    pin: str = Field(pattern=r"^\d{6}$")


class ResetPinBody(BaseModel):
    account_password: str = Field(min_length=1, max_length=128)
    new_pin: str = Field(pattern=r"^\d{6}$")


class InvitationCreate(BaseModel):
    phone_number: str = Field(min_length=1, max_length=32)
    relationship_label: str | None = Field(default=None, max_length=80)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        value = value.strip()
        if re.fullmatch(r"[+\d().\-\s]+", value) is None:
            raise ValueError("Phone number contains unsupported characters")
        digits = re.sub(r"\D", "", value)
        if not 8 <= len(digits) <= 15:
            raise ValueError("Phone number must contain 8 to 15 digits")
        if not value.startswith("+"):
            raise ValueError("Use an international phone number beginning with +")
        return value

    @field_validator("relationship_label")
    @classmethod
    def normalize_relationship_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class InvitationAccept(BaseModel):
    token: str = Field(min_length=40, max_length=128)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _signed_in_owner(
    request: Request, db: Session
) -> tuple[Profile, User, AuthSession]:
    session = get_auth_session(request.cookies.get(SESSION_COOKIE), db)
    if session is None:
        raise HTTPException(status_code=401, detail="Sign in to manage family profiles.")

    owner = db.get(User, session.user_id)
    if owner is None or owner.profile is None:
        raise HTTPException(status_code=401, detail="Account profile not found.")
    return owner.profile, owner, session


def _new_oid(db: Session) -> str:
    for _ in range(10):
        oid = "CM-" + token_hex(16).upper()
        if db.scalar(select(Profile.id).where(Profile.oid == oid)) is None:
            return oid
    raise HTTPException(status_code=503, detail="Could not generate a unique profile ID.")


def _owned_member(db: Session, owner: Profile, oid: str) -> Profile:
    member = db.scalar(
        select(Profile)
        .join(FamilyLink, FamilyLink.member_user_id == Profile.user_id)
        .where(
            FamilyLink.owner_user_id == owner.user_id,
            Profile.oid == oid,
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Family member not found.")
    return member


def _member_json(member: Profile) -> dict:
    return {
        "oid": member.oid,
        "name": member.name,
        "dob": member.dob,
        "sex": member.sex,
        "age": member.age,
        "blood_group": member.blood_group,
        "allergies_text": member.allergies_text,
        "conditions_text": member.conditions_text,
        "medicines_text": member.medicines_text,
        "previous_records": member.previous_records,
        "emergency_contact_name": member.emergency_contact_name,
        "emergency_contact_phone": member.emergency_contact_phone,
        "has_pin": member.pin_hash is not None,
    }


def _set_pin(member: Profile, pin: str) -> None:
    member.pin_hash = hash_password(pin)
    member.pin_failed_attempts = 0
    member.pin_locked_until = None


def _invitation_json(invitation: FamilyInvitation) -> dict:
    created_at = _as_utc(invitation.created_at)
    expires_at = _as_utc(invitation.expires_at)
    status = invitation.status
    if status == "pending" and expires_at <= datetime.now(timezone.utc):
        status = "expired"
    return {
        "id": invitation.id,
        "phone_number": invitation.phone_number,
        "relationship_label": invitation.relationship_label,
        "status": status,
        "delivery_status": invitation.delivery_status,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


def _send_invitation(db: Session, invitation: FamilyInvitation, token: str) -> None:
    app_url = settings.PUBLIC_APP_URL.strip().rstrip("/")
    if not app_url.startswith(("https://", "http://")):
        invitation.delivery_status = "failed"
        invitation.token_hash = None
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "The invitation was saved, but the app link is misconfigured.",
                "invitation_saved": True,
                "invitation_id": invitation.id,
            },
        )

    accept_url = f"{app_url}/family/accept?token={quote(token)}"
    message = (
        "You have a CuraMind family invitation. "
        f"Accept it securely here: {accept_url} "
        "This link expires in 30 days and can only be used once."
    )
    try:
        send_twilio_sms(invitation.phone_number, message)
    except SmsConfigurationError as error:
        invitation.delivery_status = "not_configured"
        invitation.token_hash = None
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={
                "message": (
                    "The invitation was saved, but SMS delivery is not configured. "
                    "Add the Twilio production variables and retry."
                ),
                "invitation_saved": True,
                "invitation_id": invitation.id,
            },
        ) from error
    except SmsDeliveryError as error:
        invitation.delivery_status = "failed"
        invitation.token_hash = None
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={
                "message": (
                    "The invitation was saved, but Twilio could not send the SMS. "
                    "Check the number and Twilio settings, then retry."
                ),
                "invitation_saved": True,
                "invitation_id": invitation.id,
            },
        ) from error

    invitation.delivery_status = "sent"
    db.commit()
    db.refresh(invitation)


@router.get("")
def list_family(
    request: Request,
    db: Session = Depends(get_db),
):
    owner, _, _ = _signed_in_owner(request, db)
    members = db.scalars(
        select(Profile)
        .join(FamilyLink, FamilyLink.member_user_id == Profile.user_id)
        .where(FamilyLink.owner_user_id == owner.user_id)
        .order_by(Profile.name, Profile.id)
    ).all()
    return {"members": [_member_json(member) for member in members]}


@router.get("/active")
def active_family_profile(
    request: Request,
    db: Session = Depends(get_db),
):
    owner, _, session = _signed_in_owner(request, db)
    member = owner
    if session.active_profile_id is not None:
        member = db.get(Profile, session.active_profile_id)
        if member is None:
            session.active_profile_id = None
            db.commit()
            raise HTTPException(status_code=403, detail="Selected profile is unavailable.")
        link = db.scalar(
            select(FamilyLink.id).where(
                FamilyLink.owner_user_id == owner.user_id,
                FamilyLink.member_user_id == member.user_id,
            )
        )
        if link is None:
            session.active_profile_id = None
            db.commit()
            raise HTTPException(status_code=403, detail="Family profile access denied.")

    profile_data = _member_json(member)
    if member.id == owner.id:
        profile_data["oid"] = member.oid or f"owner-{member.id}"
        return {"type": "owner", "active_profile": profile_data}
    return {"type": "family", "active_profile": profile_data}


@router.post("", status_code=201)
def create_family_member(
    body: FamilyMemberCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    owner, _, _ = _signed_in_owner(request, db)
    fields = body.model_dump(exclude={"pin"})
    fields["name"] = fields["name"].strip()
    if not fields["name"]:
        raise HTTPException(status_code=422, detail="Name cannot be blank.")

    member_user = User()
    member_profile = Profile(oid=_new_oid(db), **fields)
    _set_pin(member_profile, body.pin)
    member_user.profile = member_profile
    db.add(member_user)
    try:
        db.flush()
        db.add(
            FamilyLink(
                owner_user_id=owner.user_id,
                member_user_id=member_user.id,
            )
        )
        db.commit()
        db.refresh(member_profile)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create the family member.")
    return _member_json(member_profile)


@router.get("/invitations")
def list_invitations(
    request: Request,
    db: Session = Depends(get_db),
):
    _, user, _ = _signed_in_owner(request, db)
    invitations = db.scalars(
        select(FamilyInvitation)
        .where(FamilyInvitation.owner_user_id == user.id)
        .order_by(FamilyInvitation.created_at.desc(), FamilyInvitation.id.desc())
    ).all()
    return [_invitation_json(invitation) for invitation in invitations]


@router.post("/invitations/accept")
def accept_invitation(
    body: InvitationAccept,
    request: Request,
    db: Session = Depends(get_db),
):
    _, user, _ = _signed_in_owner(request, db)
    invitation = db.scalar(
        select(FamilyInvitation)
        .where(FamilyInvitation.token_hash == token_digest(body.token))
        .with_for_update()
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation link is invalid or expired.")
    if invitation.status != "pending":
        raise HTTPException(status_code=409, detail="This invitation is no longer available.")
    if invitation.delivery_status != "sent":
        raise HTTPException(status_code=409, detail="This invitation has not been sent.")
    if invitation.owner_user_id == user.id:
        raise HTTPException(status_code=409, detail="You cannot accept your own invitation.")
    if _as_utc(invitation.expires_at) <= datetime.now(timezone.utc):
        invitation.status = "expired"
        invitation.token_hash = None
        db.commit()
        raise HTTPException(status_code=410, detail="This invitation has expired.")

    existing_link = db.scalar(
        select(FamilyLink.id).where(
            FamilyLink.owner_user_id == invitation.owner_user_id,
            FamilyLink.member_user_id == user.id,
        )
    )
    if existing_link is not None:
        raise HTTPException(status_code=409, detail="This account is already linked.")

    db.add(
        FamilyLink(
            owner_user_id=invitation.owner_user_id,
            member_user_id=user.id,
        )
    )
    invitation.status = "accepted"
    invitation.token_hash = None
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="This invitation was already accepted.") from error
    return {"ok": True, "message": "Family invitation accepted."}


@router.get("/{oid}")
def get_family_member(
    oid: str,
    request: Request,
    db: Session = Depends(get_db),
):
    owner, _, _ = _signed_in_owner(request, db)
    return _member_json(_owned_member(db, owner, oid))


@router.put("/{oid}")
def update_family_member(
    oid: str,
    body: FamilyMemberUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    owner, _, _ = _signed_in_owner(request, db)
    member = _owned_member(db, owner, oid)
    if "name" in body.model_fields_set and body.name is None:
        raise HTTPException(status_code=422, detail="Name cannot be blank.")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "name":
            value = value.strip()
            if not value:
                raise HTTPException(status_code=422, detail="Name cannot be blank.")
        setattr(member, field, value)
    db.commit()
    db.refresh(member)
    return _member_json(member)


@router.post("/{oid}/set-pin")
def set_family_pin(
    oid: str,
    body: PinBody,
    request: Request,
    db: Session = Depends(get_db),
):
    owner, _, _ = _signed_in_owner(request, db)
    member = _owned_member(db, owner, oid)
    if member.pin_hash is not None:
        raise HTTPException(status_code=409, detail="A PIN is already set.")
    _set_pin(member, body.pin)
    db.commit()
    return {"message": "PIN set successfully."}


@router.post("/{oid}/unlock")
def unlock_family_profile(
    oid: str,
    body: PinBody,
    request: Request,
    db: Session = Depends(get_db),
):
    owner, _, session = _signed_in_owner(request, db)
    member = _owned_member(db, owner, oid)
    if member.pin_hash is None:
        raise HTTPException(status_code=409, detail="Set a PIN before opening this profile.")

    now = _utcnow()
    if member.pin_locked_until is not None:
        if member.pin_locked_until > now:
            raise HTTPException(
                status_code=429,
                detail="Too many incorrect PIN attempts. Try again after the lock expires.",
            )
        member.pin_locked_until = None
        member.pin_failed_attempts = 0

    if not verify_password(body.pin, member.pin_hash):
        member.pin_failed_attempts += 1
        if member.pin_failed_attempts >= PIN_ATTEMPT_LIMIT:
            member.pin_failed_attempts = 0
            member.pin_locked_until = now + PIN_LOCK_DURATION
            db.commit()
            raise HTTPException(
                status_code=429,
                detail="Too many incorrect PIN attempts. Try again in one minute.",
            )
        db.commit()
        raise HTTPException(status_code=401, detail="Incorrect family profile PIN.")

    member.pin_failed_attempts = 0
    member.pin_locked_until = None
    session.active_profile_id = member.id
    db.commit()
    db.refresh(member)
    return {"message": "Profile unlocked.", "active_profile": _member_json(member)}


@router.post("/{oid}/reset-pin")
def reset_family_pin(
    oid: str,
    body: ResetPinBody,
    request: Request,
    db: Session = Depends(get_db),
):
    owner, user, _ = _signed_in_owner(request, db)
    member = _owned_member(db, owner, oid)
    if not verify_password(body.account_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect account password.")
    _set_pin(member, body.new_pin)
    db.commit()
    return {"message": "PIN reset successfully."}


@router.post("/switch-to-owner")
def switch_to_owner(
    request: Request,
    db: Session = Depends(get_db),
):
    owner, _, session = _signed_in_owner(request, db)
    session.active_profile_id = None
    db.commit()
    return {
        "message": "Switched to the main account profile.",
        "active_profile": {
            "oid": owner.oid or f"owner-{owner.id}",
            "name": owner.name,
        },
    }


@router.post("/invitations", status_code=201)
def create_invitation(
    body: InvitationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _, user, _ = _signed_in_owner(request, db)
    invitation = FamilyInvitation(
        owner_user_id=user.id,
        phone_number=body.phone_number,
        relationship_label=body.relationship_label,
        status="pending",
        delivery_status="sending",
        token_hash=None,
        expires_at=datetime.now(timezone.utc) + INVITATION_LIFETIME,
    )
    token = token_urlsafe(32)
    invitation.token_hash = token_digest(token)
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    _send_invitation(db, invitation, token)
    return {
        **_invitation_json(invitation),
        "message": "Invitation SMS sent. The secure link expires in 30 days.",
    }


@router.post("/invitations/{invitation_id}/send")
def resend_invitation(
    invitation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    _, user, _ = _signed_in_owner(request, db)
    invitation = db.scalar(
        select(FamilyInvitation)
        .where(
            FamilyInvitation.id == invitation_id,
            FamilyInvitation.owner_user_id == user.id,
        )
        .with_for_update()
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    if invitation.status != "pending":
        raise HTTPException(status_code=409, detail="This invitation is no longer pending.")
    if invitation.delivery_status == "sending":
        raise HTTPException(status_code=409, detail="This invitation is already being sent.")
    if invitation.delivery_status == "sent":
        raise HTTPException(status_code=409, detail="This invitation was already sent.")
    if _as_utc(invitation.expires_at) <= datetime.now(timezone.utc):
        invitation.status = "expired"
        invitation.token_hash = None
        db.commit()
        raise HTTPException(status_code=410, detail="This invitation has expired.")

    token = token_urlsafe(32)
    invitation.token_hash = token_digest(token)
    invitation.delivery_status = "sending"
    db.commit()
    db.refresh(invitation)
    _send_invitation(db, invitation, token)
    return {
        **_invitation_json(invitation),
        "message": "Invitation SMS sent. The secure link expires in 30 days.",
    }


@router.delete("/invitations/{invitation_id}")
def cancel_invitation(
    invitation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    _, user, _ = _signed_in_owner(request, db)
    invitation = db.scalar(
        select(FamilyInvitation).where(
            FamilyInvitation.id == invitation_id,
            FamilyInvitation.owner_user_id == user.id,
        )
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    if invitation.status == "pending":
        invitation.status = "cancelled"
        invitation.token_hash = None
        db.commit()
    return {"ok": True, "id": invitation.id, "status": invitation.status}


@router.delete("/{oid}", status_code=204)
def unlink_family_member(
    oid: str,
    request: Request,
    db: Session = Depends(get_db),
):
    owner, _, session = _signed_in_owner(request, db)
    member = _owned_member(db, owner, oid)
    link = db.scalar(
        select(FamilyLink).where(
            FamilyLink.owner_user_id == owner.user_id,
            FamilyLink.member_user_id == member.user_id,
        )
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Family member not linked to this account.")
    if session.active_profile_id == member.id:
        session.active_profile_id = None
    db.delete(link)
    db.commit()

from datetime import date
from secrets import token_hex

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import current_profile
from ..db import get_db
from ..models import FamilyLink, Profile, User

router = APIRouter(prefix="/family", tags=["family"])


class FamilyMemberCreate(BaseModel):
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


class FamilyMemberUpdate(BaseModel):
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


def _new_oid(db: Session) -> str:
    for _ in range(10):
        oid = "CM-" + token_hex(16).upper()
        exists = db.scalar(select(Profile.id).where(Profile.oid == oid))
        if exists is None:
            return oid

    raise HTTPException(
        status_code=503,
        detail="Could not generate a unique profile ID",
    )


def _member_json(member: Profile) -> dict:
    calculated_age = None

    if member.dob:
        today = date.today()
        calculated_age = today.year - member.dob.year - (
            (today.month, today.day) < (member.dob.month, member.dob.day)
        )

    return {
        "oid": member.oid,
        "name": member.name,
        "dob": member.dob,
        "sex": member.sex,
        "age": calculated_age if member.dob else member.age,
        "blood_group": member.blood_group,
        "allergies_text": member.allergies_text,
        "conditions_text": member.conditions_text,
        "medicines_text": member.medicines_text,
        "previous_records": member.previous_records,
        "emergency_contact_name": member.emergency_contact_name,
        "emergency_contact_phone": member.emergency_contact_phone,
    }


def _get_linked_member(
    oid: str,
    owner: Profile,
    db: Session,
) -> Profile:
    member = db.scalar(select(Profile).where(Profile.oid == oid))

    if member is None:
        raise HTTPException(status_code=404, detail="Family member not found")

    link = db.scalar(
        select(FamilyLink).where(
            FamilyLink.owner_user_id == owner.user_id,
            FamilyLink.member_user_id == member.user_id,
        )
    )

    if link is None:
        raise HTTPException(
            status_code=404,
            detail="Family member not linked to this profile",
        )

    return member


@router.get("")
def list_family(
    owner: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    links = db.scalars(
        select(FamilyLink).where(
            FamilyLink.owner_user_id == owner.user_id
        )
    ).all()

    members = []

    for link in links:
        member = db.scalar(
            select(Profile).where(Profile.user_id == link.member_user_id)
        )

        if member is not None:
            members.append(_member_json(member))

    return {"members": members}


@router.post("", status_code=201)
def create_family_member(
    body: FamilyMemberCreate,
    owner: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    values = body.model_dump()
    name = (values.get("name") or "").strip()

    if not name:
        raise HTTPException(status_code=422, detail="Name cannot be blank")

    values["name"] = name

    for field in (
        "sex",
        "blood_group",
        "allergies_text",
        "conditions_text",
        "medicines_text",
        "previous_records",
        "emergency_contact_name",
        "emergency_contact_phone",
    ):
        if isinstance(values.get(field), str):
            values[field] = values[field].strip() or None

    member_user = User()
    member_profile = Profile(
        oid=_new_oid(db),
        **values,
    )

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
        raise HTTPException(
            status_code=409,
            detail="Could not create the family member",
        )

    return _member_json(member_profile)


@router.get("/{oid}")
def get_family_member(
    oid: str,
    owner: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    member = _get_linked_member(oid, owner, db)
    return _member_json(member)


@router.put("/{oid}")
def update_family_member(
    oid: str,
    body: FamilyMemberUpdate,
    owner: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    member = _get_linked_member(oid, owner, db)
    changes = body.model_dump(exclude_unset=True)

    for field, value in changes.items():
        if field == "name":
            if value is None or not value.strip():
                raise HTTPException(
                    status_code=422,
                    detail="Name cannot be blank",
                )
            value = value.strip()

        elif field in {
            "sex",
            "blood_group",
            "allergies_text",
            "conditions_text",
            "medicines_text",
            "previous_records",
            "emergency_contact_name",
            "emergency_contact_phone",
        }:
            if isinstance(value, str):
                value = value.strip() or None

        setattr(member, field, value)

    db.commit()
    db.refresh(member)

    return _member_json(member)


@router.delete("/{oid}", status_code=204)
def unlink_family_member(
    oid: str,
    owner: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    member = _get_linked_member(oid, owner, db)

    # Unlink only; do not delete the member or their medical records.
    link = db.scalar(
        select(FamilyLink).where(
            FamilyLink.owner_user_id == owner.user_id,
            FamilyLink.member_user_id == member.user_id,
        )
    )

    db.delete(link)
    db.commit()
    return None

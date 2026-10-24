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


def _new_oid(db: Session) -> str:
    for _ in range(10):
        oid = "CM-" + token_hex(16).upper()
        exists = db.scalar(
            select(Profile.id).where(Profile.oid == oid)
        )
        if exists is None:
            return oid

    raise HTTPException(
        status_code=503,
        detail="Could not generate a unique profile ID",
    )


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
            select(Profile).where(
                Profile.user_id == link.member_user_id
            )
        )

        if member is not None:
            members.append({
                "oid": member.oid,
                "name": member.name,
                "dob": member.dob,
                "sex": member.sex,
            })

    return {"members": members}


@router.post("", status_code=201)
def create_family_member(
    body: FamilyMemberCreate,
    owner: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    name = body.name.strip()

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Name cannot be blank",
        )

    member_user = User()
    member_profile = Profile(
        oid=_new_oid(db),
        name=name,
        dob=body.dob,
        sex=body.sex,
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

    return {
        "oid": member_profile.oid,
        "name": member_profile.name,
        "dob": member_profile.dob,
        "sex": member_profile.sex,
    }


@router.delete("/{oid}", status_code=204)
def unlink_family_member(
    oid: str,
    owner: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    member = db.scalar(
        select(Profile).where(Profile.oid == oid)
    )

    if member is None:
        raise HTTPException(
            status_code=404,
            detail="Family member not found",
        )

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

    # Unlink only; do not delete the member or their medical records.
    db.delete(link)
    db.commit()
    return None

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Document, FamilyLink, Profile


def profile_oid_for(profile: Profile) -> str:
    return profile.oid or f"owner-{profile.id}"


def is_requested_profile(profile: Profile, requested_oid: str | None) -> bool:
    return requested_oid is None or requested_oid == profile_oid_for(profile)


def confirmed_document_ids(profile_id: int):
    return select(Document.id).where(
        Document.profile_id == profile_id,
        Document.review_status == "confirmed",
    )


def profile_for_owner(
    owner: Profile,
    db: Session,
    profile_oid: str | None = None,
) -> Profile:
    if profile_oid is None or profile_oid == profile_oid_for(owner):
        return owner
    member = db.scalar(select(Profile).where(Profile.oid == profile_oid))
    if member is None:
        raise HTTPException(status_code=404, detail="Family profile not found")
    linked = db.scalar(
        select(FamilyLink.id).where(
            FamilyLink.owner_user_id == owner.user_id,
            FamilyLink.member_user_id == member.user_id,
        )
    )
    if linked is None:
        raise HTTPException(status_code=404, detail="Family profile not found")
    return member


def owns_or_links_profile(owner: Profile, target: Profile, db: Session) -> bool:
    if owner.id == target.id:
        return True
    return db.scalar(
        select(FamilyLink.id).where(
            FamilyLink.owner_user_id == owner.user_id,
            FamilyLink.member_user_id == target.user_id,
        )
    ) is not None

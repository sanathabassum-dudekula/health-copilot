from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Document, FamilyLink, Profile


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
    if profile_oid is None or profile_oid == owner.oid:
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

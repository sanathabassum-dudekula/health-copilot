
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

CASCADE = "all, delete-orphan"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    preferred_language: Mapped[str] = mapped_column(String, default="en")

    profile: Mapped["Profile"] = relationship(
        back_populates="user", cascade=CASCADE, uselist=False
    )
    visit: Mapped["Visit"] = relationship(
        back_populates="user", cascade=CASCADE, uselist=False
    )


class Visit(Base):
    __tablename__ = "visits"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="visit")


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        UniqueConstraint("oid", name="uq_profiles_oid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True
    )
    oid: Mapped[str | None] = mapped_column(String(40), index=True)

    name: Mapped[str] = mapped_column(String)
    dob: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String)

    abha_number: Mapped[str | None] = mapped_column(String)
    abha_address: Mapped[str | None] = mapped_column(String)
    abha_linked_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="profile")
    documents: Mapped[list["Document"]] = relationship(
        cascade=CASCADE
    )


class FamilyLink(Base):
    __tablename__ = "family_links"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "member_user_id",
            name="uq_family_owner_member",
        ),
        CheckConstraint(
            "owner_user_id <> member_user_id",
            name="ck_family_no_self_link",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    member_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))

    file_path: Mapped[str | None] = mapped_column(String)
    mime: Mapped[str | None] = mapped_column(String)
    doc_type: Mapped[str | None] = mapped_column(String)
    doc_date: Mapped[date | None] = mapped_column(Date)
    facility: Mapped[str | None] = mapped_column(String)
    practitioner: Mapped[str | None] = mapped_column(String)
    admission_date: Mapped[date | None] = mapped_column(Date)
    discharge_date: Mapped[date | None] = mapped_column(Date)

    status: Mapped[str] = mapped_column(String, default="processing")
    extraction: Mapped[dict | None] = mapped_column(JSON)
    summary: Mapped[dict | None] = mapped_column(JSON)
    summary_i18n: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String, default="upload")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    observations: Mapped[list["Observation"]] = relationship(
        cascade=CASCADE
    )
    medications: Mapped[list["Medication"]] = relationship(
        cascade=CASCADE
    )
    conditions: Mapped[list["Condition"]] = relationship(
        cascade=CASCADE
    )
    allergies: Mapped[list["Allergy"]] = relationship(
        cascade=CASCADE
    )


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    loinc_code: Mapped[str | None] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String)
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String)
    unit: Mapped[str | None] = mapped_column(String)
    ref_low: Mapped[float | None] = mapped_column(Float)
    ref_high: Mapped[float | None] = mapped_column(Float)
    interpretation: Mapped[str | None] = mapped_column(String)
    effective_at: Mapped[date | None] = mapped_column(Date)
    confidence: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String)


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    brand_name: Mapped[str] = mapped_column(String)
    salt: Mapped[str | None] = mapped_column(String)
    strength: Mapped[str | None] = mapped_column(String)
    form: Mapped[str | None] = mapped_column(String)
    dose_pattern: Mapped[str | None] = mapped_column(String)
    per_day: Mapped[int | None] = mapped_column(Integer)
    timing: Mapped[str | None] = mapped_column(String)
    duration_days: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    prescriber: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column(Float)


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    name: Mapped[str] = mapped_column(String)
    recorded_at: Mapped[date | None] = mapped_column(Date)


class Allergy(Base):
    __tablename__ = "allergies"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    substance: Mapped[str] = mapped_column(String)
    reaction: Mapped[str | None] = mapped_column(String)

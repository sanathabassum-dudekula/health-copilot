
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
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)

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

    # Basic personal information
    name: Mapped[str] = mapped_column(String)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Additional information entered in the profile form
    allergies_text: Mapped[str | None] = mapped_column(String, nullable=True)
    conditions_text: Mapped[str | None] = mapped_column(String, nullable=True)
    medicines_text: Mapped[str | None] = mapped_column(String, nullable=True)
    previous_records: Mapped[str | None] = mapped_column(String, nullable=True)

    # Emergency contact
    emergency_contact_name: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    emergency_contact_phone: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )

    # ABHA information
    abha_number: Mapped[str | None] = mapped_column(String, nullable=True)
    abha_address: Mapped[str | None] = mapped_column(String, nullable=True)
    abha_linked_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="profile")
    documents: Mapped[list["Document"]] = relationship(
        cascade=CASCADE
    )


class FamilyLink(Base):
    __tablename__ = "family_links"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "member_user_id",
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

    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    mime: Mapped[str | None] = mapped_column(String, nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String, nullable=True)
    doc_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    facility: Mapped[str | None] = mapped_column(String, nullable=True)
    practitioner: Mapped[str | None] = mapped_column(String, nullable=True)
    admission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    discharge_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String, default="processing")
    extraction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary_i18n: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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

    loinc_code: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str] = mapped_column(String)
    value_num: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    ref_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    interpretation: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    brand_name: Mapped[str] = mapped_column(String)
    salt: Mapped[str | None] = mapped_column(String, nullable=True)
    strength: Mapped[str | None] = mapped_column(String, nullable=True)
    form: Mapped[str | None] = mapped_column(String, nullable=True)
    dose_pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timing: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    prescriber: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    name: Mapped[str] = mapped_column(String)
    recorded_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class Allergy(Base):
    __tablename__ = "allergies"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    substance: Mapped[str] = mapped_column(String)
    reaction: Mapped[str | None] = mapped_column(String, nullable=True)
class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    active_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


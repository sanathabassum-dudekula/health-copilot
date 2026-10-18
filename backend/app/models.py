
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
    Text,
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
    preferred_voice_language: Mapped[str] = mapped_column(
        String, default="en", server_default="en"
    )
    voice_reminders_enabled: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )
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

    name: Mapped[str] = mapped_column(String)
    dob: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String)
    age: Mapped[int | None] = mapped_column(Integer)
    blood_group: Mapped[str | None] = mapped_column(String)
    allergies_text: Mapped[str | None] = mapped_column(String)
    conditions_text: Mapped[str | None] = mapped_column(String)
    medicines_text: Mapped[str | None] = mapped_column(String)
    previous_records: Mapped[str | None] = mapped_column(String)
    emergency_contact_name: Mapped[str | None] = mapped_column(String)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String)

    abha_number: Mapped[str | None] = mapped_column(String)
    abha_address: Mapped[str | None] = mapped_column(String)
    abha_linked_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="profile")
    documents: Mapped[list["Document"]] = relationship(
        cascade=CASCADE
    )
    assistant_messages: Mapped[list["AssistantMessage"]] = relationship(
        back_populates="profile", cascade=CASCADE
    )
    assistant_conversations: Mapped[list["AssistantConversation"]] = relationship(
        back_populates="profile", cascade=CASCADE
    )
    health_reminders: Mapped[list["HealthReminder"]] = relationship(
        back_populates="profile", cascade=CASCADE
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
    review_status: Mapped[str] = mapped_column(
        String, default="pending", server_default="pending", nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_profile_id: Mapped[int | None] = mapped_column(Integer)
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


class HealthReminder(Base):
    __tablename__ = "health_reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(160))
    details: Mapped[str | None] = mapped_column(Text)
    spoken_title: Mapped[str | None] = mapped_column(String(160))
    spoken_details: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    category: Mapped[str] = mapped_column(String(24), default="other")
    recurrence: Mapped[str] = mapped_column(String(16), default="none")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    profile: Mapped["Profile"] = relationship(back_populates="health_reminders")


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="New health chat")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped["Profile"] = relationship(back_populates="assistant_conversations")
    messages: Mapped[list["AssistantMessage"]] = relationship(
        back_populates="conversation", cascade=CASCADE
    )


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("assistant_conversations.id"), index=True, nullable=True
    )
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    profile: Mapped["Profile"] = relationship(back_populates="assistant_messages")
    conversation: Mapped["AssistantConversation | None"] = relationship(
        back_populates="messages"
    )



class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

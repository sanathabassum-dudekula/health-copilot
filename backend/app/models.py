
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

    # Basic personal information
    name: Mapped[str] = mapped_column(String)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pin_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    pin_failed_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    pin_locked_until: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Additional information entered in the profile form
    allergies_text: Mapped[str | None] = mapped_column(String, nullable=True)
    conditions_text: Mapped[str | None] = mapped_column(String, nullable=True)
    medicines_text: Mapped[str | None] = mapped_column(String, nullable=True)
    previous_records: Mapped[str | None] = mapped_column(String, nullable=True)
    womens_health_profile: Mapped[dict] = mapped_column(
        JSON, default=dict, server_default="{}", nullable=False
    )

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
    assistant_messages: Mapped[list["AssistantMessage"]] = relationship(
        back_populates="profile", cascade=CASCADE
    )
    assistant_conversations: Mapped[list["AssistantConversation"]] = relationship(
        back_populates="profile", cascade=CASCADE
    )
    health_reminders: Mapped[list["HealthReminder"]] = relationship(
        back_populates="profile", cascade=CASCADE
    )
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(
        back_populates="profile", cascade=CASCADE
    )
    vital_signs: Mapped[list["VitalSign"]] = relationship(
        back_populates="profile", cascade=CASCADE
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
    review_status: Mapped[str] = mapped_column(
        String, default="pending", server_default="pending", nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_profile_id: Mapped[int | None] = mapped_column(Integer)
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


class VitalSign(Base):
    __tablename__ = "vital_signs"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = mapped_column(String(32))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    device_name: Mapped[str | None] = mapped_column(String(120))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )

    profile: Mapped["Profile"] = relationship(back_populates="vital_signs")


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
    push_deliveries: Mapped[list["PushDelivery"]] = relationship(
        back_populates="reminder", cascade=CASCADE
    )


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "endpoint", name="uq_push_subscription_profile_endpoint"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(Text)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    profile: Mapped["Profile"] = relationship(back_populates="push_subscriptions")
    deliveries: Mapped[list["PushDelivery"]] = relationship(
        back_populates="subscription", cascade=CASCADE
    )


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "reminder_id",
            "subscription_id",
            "due_at",
            name="uq_push_delivery_occurrence",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(
        ForeignKey("health_reminders.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("push_subscriptions.id", ondelete="CASCADE"), index=True
    )
    due_at: Mapped[datetime] = mapped_column(DateTime)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reminder: Mapped["HealthReminder"] = relationship(back_populates="push_deliveries")
    subscription: Mapped["PushSubscription"] = relationship(back_populates="deliveries")


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

    profile: Mapped["Profile"] = relationship(
        back_populates="assistant_conversations"
    )
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


class FamilyInvitation(Base):
    __tablename__ = "family_invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    phone_number: Mapped[str] = mapped_column(String(32))
    relationship_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", index=True
    )
    delivery_status: Mapped[str] = mapped_column(
        String(16), default="not_sent", server_default="not_sent", nullable=False
    )
    token_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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

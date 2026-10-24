from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db


def init_db():
    from . import models

    with engine.begin() as conn:
        inspector = inspect(conn)

        if inspector.has_table("users"):
            columns = {column["name"] for column in inspector.get_columns("users")}

            if "email" not in columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN email VARCHAR(320)")
            if "password_hash" not in columns:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)"
                )
            if "preferred_voice_language" not in columns:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN preferred_voice_language "
                    "VARCHAR NOT NULL DEFAULT 'en'"
                )
            if "voice_reminders_enabled" not in columns:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN voice_reminders_enabled "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )

            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
            )

        if inspector.has_table("profiles"):
            columns = {column["name"] for column in inspector.get_columns("profiles")}
            new_columns = {
                "age": "INTEGER",
                "blood_group": "VARCHAR",
                "allergies_text": "VARCHAR",
                "conditions_text": "VARCHAR",
                "medicines_text": "VARCHAR",
                "previous_records": "VARCHAR",
                "emergency_contact_name": "VARCHAR(120)",
                "emergency_contact_phone": "VARCHAR(40)",
            }
            for name, sql_type in new_columns.items():
                if name not in columns:
                    conn.exec_driver_sql(
                        f"ALTER TABLE profiles ADD COLUMN {name} {sql_type}"
                    )

        if inspector.has_table("documents"):
            columns = {
                column["name"] for column in inspector.get_columns("documents")
            }
            new_columns = {
                "review_status": "VARCHAR NOT NULL DEFAULT 'pending'",
                "reviewed_at": "TIMESTAMP",
                "reviewed_by_profile_id": "INTEGER",
            }
            for name, sql_type in new_columns.items():
                if name not in columns:
                    conn.exec_driver_sql(
                        f"ALTER TABLE documents ADD COLUMN {name} {sql_type}"
                    )

        if inspector.has_table("health_reminders"):
            columns = {
                column["name"]
                for column in inspector.get_columns("health_reminders")
            }
            if "spoken_title" not in columns:
                conn.exec_driver_sql(
                    "ALTER TABLE health_reminders ADD COLUMN spoken_title VARCHAR(160)"
                )
            if "spoken_details" not in columns:
                conn.exec_driver_sql(
                    "ALTER TABLE health_reminders ADD COLUMN spoken_details TEXT"
                )

        if inspector.has_table("assistant_messages"):
            columns = {
                column["name"]
                for column in inspector.get_columns("assistant_messages")
            }
            if "conversation_id" not in columns:
                conn.exec_driver_sql(
                    "ALTER TABLE assistant_messages ADD COLUMN conversation_id INTEGER"
                )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_assistant_messages_conversation_id "
                "ON assistant_messages (conversation_id)"
            )

        if inspector.has_table("auth_sessions"):
            columns = {
                column["name"] for column in inspector.get_columns("auth_sessions")
            }
            if "active_profile_id" not in columns:
                conn.exec_driver_sql(
                    "ALTER TABLE auth_sessions ADD COLUMN active_profile_id INTEGER"
                )

    Base.metadata.create_all(engine)

    with SessionLocal.begin() as session:
        legacy_profile_ids = session.scalars(
            select(models.AssistantMessage.profile_id)
            .where(models.AssistantMessage.conversation_id.is_(None))
            .distinct()
        ).all()
        for profile_id in legacy_profile_ids:
            messages = session.scalars(
                select(models.AssistantMessage)
                .where(
                    models.AssistantMessage.profile_id == profile_id,
                    models.AssistantMessage.conversation_id.is_(None),
                )
                .order_by(models.AssistantMessage.id)
            ).all()
            first_user_message = next(
                (message.content for message in messages if message.role == "user"),
                "Previous health chat",
            )
            conversation = models.AssistantConversation(
                profile_id=profile_id,
                title=" ".join(first_user_message.split())[:120],
            )
            session.add(conversation)
            session.flush()
            for message in messages:
                message.conversation_id = conversation.id

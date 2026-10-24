from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app import db, models


def test_init_db_adds_profile_fields_to_existing_schema(monkeypatch, tmp_path):
    legacy_engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with legacy_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                preferred_language VARCHAR NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                oid VARCHAR(40),
                name VARCHAR NOT NULL,
                dob DATE,
                sex VARCHAR,
                abha_number VARCHAR,
                abha_address VARCHAR,
                abha_linked_at DATETIME
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                profile_id INTEGER NOT NULL,
                file_path VARCHAR,
                mime VARCHAR,
                doc_type VARCHAR,
                doc_date DATE,
                facility VARCHAR,
                practitioner VARCHAR,
                admission_date DATE,
                discharge_date DATE,
                status VARCHAR NOT NULL,
                extraction JSON,
                summary JSON,
                summary_i18n JSON,
                source VARCHAR NOT NULL,
                created_at DATETIME
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO documents (id, profile_id, status, source)
            VALUES (1, 1, 'done', 'upload')
            """
        )

    monkeypatch.setattr(db, "engine", legacy_engine)
    monkeypatch.setattr(
        db, "SessionLocal", sessionmaker(legacy_engine, expire_on_commit=False)
    )

    db.init_db()

    columns = {
        column["name"]
        for column in inspect(legacy_engine).get_columns("profiles")
    }
    assert {
        "age",
        "blood_group",
        "allergies_text",
        "conditions_text",
        "medicines_text",
        "previous_records",
        "womens_health_profile",
        "emergency_contact_name",
        "emergency_contact_phone",
        "pin_hash",
        "pin_failed_attempts",
        "pin_locked_until",
    } <= columns
    user_columns = {
        column["name"]
        for column in inspect(legacy_engine).get_columns("users")
    }
    assert {"preferred_voice_language", "voice_reminders_enabled"} <= user_columns

    document_columns = {
        column["name"]
        for column in inspect(legacy_engine).get_columns("documents")
    }
    assert {
        "review_status",
        "reviewed_at",
        "reviewed_by_profile_id",
    } <= document_columns
    with legacy_engine.connect() as conn:
        migrated_review = conn.exec_driver_sql(
            "SELECT review_status, reviewed_at, reviewed_by_profile_id "
            "FROM documents WHERE id = 1"
        ).one()
    assert tuple(migrated_review) == ("pending", None, None)

    with Session(legacy_engine) as session:
        user = models.User()
        user.profile = models.Profile(name="Guest")
        user.visit = models.Visit(token="00000000-0000-4000-8000-000000000001")
        session.add(user)
        session.commit()

        assert session.get(models.Profile, user.profile.id).name == "Guest"
        assert user.preferred_voice_language == "en"
        assert user.voice_reminders_enabled is False
        assert session.get(
            models.Visit, "00000000-0000-4000-8000-000000000001"
        ).user_id == user.id

    db.init_db()
    assert {
        column["name"]
        for column in inspect(legacy_engine).get_columns("profiles")
    } >= columns
    assert "review_status" in {
        column["name"]
        for column in inspect(legacy_engine).get_columns("documents")
    }
    assert {"spoken_title", "spoken_details"} <= {
        column["name"]
        for column in inspect(legacy_engine).get_columns("health_reminders")
    }
    assert {
        "owner_user_id",
        "phone_number",
        "relationship_label",
        "status",
        "created_at",
        "expires_at",
    } <= {
        column["name"]
        for column in inspect(legacy_engine).get_columns("family_invitations")
    }
    assert inspect(legacy_engine).has_table("push_subscriptions")
    assert inspect(legacy_engine).has_table("push_deliveries")
    legacy_engine.dispose()


def test_init_db_moves_existing_assistant_messages_into_a_conversation(
    monkeypatch, tmp_path
):
    legacy_engine = create_engine(f"sqlite:///{tmp_path / 'legacy-chat.db'}")
    with legacy_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                preferred_language VARCHAR NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE,
                oid VARCHAR(40),
                name VARCHAR NOT NULL,
                dob DATE,
                sex VARCHAR,
                abha_number VARCHAR,
                abha_address VARCHAR,
                abha_linked_at DATETIME
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE assistant_messages (
                id INTEGER PRIMARY KEY,
                profile_id INTEGER NOT NULL,
                role VARCHAR(10) NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            "INSERT INTO users (id, preferred_language) VALUES (1, 'en')"
        )
        conn.exec_driver_sql(
            "INSERT INTO profiles (id, user_id, name) VALUES (1, 1, 'Guest')"
        )
        conn.exec_driver_sql(
            """
            INSERT INTO assistant_messages (id, profile_id, role, content)
            VALUES (1, 1, 'user', 'My allergy started after lunch')
            """
        )

    monkeypatch.setattr(db, "engine", legacy_engine)
    monkeypatch.setattr(
        db, "SessionLocal", sessionmaker(legacy_engine, expire_on_commit=False)
    )
    db.init_db()

    with Session(legacy_engine) as session:
        message = session.get(models.AssistantMessage, 1)
        conversation = session.get(
            models.AssistantConversation, message.conversation_id
        )
        assert conversation.title == "My allergy started after lunch"
        assert conversation.profile_id == message.profile_id
    legacy_engine.dispose()

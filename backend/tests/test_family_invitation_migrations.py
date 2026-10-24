from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app import db


def test_init_db_adds_secure_invitation_fields_to_existing_schema(monkeypatch, tmp_path):
    legacy_engine = create_engine(f"sqlite:///{tmp_path / 'legacy-invitations.db'}")
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE family_invitations (
                id INTEGER PRIMARY KEY,
                owner_user_id INTEGER NOT NULL,
                phone_number VARCHAR(32) NOT NULL,
                relationship_label VARCHAR(80),
                status VARCHAR(16) NOT NULL,
                created_at DATETIME,
                expires_at DATETIME NOT NULL
            )
            """
        )

    monkeypatch.setattr(db, "engine", legacy_engine)
    monkeypatch.setattr(
        db, "SessionLocal", sessionmaker(legacy_engine, expire_on_commit=False)
    )

    db.init_db()

    inspector = inspect(legacy_engine)
    columns = {
        column["name"] for column in inspector.get_columns("family_invitations")
    }
    assert {"delivery_status", "token_hash"} <= columns
    indexes = {index["name"]: index for index in inspector.get_indexes("family_invitations")}
    assert bool(indexes["ix_family_invitations_token_hash"]["unique"])

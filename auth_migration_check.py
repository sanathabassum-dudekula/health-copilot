from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from backend.app.config import settings
from backend.app.models import AuthSession

engine = create_engine(settings.DATABASE_URL)

with engine.begin() as conn:
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if "users" not in tables:
        raise RuntimeError("The users table is missing. No migration was performed.")

    columns = {c["name"] for c in inspect(conn).get_columns("users")}

    if "email" not in columns:
        conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(320)"))
        print("Added missing users.email column.")
    else:
        print("users.email already exists.")

    if "password_hash" not in columns:
        conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)"))
        print("Added missing users.password_hash column.")
    else:
        print("users.password_hash already exists.")

    duplicate_emails = conn.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT lower(email)
            FROM users
            WHERE email IS NOT NULL AND trim(email) <> ''
            GROUP BY lower(email)
            HAVING COUNT(*) > 1
        )
    """)).scalar_one()

    if duplicate_emails == 0:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
        ))
        print("Email uniqueness index verified.")
    else:
        print(
            f"WARNING: Found {duplicate_emails} duplicate email groups. "
            "Unique index was NOT created; existing data was preserved."
        )

# Create only the authentication-session table if it is missing.
AuthSession.__table__.create(engine, checkfirst=True)

inspector = inspect(engine)
tables = inspector.get_table_names()
user_columns = {c["name"] for c in inspector.get_columns("users")}

print("\n--- DATABASE VERIFICATION ---")
print("Database:", settings.DATABASE_URL)
print("Email column:", "email" in user_columns)
print("Password hash column:", "password_hash" in user_columns)
print("Auth sessions table:", "auth_sessions" in tables)

with engine.connect() as conn:
    for table in ("users", "profiles", "visits", "documents", "family_links", "auth_sessions"):
        if table in tables:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
            print(f"{table}: {count} rows")

if not {"email", "password_hash"}.issubset(user_columns):
    raise RuntimeError("Authentication columns could not be verified.")

if "auth_sessions" not in tables:
    raise RuntimeError("Authentication session table could not be verified.")

print("\nMigration and verification completed.")

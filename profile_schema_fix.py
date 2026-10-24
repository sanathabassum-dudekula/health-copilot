from sqlalchemy import create_engine, inspect, text
from backend.app.config import settings

engine = create_engine(settings.DATABASE_URL)

# Add only columns already defined in the Profile model.
from backend.app.models import Profile

with engine.begin() as conn:
    inspector = inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("profiles")}

    for column in Profile.__table__.columns:
        if column.name in existing or column.primary_key:
            continue

        # Add missing columns using their SQLAlchemy type.
        column_type = column.type.compile(dialect=engine.dialect)
        nullable = "" if column.nullable else " NOT NULL"

        # A missing non-null column needs a safe default if rows already exist.
        if not column.nullable and column.default is None and column.server_default is None:
            raise RuntimeError(
                f"Column {column.name} is required and has no default. "
                "Stopped without adding it; review this column first."
            )

        sql = f'ALTER TABLE profiles ADD COLUMN "{column.name}" {column_type}'
        if column.server_default is not None:
            sql += f" DEFAULT {column.server_default.arg}"
        elif column.default is not None and not column.nullable:
            value = column.default.arg
            if not isinstance(value, (str, int, float)):
                raise RuntimeError(f"Unsupported default for {column.name}")
            if isinstance(value, str):
                value = "'" + value.replace("'", "''") + "'"
            sql += f" DEFAULT {value}"

        conn.execute(text(sql))
        print("Added profiles column:", column.name)

    print("\nExisting profile rows:", conn.execute(
        text("SELECT COUNT(*) FROM profiles")
    ).scalar_one())

print("Profile schema migration finished.")

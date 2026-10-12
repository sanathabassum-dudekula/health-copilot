from sqlalchemy import create_engine, inspect
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

    # Add new account columns before SQLAlchemy creates indexes for them.
    with engine.begin() as conn:
        inspector = inspect(conn)

        if inspector.has_table("users"):
            columns = {column["name"] for column in inspector.get_columns("users")}

            if "email" not in columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN email VARCHAR(320)")

            if "password_hash" not in columns:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)")

            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"
            )

    Base.metadata.create_all(engine)

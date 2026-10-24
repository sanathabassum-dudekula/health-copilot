from app.config import Settings
from app.db import _database_url


def test_settings_accepts_vercel_neon_unpooled_database_url():
    settings = Settings(
        _env_file=None,
        DATABASE_URL_UNPOOLED="postgresql://user:password@db.example.com/health",
    )

    assert settings.DATABASE_URL == (
        "postgresql://user:password@db.example.com/health"
    )


def test_postgres_urls_use_installed_psycopg_v3_driver():
    url = _database_url("postgresql://user:password@db.example.com/health")

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "db.example.com"


def test_sqlite_url_is_unchanged():
    url = _database_url("sqlite:////tmp/health.db")

    assert url.drivername == "sqlite"
    assert url.database == "/tmp/health.db"

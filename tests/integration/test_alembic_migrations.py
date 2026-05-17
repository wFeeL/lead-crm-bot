from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.db.models import Base
from sqlalchemy import create_engine, inspect


def make_alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_upgrade_creates_all_sqlalchemy_tables(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "alembic_schema.db"
    async_url = f"sqlite+aiosqlite:///{database_path}"
    sync_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", async_url)
    get_settings.cache_clear()

    command.upgrade(make_alembic_config(async_url), "head")

    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        actual_tables = set(inspector.get_table_names())
        expected_tables = set(Base.metadata.tables)

        assert expected_tables <= actual_tables
        assert "alembic_version" in actual_tables

        for table_name, table in Base.metadata.tables.items():
            actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
            expected_columns = set(table.columns.keys())
            assert expected_columns <= actual_columns
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_alembic_downgrade_removes_application_tables(tmp_path, monkeypatch) -> None:
    database_path = Path(tmp_path) / "alembic_downgrade.db"
    async_url = f"sqlite+aiosqlite:///{database_path}"
    sync_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", async_url)
    get_settings.cache_clear()

    config = make_alembic_config(async_url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(sync_url)
    try:
        inspector = inspect(engine)
        remaining_tables = set(inspector.get_table_names())
        assert set(Base.metadata.tables).isdisjoint(remaining_tables)
    finally:
        engine.dispose()
        get_settings.cache_clear()

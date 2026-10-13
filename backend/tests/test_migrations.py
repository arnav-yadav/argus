from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND = Path(__file__).resolve().parents[1]


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_migrations_upgrade_and_downgrade_cleanly(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrate.db'}"
    config = alembic_config(url)

    engine = create_engine(url)
    try:
        command.upgrade(config, "head")
        inspector = inspect(engine)
        assert {"services", "heartbeats", "alembic_version"} <= set(inspector.get_table_names())
        index_names = {i["name"] for i in inspector.get_indexes("heartbeats")}
        assert "ix_heartbeats_service_received" in index_names

        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()

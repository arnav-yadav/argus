import time
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app import models  # noqa: F401  registers the tables on Base.metadata
from app.config import settings
from app.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Any constant works; it only has to be the same for every replica running migrations.
MIGRATION_LOCK_KEY = 0x41524755  # "ARGU"


def database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def run_migrations_offline() -> None:
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def connect_with_retry(engine, attempts: int = 30, delay_s: float = 2.0):
    """The database may still be starting when a migration container runs."""
    for attempt in range(1, attempts + 1):
        try:
            return engine.connect()
        except OperationalError:
            if attempt == attempts:
                raise
            print(f"database not ready, retrying ({attempt}/{attempts})", flush=True)
            time.sleep(delay_s)


def run_migrations_online() -> None:
    engine = create_engine(database_url())
    with connect_with_retry(engine) as connection:
        is_postgres = connection.dialect.name == "postgresql"
        if is_postgres:
            # Several backend replicas start at once in Kubernetes, and each runs
            # `alembic upgrade head` in an init container. A session-level advisory lock
            # makes them take turns: the first migrates, the rest find nothing to do.
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
            connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
            connection.commit()
        finally:
            if is_postgres:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY}
                )
                connection.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

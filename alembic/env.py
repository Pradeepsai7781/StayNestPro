
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from alembic import context
from sqlalchemy import engine_from_config, pool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.db.session import Base
import app.models
target_metadata = Base.metadata
# Import models here so Alembic can detect them.
# We'll add each model import as we implement the modules.

config = context.config

database_url = os.getenv("DATABASE_URL")
if not database_url:
    from app.db.session import DATABASE_URL
    database_url = DATABASE_URL.render_as_string(hide_password=False)

config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

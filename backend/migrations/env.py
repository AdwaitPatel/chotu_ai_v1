"""Alembic metadata bridge for GrowthOS's async database engine."""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config


# The `alembic` console script is installed under /usr/local/bin,
# so it does not reliably include the application working directory
# on sys.path in Docker.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


from app.core.database import Base
import app.domain.models  # noqa: F401 - registers model metadata


config = context.config


# -------------------------------------------------------------------
# Database URL
# -------------------------------------------------------------------

database_url = os.getenv("DATABASE_URL")

if database_url:
    # Convert Render/Supabase PostgreSQL URL to the asyncpg driver.
    if database_url.startswith("postgres://"):
        database_url = (
            "postgresql+asyncpg://"
            + database_url.removeprefix("postgres://")
        )

    elif database_url.startswith("postgresql://"):
        database_url = (
            "postgresql+asyncpg://"
            + database_url.removeprefix("postgresql://")
        )

    # Alembic uses ConfigParser internally.
    # ConfigParser treats '%' as interpolation syntax,
    # so '%' must be escaped as '%%'.
    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("%", "%%"),
    )


# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------

if config.config_file_name:
    fileConfig(config.config_file_name)


# -------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------

target_metadata = Base.metadata


# -------------------------------------------------------------------
# Offline migrations
# -------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# -------------------------------------------------------------------
# Synchronous migration function
# -------------------------------------------------------------------

def _run_sync_migrations(connection) -> None:
    """Run migrations using a synchronous connection."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


# -------------------------------------------------------------------
# Online migrations
# -------------------------------------------------------------------

async def run_migrations_online() -> None:
    """Run migrations using the async database engine."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_run_sync_migrations)

    await connectable.dispose()


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
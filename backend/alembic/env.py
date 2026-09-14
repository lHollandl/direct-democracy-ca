"""Alembic environment. Two branch labels in one versions directory.

    alembic upgrade foundation@head
    alembic upgrade iteration@head

The database URL is read through backend/config/settings_env.py, never from
alembic.ini and never from the environment directly (CLAUDE.md Law 10).
Migrations are schema-only (DATABASE.md §6); seeds live in backend/seed.py.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config.settings_env import get_env_settings  # noqa: E402
from backend.models import (  # noqa: E402
    FOUNDATION_TABLES,
    ITERATION_TABLES,
    Base,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", get_env_settings().sync_database_url)


#: `alembic -x half=foundation revision --autogenerate` restricts autogenerate
#: to one half's tables, so each chain only ever describes its own (DATABASE.md
#: §2). Running an upgrade never passes it, and then nothing is filtered.
_HALVES = {"foundation": set(FOUNDATION_TABLES), "iteration": set(ITERATION_TABLES)}
_half = context.get_x_argument(as_dictionary=True).get("half")


def _include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name == "alembic_version":
        return False
    if _half and type_ == "table" and name not in _HALVES[_half]:
        return False
    if _half and type_ in ("index", "column", "unique_constraint", "foreign_key_constraint"):
        table = getattr(obj, "table", None)
        table_name = getattr(table, "name", None)
        if table_name and table_name not in _HALVES[_half]:
            return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
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
            include_object=_include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

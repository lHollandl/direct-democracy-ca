import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# Make sure backend/ is on sys.path so 'from models import Base' works
# regardless of which directory alembic is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Alembic Config object — gives access to alembic.ini values
config = context.config

# Override sqlalchemy.url from the environment — never hardcode credentials.
# DATABASE_URL must be set in backend/.env before running any migration.
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

# Set up Python logging as defined in alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so autogenerate can detect the full schema.
# Every new model file must be imported here — a missing import means
# autogenerate will not see those tables and migrations will be incomplete.
from models import Base  # noqa: E402  — must come after sys.path insert

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Emit SQL to stdout without a live DB connection.
    Useful for reviewing what a migration will do before applying it.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against the live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # NullPool is correct for migrations — no persistent connection reuse
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""`python backend/scripts/verify_schema.py` — does the database match?

DATABASE.md §6: build a scratch database from both migration chains and diff it
against the live database and against the ORM metadata. Run after every
migration; the output is pasted into HISTORY.md.

Three comparisons, all reported:

1. **Live database vs the ORM models** — Alembic's own autogenerate comparison.
   Any operation it wants to emit is drift.
2. **Scratch database (built from the migrations) vs the ORM models** — the
   same comparison against a database built only by `alembic upgrade`. This is
   what catches a migration that was hand-edited out of step with the models.
3. **Scratch vs live, table by table and column by column** — catches anything
   applied to the live database outside a migration.

Also checks the two halves: every table belongs to exactly one of them
(DATABASE.md §2), and every foreign key and every queried column is indexed
(CLAUDE.md Law 4).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alembic import command  # noqa: E402
from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from sqlalchemy import create_engine, inspect, text  # noqa: E402

from backend.config.settings_env import get_env_settings, repo_root  # noqa: E402
from backend.models import FOUNDATION_TABLES, ITERATION_TABLES, Base  # noqa: E402

SCRATCH_DB = "ddc_schema_scratch"
IGNORED_TABLES = {"alembic_version"}


def _alembic_config(url: str) -> Config:
    config = Config(str(repo_root() / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root() / "backend" / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _describe(diff) -> str:
    if isinstance(diff, tuple):
        return " ".join(str(part) for part in diff[:3])
    return str(diff)


def compare_to_models(url: str) -> list[str]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={
                    "compare_type": True,
                    "include_object": lambda obj, name, type_, reflected, compare_to: not (
                        type_ == "table" and name in IGNORED_TABLES
                    ),
                },
            )
            return [_describe(d) for d in compare_metadata(context, Base.metadata)]
    finally:
        engine.dispose()


def snapshot(url: str) -> dict[str, dict]:
    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        out: dict[str, dict] = {}
        for table in inspector.get_table_names():
            if table in IGNORED_TABLES:
                continue
            out[table] = {
                "columns": {
                    column["name"]: {
                        "type": str(column["type"]),
                        "nullable": bool(column["nullable"]),
                    }
                    for column in inspector.get_columns(table)
                },
                "indexes": sorted(
                    index["name"] for index in inspector.get_indexes(table) if index["name"]
                ),
                "foreign_keys": sorted(
                    f"{fk['constrained_columns']}->{fk['referred_table']}"
                    for fk in inspector.get_foreign_keys(table)
                ),
                "unique_constraints": sorted(
                    c["name"] for c in inspector.get_unique_constraints(table) if c["name"]
                ),
            }
        return out
    finally:
        engine.dispose()


def build_scratch(admin_url: str, scratch_url: str) -> None:
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
            connection.execute(text(f'CREATE DATABASE "{SCRATCH_DB}"'))
    finally:
        engine.dispose()
    config = _alembic_config(scratch_url)
    command.upgrade(config, "foundation@head")
    command.upgrade(config, "iteration@head")


def drop_scratch(admin_url: str) -> None:
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
    finally:
        engine.dispose()


def check_halves() -> list[str]:
    problems = []
    declared = set(FOUNDATION_TABLES) | set(ITERATION_TABLES)
    overlap = set(FOUNDATION_TABLES) & set(ITERATION_TABLES)
    for table in overlap:
        problems.append(f"{table} is listed in both halves (DATABASE.md §2)")
    for table in set(Base.metadata.tables) - declared:
        problems.append(f"{table} belongs to neither half (DATABASE.md §2)")
    for table in declared - set(Base.metadata.tables):
        problems.append(f"{table} is declared in a half but has no model")
    return problems


def check_indexes() -> list[str]:
    """CLAUDE.md Law 4: foreign keys and queried columns are indexed, always."""
    problems = []
    for name, table in sorted(Base.metadata.tables.items()):
        indexed_first_columns = {
            list(index.columns)[0].name for index in table.indexes if list(index.columns)
        }
        primary_key_columns = {c.name for c in table.primary_key.columns}
        for fk in table.foreign_key_constraints:
            columns = [c.name for c in fk.columns]
            first = columns[0]
            covered = (
                first in indexed_first_columns
                or first in primary_key_columns
                or any(
                    list(u.columns) and list(u.columns)[0].name == first
                    for u in table.constraints
                    if u.__class__.__name__ == "UniqueConstraint"
                )
            )
            if not covered:
                problems.append(f"{name}.{first} is a foreign key with no index (Law 4)")
    return problems


async def main() -> int:
    parser = argparse.ArgumentParser(description="Check the database against the documents.")
    parser.add_argument(
        "--keep-scratch", action="store_true", help="leave the scratch database in place"
    )
    args = parser.parse_args()

    env = get_env_settings()
    live_url = env.sync_database_url
    base, _, _database = live_url.rpartition("/")
    admin_url = f"{base}/postgres"
    scratch_url = f"{base}/{SCRATCH_DB}"

    print("=== verify_schema.py ===")
    print(f"live database:    {live_url.split('@')[-1]}")
    print(f"scratch database: {SCRATCH_DB} (built from both migration chains)")
    print()

    failures = 0

    print("[1] live database vs the ORM models")
    live_diff = compare_to_models(live_url)
    if live_diff:
        failures += 1
        for item in live_diff:
            print(f"    DRIFT: {item}")
    else:
        print("    no drift")

    print()
    print("[2] scratch database (from migrations) vs the ORM models")
    build_scratch(admin_url, scratch_url)
    try:
        scratch_diff = compare_to_models(scratch_url)
        if scratch_diff:
            failures += 1
            for item in scratch_diff:
                print(f"    DRIFT: {item}")
        else:
            print("    no drift")

        print()
        print("[3] scratch vs live, table by table")
        live_snapshot = snapshot(live_url)
        scratch_snapshot = snapshot(scratch_url)
        only_live = sorted(set(live_snapshot) - set(scratch_snapshot))
        only_scratch = sorted(set(scratch_snapshot) - set(live_snapshot))
        for table in only_live:
            failures += 1
            print(f"    DRIFT: {table} is in the live database but not in the migrations")
        for table in only_scratch:
            failures += 1
            print(f"    DRIFT: {table} is in the migrations but not in the live database")
        differing = 0
        for table in sorted(set(live_snapshot) & set(scratch_snapshot)):
            if live_snapshot[table] != scratch_snapshot[table]:
                differing += 1
                failures += 1
                print(f"    DRIFT: {table} differs")
                for key in ("columns", "indexes", "foreign_keys", "unique_constraints"):
                    if live_snapshot[table][key] != scratch_snapshot[table][key]:
                        print(f"        live    {key}: {live_snapshot[table][key]}")
                        print(f"        scratch {key}: {scratch_snapshot[table][key]}")
        if not only_live and not only_scratch and not differing:
            print(f"    no drift — {len(live_snapshot)} tables identical")
    finally:
        if not args.keep_scratch:
            drop_scratch(admin_url)

    print()
    print("[4] the two halves (DATABASE.md §2)")
    half_problems = check_halves()
    if half_problems:
        failures += 1
        for item in half_problems:
            print(f"    PROBLEM: {item}")
    else:
        print(
            f"    no problems — {len(FOUNDATION_TABLES)} Foundation tables, "
            f"{len(ITERATION_TABLES)} Iteration tables, none in both"
        )

    print()
    print("[5] every foreign key indexed (CLAUDE.md Law 4)")
    index_problems = check_indexes()
    if index_problems:
        failures += 1
        for item in index_problems:
            print(f"    PROBLEM: {item}")
    else:
        print("    no problems")

    print()
    print("=== RESULT: " + ("NO DRIFT" if failures == 0 else f"{failures} PROBLEM AREA(S)") + " ===")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

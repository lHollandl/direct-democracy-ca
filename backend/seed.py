"""The seed runner: `python -m backend.seed --dry-run` / `--apply`.

DATABASE.md §5. Re-runnable: a second run reports what already holds and writes
nothing. Coverage is reported both ways — rows in the file that are not in the
database, and rows in the database that are not in the file — so a seed file
that silently lost an entry is visible.

Seeds are not migrations (DATABASE.md §6): migrations are schema only.

Seed files are director-placed. If one is missing, this stops and says so
rather than inventing civic data.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.categories import MAIN_CATEGORIES
from backend.config.settings_env import get_env_settings
from backend.db import dispose_engine, session_scope
from backend.models import (
    City,
    County,
    MainCategory,
    Official,
    Setting,
    State,
    TermsVersion,
    Umbrella,
)
from backend.services.settings import REQUIRED_KEYS

CONFIG_DIR = Path(__file__).resolve().parent / "config"
GEOGRAPHY_FILE = CONFIG_DIR / "seed_geography.yaml"
CITIES_FILE = CONFIG_DIR / "seed_cities.csv"
OFFICIALS_FILE = CONFIG_DIR / "seed_officials.yaml"
UMBRELLAS_FILE = CONFIG_DIR / "seed_umbrellas.yaml"
SETTINGS_FILE = CONFIG_DIR / "seed_settings.yaml"

LEGAL_DIR = Path(__file__).resolve().parents[1] / "legal"

_VAR = re.compile(r"\$\{([A-Z0-9_]+)\}")


class SeedError(RuntimeError):
    """A seed file is missing, empty, or does not line up with another one."""


@dataclass
class Report:
    """What one seed section did, in both directions (DATABASE.md §5)."""

    section: str
    to_insert: list[str] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)
    in_db_not_in_file: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def pending(self) -> int:
        return len(self.to_insert)

    def render(self) -> str:
        lines = [f"[{self.section}]"]
        lines.append(f"  to write:            {len(self.to_insert)}")
        lines.append(f"  already present:     {len(self.already_present)}")
        lines.append(f"  in database only:    {len(self.in_db_not_in_file)}")
        for item in self.to_insert[:10]:
            lines.append(f"    + {item}")
        if len(self.to_insert) > 10:
            lines.append(f"    + ... and {len(self.to_insert) - 10} more")
        for item in self.in_db_not_in_file[:10]:
            lines.append(f"    ? in database but not in the file: {item}")
        if len(self.in_db_not_in_file) > 10:
            lines.append(f"    ? ... and {len(self.in_db_not_in_file) - 10} more")
        for note in self.notes:
            lines.append(f"    note: {note}")
        return "\n".join(lines)


def _substitute(value: Any) -> Any:
    """Replace `${NAME}` in any YAML string with the configuration value.

    Reads through settings_env (never the environment — CLAUDE.md Law 10) and
    stops with the name in the error if the key is unset.
    """
    if isinstance(value, dict):
        return {k: _substitute(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v) for v in value]
    if not isinstance(value, str):
        return value
    env = get_env_settings()

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        resolved = getattr(env, name, None)
        if resolved in (None, ""):
            raise SeedError(
                f"{name} is used in a seed file but is empty in .env. "
                f"Set {name} and run the seed again."
            )
        return str(resolved)

    return _VAR.sub(replace, value)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise SeedError(
            f"{path} is missing. It is a director-placed seed file (DATABASE.md §5); "
            "the build does not invent its contents."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data:
        raise SeedError(f"{path} is empty. Fill it in or remove the seed step.")
    return _substitute(data)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------


async def seed_settings(session: AsyncSession, apply: bool) -> Report:
    report = Report("settings (DEMOCRACY.md §7.4)")
    data = _load_yaml(SETTINGS_FILE)
    values: dict[str, str] = {k: str(v) for k, v in (data.get("settings") or {}).items()}
    if not values:
        raise SeedError(f"{SETTINGS_FILE} has no `settings:` mapping.")

    missing = [k for k in REQUIRED_KEYS if k not in values]
    if missing:
        raise SeedError(
            f"{SETTINGS_FILE} is missing settings that DEMOCRACY.md §7.4 requires: "
            f"{', '.join(missing)}. Every rule that decides a democratic outcome "
            "must have a value before the platform runs."
        )
    unknown = [k for k in values if k not in REQUIRED_KEYS]
    for key in unknown:
        report.notes.append(
            f"{key} is in the file but is not a setting DEMOCRACY.md §7.4 names; ignored."
        )

    existing_keys = {
        row.key
        for row in (await session.execute(select(Setting))).scalars().all()
    }
    for key in REQUIRED_KEYS:
        if key in existing_keys:
            report.already_present.append(key)
        else:
            report.to_insert.append(f"{key} = {values[key]}")
            if apply:
                session.add(
                    Setting(key=key, value=values[key], changed_by=None, reason="Demo 1 default")
                )
    report.in_db_not_in_file = sorted(existing_keys - set(values))
    return report


async def seed_geography(session: AsyncSession, apply: bool) -> tuple[Report, Report, Report]:
    data = _load_yaml(GEOGRAPHY_FILE)
    state_spec = data.get("state") or {}
    counties_spec = data.get("counties") or []
    if not state_spec or not counties_spec:
        raise SeedError(f"{GEOGRAPHY_FILE} needs both a `state:` and a `counties:` list.")

    state_report = Report("geography: state")
    state = (
        await session.execute(
            select(State).where(State.abbreviation == state_spec["abbreviation"])
        )
    ).scalar_one_or_none()
    if state is None:
        state_report.to_insert.append(f"{state_spec['name']} ({state_spec['abbreviation']})")
        if apply:
            state = State(name=state_spec["name"], abbreviation=state_spec["abbreviation"])
            session.add(state)
            await session.flush()
    else:
        state_report.already_present.append(state.name)

    county_report = Report("geography: counties")
    existing_counties = {
        c.name: c for c in (await session.execute(select(County))).scalars().all()
    }
    for spec in counties_spec:
        if spec["name"] in existing_counties:
            county_report.already_present.append(spec["name"])
        else:
            county_report.to_insert.append(f"{spec['name']} ({spec['fips']})")
            if apply and state is not None:
                session.add(County(state_id=state.id, name=spec["name"], fips=str(spec["fips"])))
    file_county_names = {c["name"] for c in counties_spec}
    county_report.in_db_not_in_file = sorted(set(existing_counties) - file_county_names)
    if apply:
        await session.flush()

    city_report = await _seed_cities(session, apply, file_county_names)
    return state_report, county_report, city_report


async def _seed_cities(session: AsyncSession, apply: bool, county_names: set[str]) -> Report:
    report = Report("geography: cities")
    if not CITIES_FILE.exists():
        raise SeedError(
            f"{CITIES_FILE} is missing. It is a director-placed seed file (DATABASE.md §5)."
        )
    with CITIES_FILE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_header = {"county", "city", "incorporated", "fips"}
    if not rows:
        raise SeedError(f"{CITIES_FILE} has a header but no data rows.")
    if not expected_header.issubset(rows[0].keys()):
        raise SeedError(
            f"{CITIES_FILE} must have the header `county,city,incorporated,fips`; "
            f"found {list(rows[0].keys())}."
        )

    mismatches = sorted({r["county"] for r in rows} - county_names)
    if mismatches:
        raise SeedError(
            f"{CITIES_FILE} names counties that {GEOGRAPHY_FILE.name} does not: "
            f"{', '.join(mismatches)}. County names must match exactly."
        )

    counties = {
        c.name: c.id for c in (await session.execute(select(County))).scalars().all()
    }
    existing = {
        (city.county_id, city.name)
        for city in (await session.execute(select(City))).scalars().all()
    }
    file_pairs: set[tuple[int, str]] = set()
    for row in rows:
        county_id = counties.get(row["county"])
        if county_id is None:
            # Only reachable on --dry-run against an unseeded database.
            report.notes.append(
                f"{row['county']} County is not in the database yet; its cities are "
                "counted as pending."
            )
            report.to_insert.append(f"{row['city']}, {row['county']}")
            continue
        file_pairs.add((county_id, row["city"]))
        if (county_id, row["city"]) in existing:
            report.already_present.append(f"{row['city']}, {row['county']}")
        else:
            report.to_insert.append(f"{row['city']}, {row['county']}")
            if apply:
                session.add(
                    City(
                        county_id=county_id,
                        name=row["city"],
                        incorporated=str(row["incorporated"]).lower() == "true",
                        fips=(row["fips"] or None),
                    )
                )
    by_id = {v: k for k, v in counties.items()}
    report.in_db_not_in_file = sorted(
        f"{name}, {by_id.get(cid, cid)}" for cid, name in existing - file_pairs
    )
    if apply:
        await session.flush()
    return report


async def seed_categories(session: AsyncSession, apply: bool) -> Report:
    """`main_categories` mirrors backend/config/categories.py (DATABASE.md §4.1):
    insert missing, never delete, mark inactive if removed from config."""
    report = Report("main categories (config mirror)")
    existing = {
        row.slug: row for row in (await session.execute(select(MainCategory))).scalars().all()
    }
    config_slugs = set()
    for name in MAIN_CATEGORIES:
        slug = _slug(name)
        config_slugs.add(slug)
        row = existing.get(slug)
        if row is None:
            report.to_insert.append(name)
            if apply:
                session.add(MainCategory(slug=slug, name=name, active=True))
        else:
            report.already_present.append(name)
            if apply and not row.active:
                row.active = True
                report.notes.append(f"{name} was inactive and is active again in config.")
    for slug, row in existing.items():
        if slug not in config_slugs:
            report.in_db_not_in_file.append(f"{row.name} (marked inactive, never deleted)")
            if apply and row.active:
                row.active = False
    if apply:
        await session.flush()
    return report


async def seed_officials(session: AsyncSession, apply: bool) -> Report:
    report = Report("officials directory")
    data = _load_yaml(OFFICIALS_FILE)
    entries = data.get("officials") or []
    if not entries:
        raise SeedError(f"{OFFICIALS_FILE} has no `officials:` list.")

    existing = {
        (o.community_level, o.community_entity_id, o.office): o
        for o in (await session.execute(select(Official))).scalars().all()
    }
    file_keys = set()
    for entry in entries:
        try:
            level, entity_id, label = await _resolve_community(session, entry)
        except SeedError as exc:
            report.notes.append(str(exc))
            report.to_insert.append(f"{entry.get('office')} — unresolved: {exc}")
            continue
        key = (level, entity_id, entry["office"])
        file_keys.add(key)
        if key in existing:
            report.already_present.append(f"{entry['office']} — {label}")
        else:
            report.to_insert.append(f"{entry['office']} — {label}")
            if apply:
                session.add(
                    Official(
                        community_level=level,
                        community_entity_id=entity_id,
                        office=entry["office"],
                        holder_name=entry.get("holder_name") or None,
                        email=entry["email"],
                        source="seed",
                        active=True,
                    )
                )
    report.in_db_not_in_file = sorted(
        f"{office} ({level} {entity})" for (level, entity, office) in set(existing) - file_keys
    )
    if apply:
        await session.flush()
    return report


async def seed_umbrellas(session: AsyncSession, apply: bool) -> Report:
    report = Report("umbrellas (Iteration)")
    data = _load_yaml(UMBRELLAS_FILE)
    entries = data.get("umbrellas") or []
    if not entries:
        raise SeedError(
            f"{UMBRELLAS_FILE} has no `umbrellas:` list. Claude Code does not invent "
            "umbrellas (DEMOCRACY.md §3.2); the build stops."
        )
    categories = {
        row.slug: row.id for row in (await session.execute(select(MainCategory))).scalars().all()
    }
    existing = {
        (u.community_level, u.community_entity_id, u.main_category_id, u.name): u
        for u in (await session.execute(select(Umbrella))).scalars().all()
    }
    file_keys = set()
    for entry in entries:
        category_id = categories.get(entry["main_category"])
        if category_id is None:
            if apply:
                raise SeedError(
                    f"{UMBRELLAS_FILE}: main_category {entry['main_category']!r} is not in "
                    "backend/config/categories.py. The AI must choose from a fixed list and "
                    "so must the seed."
                )
            report.to_insert.append(f"{entry['name']} (category not seeded yet)")
            continue
        try:
            level, entity_id, label = await _resolve_community(session, entry)
        except SeedError as exc:
            report.notes.append(str(exc))
            report.to_insert.append(f"{entry['name']} — unresolved: {exc}")
            continue
        key = (level, entity_id, category_id, entry["name"])
        file_keys.add(key)
        if key in existing:
            report.already_present.append(f"{entry['name']} — {label}")
        else:
            report.to_insert.append(f"{entry['name']} — {label}")
            if apply:
                session.add(
                    Umbrella(
                        main_category_id=category_id,
                        community_level=level,
                        community_entity_id=entity_id,
                        name=entry["name"],
                        statement=entry["statement"],
                        status="active",
                        source="seed",
                    )
                )
    report.in_db_not_in_file = sorted(
        f"{name} ({level} {entity})" for (level, entity, _cat, name) in set(existing) - file_keys
    )
    if apply:
        await session.flush()
    return report


async def seed_terms(session: AsyncSession, apply: bool) -> Report:
    """The placeholder legal text, clearly marked DRAFT (PROJECT.md, Demo 1 scope).

    A terms version must exist before anyone can sign up, because signup records
    which version the person agreed to (DATABASE.md §3.5).
    """
    report = Report("legal: terms version")
    version_file = LEGAL_DIR / "version.txt"
    privacy_file = LEGAL_DIR / "privacy_policy.md"
    terms_file = LEGAL_DIR / "terms_of_service.md"
    for path in (version_file, privacy_file, terms_file):
        if not path.exists():
            raise SeedError(f"{path} is missing; the legal pages ship with the build.")
    version = version_file.read_text(encoding="utf-8").strip()
    existing = (
        await session.execute(select(TermsVersion).where(TermsVersion.version == version))
    ).scalar_one_or_none()
    if existing is None:
        report.to_insert.append(version)
        if apply:
            session.add(
                TermsVersion(
                    version=version,
                    privacy_policy_md=privacy_file.read_text(encoding="utf-8"),
                    terms_of_service_md=terms_file.read_text(encoding="utf-8"),
                )
            )
            await session.flush()
    else:
        report.already_present.append(version)
    return report


async def _resolve_community(session: AsyncSession, entry: dict) -> tuple[str, int, str]:
    """Turn a seed file's community words into `(level, entity_id, label)`."""
    level = entry["community_level"]
    name = entry["community"]
    if level == "state":
        row = (
            await session.execute(select(State).where(State.name == name))
        ).scalar_one_or_none()
        if row is None:
            raise SeedError(f"state {name!r} is not seeded yet")
        return "state", row.id, name
    if level == "county":
        row = (
            await session.execute(select(County).where(County.name == name))
        ).scalar_one_or_none()
        if row is None:
            raise SeedError(f"county {name!r} is not seeded yet")
        return "county", row.id, f"{name} County"
    if level == "city":
        county_name = entry.get("county")
        if not county_name:
            raise SeedError(f"city {name!r} needs a `county:` so it can be resolved")
        county = (
            await session.execute(select(County).where(County.name == county_name))
        ).scalar_one_or_none()
        if county is None:
            raise SeedError(f"county {county_name!r} is not seeded yet")
        city = (
            await session.execute(
                select(City).where(City.county_id == county.id, City.name == name)
            )
        ).scalar_one_or_none()
        if city is None:
            raise SeedError(f"city {name!r} in {county_name} County is not seeded yet")
        return "city", city.id, f"{name}, {county_name} County"
    raise SeedError(f"{level!r} is not a governance level the platform knows")


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


async def run(apply: bool) -> int:
    reports: list[Report] = []
    async with session_scope() as session:
        reports.append(await seed_settings(session, apply))
        state_r, county_r, city_r = await seed_geography(session, apply)
        reports.extend([state_r, county_r, city_r])
        reports.append(await seed_terms(session, apply))
        reports.append(await seed_officials(session, apply))
        reports.append(await seed_categories(session, apply))
        reports.append(await seed_umbrellas(session, apply))
        if not apply:
            await session.rollback()

    mode = "APPLY" if apply else "DRY RUN"
    print(f"=== backend.seed — {mode} ===")
    for report in reports:
        print(report.render())
    pending = sum(r.pending for r in reports)
    print("---")
    print(f"pending writes: {pending}")
    if not apply and pending == 0:
        print("Nothing to do: every seed row is already in the database.")
    return pending


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.seed",
        description="Load the director-placed seed files into the database (DATABASE.md §5).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="report and write nothing")
    group.add_argument("--apply", action="store_true", help="write the missing rows")
    args = parser.parse_args(argv)

    async def _main() -> int:
        try:
            pending = await run(apply=args.apply)
        except SeedError as exc:
            print(f"SEED STOPPED: {exc}", file=sys.stderr)
            return 2
        finally:
            await dispose_engine()
        return 0 if (args.apply or pending == 0) else 1

    return asyncio.run(_main())


if __name__ == "__main__":
    raise SystemExit(main())

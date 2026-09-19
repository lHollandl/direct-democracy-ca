"""Test fixtures: a throwaway database, a fake Redis, and a mocked Ollama.

ARCHITECTURE.md §10 asks for a throwaway Postgres created and dropped by the
test session. This creates and drops a throwaway **database** on the Postgres
the `.env` already points at, rather than a throwaway container, because the
sandbox this build ran in cannot pull images (recorded in HISTORY.md). The
schema comes from the two migration chains, exactly as a real database does —
never from `create_all`, which would let the models and the migrations drift
apart without anything noticing.

Ollama and the search provider are mocked through their client interfaces. One
opt-in test (`-m live`) hits the real Ollama to check the prompt files still
produce the shape the code parses.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config.settings_env import get_env_settings, repo_root

TEST_DB = "ddc_test"


def _urls() -> tuple[str, str, str]:
    env = get_env_settings()
    sync_base, _, _name = env.sync_database_url.rpartition("/")
    async_base, _, _name2 = env.DATABASE_URL.rpartition("/")
    return f"{sync_base}/postgres", f"{sync_base}/{TEST_DB}", f"{async_base}/{TEST_DB}"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def throwaway_database():
    admin_url, sync_url, _async_url = _urls()
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    engine.dispose()

    config = Config(str(repo_root() / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root() / "backend" / "alembic"))
    config.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(config, "foundation@head")
    command.upgrade(config, "iteration@head")

    yield sync_url

    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
    engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_state(throwaway_database):
    """Every test starts from an empty database with the settings seeded.

    Settings are seeded because every democratic rule reads them (CLAUDE.md
    Law 8) — a test database without them is not a database this platform can
    run against.
    """
    import fakeredis.aioredis

    from backend.clients import email as email_client
    from backend.clients import ollama as ollama_client
    from backend.clients import redis as redis_client
    from backend.clients import search as search_client
    from backend.db import override_engine
    from backend.models import Base
    from backend.services import export as export_service

    _admin, _sync, async_url = _urls()
    engine = create_async_engine(async_url, poolclass=None)
    override_engine(engine)
    redis_client.override_redis(fakeredis.aioredis.FakeRedis(decode_responses=True))
    ollama_client.override_ollama(FakeOllama())
    search_client.override_search(FakeSearch(configured=False))
    email_client.sent_messages().clear()
    export_service.clear_contributors()

    async with engine.begin() as connection:
        tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    await _seed_minimum(engine)
    yield
    await engine.dispose()


async def _seed_minimum(engine) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from backend.config.categories import MAIN_CATEGORIES
    from backend.models import City, County, MainCategory, Official, Setting, State, TermsVersion
    from backend.seed import SETTINGS_FILE, _load_yaml, _slug

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        for key, value in (_load_yaml(SETTINGS_FILE)["settings"]).items():
            session.add(
                Setting(key=key, value=str(value), changed_by=None, reason="test default")
            )
        state = State(name="California", abbreviation="CA")
        session.add(state)
        await session.flush()
        county = County(state_id=state.id, name="Santa Clara", fips="06085")
        other_county = County(state_id=state.id, name="Solano", fips="06095")
        session.add_all([county, other_county])
        await session.flush()
        session.add_all(
            [
                City(county_id=county.id, name="San Jose", incorporated=True),
                City(county_id=other_county.id, name="Vallejo", incorporated=True),
            ]
        )
        for name in MAIN_CATEGORIES:
            session.add(MainCategory(slug=_slug(name), name=name, active=True))
        session.add(
            TermsVersion(
                version="test-terms-1",
                privacy_policy_md="# Privacy (test)",
                terms_of_service_md="# Terms (test)",
            )
        )
        await session.flush()
        session.add(
            Official(
                community_level="city",
                community_entity_id=1,
                office="Mayor",
                holder_name=None,
                email="director@example.com",
                source="seed",
                active=True,
            )
        )
        await session.commit()


class FakeOllama:
    """Stands in for the host GPU. Returns whatever the test tells it to."""

    def __init__(self) -> None:
        self.model = "test-model"
        self.embed_model = "test-embed"
        self.responses: dict[str, str] = {}
        self.embeddings: dict[str, list[float]] = {}
        self.calls: list[tuple[str, dict]] = []
        self.fail_with: Exception | None = None

    @property
    def model_label(self) -> str:
        return f"ollama:{self.model}"

    @property
    def embed_model_label(self) -> str:
        return f"ollama:{self.embed_model}"

    async def generate(self, prompt_file: str, variables: dict[str, Any]):
        from backend.clients.ollama import load_prompt

        self.calls.append((prompt_file, variables))
        if self.fail_with:
            raise self.fail_with
        return self.responses.get(prompt_file, "{}"), load_prompt(prompt_file)

    async def embed(self, text_body: str) -> list[float]:
        if self.fail_with:
            raise self.fail_with
        return self.embeddings.get(text_body, [1.0, 0.0, 0.0])


class FakeSearch:
    def __init__(self, configured: bool = True) -> None:
        self.provider = "fake"
        self.configured = configured
        self.results: list = []
        self.raw: Any = {}

    def require_configured(self) -> None:
        from backend.errors import ExternalServiceDown

        if not self.configured:
            raise ExternalServiceDown(
                "Reference recommendation needs a web search provider, and none "
                "is configured on this platform yet.",
                code="search_not_configured",
            )

    async def search(self, query: str):
        return self.results, self.raw


@pytest_asyncio.fixture
async def session():
    from backend.db import session_scope

    async with session_scope() as s:
        yield s


@pytest_asyncio.fixture
async def app():
    from backend.errors import install_error_handlers
    from backend.middleware import install_middleware
    from fastapi import FastAPI

    from backend.routers import (
        admin,
        amendments,
        auth,
        ballots,
        comments,
        feed,
        geo,
        juries,
        legal,
        me,
        posts,
        references,
        solutions,
        summaries,
        transparency,
        umbrellas,
        votes,
    )

    application = FastAPI()
    install_middleware(application)
    install_error_handlers(application)
    for module in (
        auth, me, geo, legal, transparency, posts, feed, umbrellas, solutions,
        amendments, comments, votes, references, ballots, juries, summaries, admin,
    ):
        application.include_router(module.router)
    return application


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        yield http_client


# --------------------------------------------------------------------------
# Helpers every test file uses
# --------------------------------------------------------------------------


async def make_user(
    client: AsyncClient,
    *,
    email: str,
    display_name: str,
    city_id: int = 1,
    county_id: int = 1,
    verify: bool = True,
    admin: bool = False,
    password: str = "Crosswalk1",
) -> dict:
    """Sign up, confirm the email, sign in, and hand back the tokens."""
    from backend.clients import email as email_client

    response = await client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": password,
            "real_name": f"Real {display_name}",
            "display_name": display_name,
            "date_of_birth": "1990-01-01",
            "gender": "prefer_not_to_say",
            "political_party": "no_party_preference",
            "county_id": county_id,
            "city_id": city_id,
            "terms_version": "test-terms-1",
            "agreed_to_terms": True,
        },
    )
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]

    if verify:
        import re

        body = email_client.sent_messages()[-1]["body"]
        token = re.search(r"token=([A-Za-z0-9_\-]+)", body).group(1)
        confirmed = await client.post("/auth/verify-email", json={"token": token})
        assert confirmed.status_code == 200, confirmed.text

    if admin:
        from backend.db import session_scope
        from backend.repositories import users as users_repo

        async with session_scope() as session:
            row = await users_repo.get(session, user_id)
            row.is_admin = True

    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {
        "id": user_id,
        "email": email,
        "password": password,
        "token": login.json()["access_token"],
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


async def settle_jobs(timeout: float = 30.0) -> None:
    """Wait for the background jobs a request started (ARCHITECTURE.md §7).

    The routers spawn labeling and similarity as independent tasks, so a test
    that wants to see their result has to wait for them, exactly as a person
    refreshing the page does.
    """
    from backend.jobs import runner

    # The job is spawned from an `after_commit` hook through `loop.call_soon`,
    # so let the loop turn before looking for it.
    for _ in range(3):
        await asyncio.sleep(0)
    await runner.drain(timeout=timeout)
    for _ in range(3):
        await asyncio.sleep(0)
    await runner.drain(timeout=timeout)


def labeler_answer(*, main_category: str, umbrella_id: int | None, level: str, entity_id: int) -> str:
    import json

    return json.dumps(
        {
            "main_category": main_category,
            "umbrellas": [
                {
                    "community_level": level,
                    "community_entity_id": entity_id,
                    "umbrella_id": umbrella_id,
                }
            ],
            "confidence": 0.9,
        }
    )


async def make_umbrella(
    *, name: str, statement: str, level: str = "city", entity_id: int = 1, category_slug: str = "public_safety"
) -> int:
    from backend.db import session_scope
    from backend.models import Umbrella
    from backend.repositories import umbrellas as umbrellas_repo

    async with session_scope() as session:
        category = await umbrellas_repo.category_by_slug(session, category_slug)
        row = Umbrella(
            main_category_id=category.id,
            community_level=level,
            community_entity_id=entity_id,
            name=name,
            statement=statement,
            status="active",
            source="seed",
        )
        session.add(row)
        await session.flush()
        return row.id


async def set_setting(key: str, value: str) -> None:
    from backend.db import session_scope
    from backend.repositories import settings as settings_repo
    from backend.services import settings as settings_service

    async with session_scope() as session:
        await settings_repo.append(
            session, key=key, value=value, changed_by=None, reason="test"
        )
    await settings_service.invalidate_cache()


async def make_active(user_ids: list[int]) -> None:
    """The active-user count needs a recent `last_active_at` (DEMOCRACY §2.4)."""
    from backend.db import session_scope
    from backend.repositories import users as users_repo

    async with session_scope() as session:
        for user_id in user_ids:
            await users_repo.touch_last_active(session, user_id)


def days_ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


__all__ = [
    "FakeOllama",
    "FakeSearch",
    "days_ago",
    "labeler_answer",
    "make_active",
    "make_umbrella",
    "make_user",
    "set_setting",
    "date",
]

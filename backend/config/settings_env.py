"""The only module in the codebase that reads the process environment.

CLAUDE.md Law 10: configuration is centralized. Ports, URLs, model names and
secrets live in `.env` at the repository root and are read here into a single
frozen `Settings` object. Every other module imports `get_env_settings()`.

Startup refuses to run when a required key is missing, naming the key
(ARCHITECTURE.md §3).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


class ConfigurationError(RuntimeError):
    """Raised at startup when configuration is missing or unusable."""


class Settings(BaseSettings):
    """Every key in ARCHITECTURE.md §3, plus the Docker Compose credentials.

    Keys with no sensible universal default are required: the application
    refuses to start without them rather than inventing a value.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # --- Data stores -----------------------------------------------------
    DATABASE_URL: str
    REDIS_URL: str

    # --- Tokens ----------------------------------------------------------
    JWT_SECRET: str
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 14
    EMAIL_VERIFY_HOURS: int = 24
    PASSWORD_RESET_MINUTES: int = 30
    # How long a person has to collect the data export they asked for
    # (DATABASE.md §3.11) — a user-rights window (CLAUDE.md §6), not a
    # democratic rule, so it is configuration rather than a settings-table
    # value (director decision, HISTORY.md; audit demo-01 run 4, MEDIUM: this
    # was a bare module constant, undocumented and unrecorded). No default:
    # startup refuses to run without it.
    EXPORT_FILE_HOURS: int

    # --- Email -----------------------------------------------------------
    EMAIL_BACKEND: Literal["console", "smtp"] = "console"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str

    # --- Ollama ----------------------------------------------------------
    OLLAMA_BASE_URL: str
    OLLAMA_MODEL: str
    EMBED_MODEL: str
    OLLAMA_TIMEOUT_SECONDS: int = 60

    # --- Web search (reference recommendation) ---------------------------
    SEARCH_PROVIDER: str = ""
    SEARCH_API_KEY: str = ""
    SEARCH_BASE_URL: str = ""

    # --- Platform --------------------------------------------------------
    OFFICIALS_TEST_EMAIL: str
    BUILD_LABEL: str
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Salts terms_acceptances.ip_hash (DATABASE.md §3.5) so a stored hash
    # cannot be reversed by enumerating the IPv4 space (audit demo-01 run 5,
    # LOW: an unsalted SHA-256 of the address was reversible in seconds).
    # No default: startup refuses to run without it.
    IP_HASH_SECRET: str
    # The address the frontend is reached at (ARCHITECTURE.md §3) — used
    # wherever a link must work outside the site: the `mailto:` body, the PDF
    # footer, the summary's verify text (DEMOCRACY.md §11.5; audit demo-01
    # run 3, LOW).
    PUBLIC_BASE_URL: str
    RATE_LIMIT_WRITE_PER_MINUTE: int = 30
    LOG_LEVEL: str = "INFO"

    # --- Test data (ARCHITECTURE.md §3; change/01, C1-14; fix-1, FX-01) ----
    # `true` only in a demo environment. Enables load_test_data.py and lets
    # signup accept TEST_DATA_EMAIL_DOMAIN; when `false` the loader refuses
    # to run and signup refuses that domain. There is no remover — test data
    # is cleared by rebuilding the database from empty (Law 6).
    ALLOW_TEST_DATA: bool = False
    TEST_DATA_EMAIL_DOMAIN: str = "test.example.com"
    TEST_DATA_PASSWORD: str = "Str0ngPassword!"

    # --- Docker Compose only (infra/docker-compose.yml --env-file .env) ---
    # Added by the demo-01 build: ARCHITECTURE.md §3 says one root .env is
    # passed to Compose with --env-file, and Compose needs these three.
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    POSTGRES_PORT: int = 5432
    REDIS_PORT: int = 6379

    @field_validator("JWT_SECRET", "IP_HASH_SECRET")
    @classmethod
    def _secret_is_real(cls, v: str, info) -> str:
        if len(v) < 32 or v.startswith("CHANGE_ME"):
            raise ValueError(
                f"{info.field_name} must be at least 32 characters and not the "
                ".env.example placeholder"
            )
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def sync_database_url(self) -> str:
        """The same database, for tools that cannot speak asyncpg (Alembic CLI)."""
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg")

    @property
    def search_configured(self) -> bool:
        return bool(self.SEARCH_API_KEY and self.SEARCH_PROVIDER)

    def absolute_url(self, path: str) -> str:
        """`PUBLIC_BASE_URL` plus a site-relative path, e.g. `/summaries/...`
        (DEMOCRACY.md §11.5)."""
        return f"{self.PUBLIC_BASE_URL.rstrip('/')}{path}"


@lru_cache(maxsize=1)
def get_env_settings() -> Settings:
    """Load and cache the configuration, refusing to start on a missing key."""
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = sorted({str(e["loc"][0]) for e in exc.errors()})
        raise ConfigurationError(
            "Configuration is incomplete or invalid. Fix these keys in "
            f"{ENV_FILE}: {', '.join(missing)}. "
            "Copy .env.example and fill every value."
        ) from exc


def env_file_path() -> Path:
    return ENV_FILE


def repo_root() -> Path:
    return REPO_ROOT

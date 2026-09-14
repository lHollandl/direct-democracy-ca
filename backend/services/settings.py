"""Runtime settings: every number that decides a democratic outcome.

CLAUDE.md Law 8 — thresholds and rules are public settings. They live in the
`settings` table, are displayed on a public page, are printed in every summary
document they produced, and are never constants in code.

This module is the only reader. Values are cached in Redis for 60 seconds
(ARCHITECTURE.md §2); a settings change clears the cache immediately so the
next request sees the new value.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients import redis as redis_client
from backend.errors import ValidationFailed
from backend.repositories import settings as settings_repo

CACHE_KEY = "settings:current"
CACHE_TTL_SECONDS = 60


class SettingSpec:
    """One setting: how to parse it and how to explain it in plain language."""

    def __init__(self, key: str, kind: str, meaning: str, where: str):
        self.key = key
        self.kind = kind
        self.meaning = meaning
        self.where = where

    def parse(self, raw: str) -> Any:
        try:
            if self.kind == "int":
                return int(raw)
            if self.kind == "decimal":
                return float(Decimal(raw))
            return raw
        except (ValueError, ArithmeticError) as exc:
            raise ValidationFailed(
                f"The value for {self.key} must be a {self.kind}.", code="bad_setting_value"
            ) from exc


#: Exactly DEMOCRACY.md §7.4. Adding a key here without adding it to that table
#: is a document conflict, not a code change.
SPECS: dict[str, SettingSpec] = {
    s.key: s
    for s in [
        SettingSpec("active_user_window_days", "int",
                    "How recently someone must have used the platform to count as an active "
                    "user of their community.", "DEMOCRACY.md §2.4"),
        SettingSpec("dominant_pct", "decimal",
                    "Percentage of active users whose net support makes a solution dominant.",
                    "DEMOCRACY.md §7.1"),
        SettingSpec("dominant_min", "int",
                    "Fixed number of net upvotes that makes a solution dominant, used when it "
                    "is lower than the percentage.", "DEMOCRACY.md §7.1"),
        SettingSpec("amendment_pct", "decimal",
                    "Percentage of a solution's supporters whose net support absorbs an "
                    "amendment.", "DEMOCRACY.md §5.3"),
        SettingSpec("amendment_min", "int",
                    "Fixed number of net upvotes that absorbs an amendment, used when it is "
                    "lower than the percentage.", "DEMOCRACY.md §5.3"),
        SettingSpec("ballot_pct", "decimal",
                    "Percentage of active users whose net support qualifies a solution for the "
                    "ballot.", "DEMOCRACY.md §7.2"),
        SettingSpec("ballot_min", "int",
                    "Fixed number of net upvotes that qualifies a solution for the ballot, used "
                    "when it is lower than the percentage.", "DEMOCRACY.md §7.2"),
        SettingSpec("ballot_min_dominant_days", "int",
                    "How many days a solution must have been dominant before it can go on a "
                    "ballot.", "DEMOCRACY.md §7.2"),
        SettingSpec("similarity_threshold", "decimal",
                    "How alike two amendments must be, from 0 to 1, before the platform asks "
                    "whether they are the same change.", "DEMOCRACY.md §5.4"),
        SettingSpec("similarity_confirm_min", "int",
                    "How many people must press Same before two amendments are counted "
                    "together.", "DEMOCRACY.md §5.4"),
        SettingSpec("jury_size", "int", "How many citizens are drawn for a ballot jury.",
                    "DEMOCRACY.md §8.1"),
        SettingSpec("jury_no_repeat_cycles", "int",
                    "How many cycles must pass before someone can be drawn for jury duty in the "
                    "same community again.", "DEMOCRACY.md §8.1"),
        SettingSpec("jury_review_days", "int",
                    "How long jurors have to accept and review. In Demo 1 the director opens the "
                    "ballot by hand, so this is displayed but does not fire.",
                    "DEMOCRACY.md §8.3"),
        SettingSpec("ballot_window_days", "int",
                    "How long a ballot stays open. In Demo 1 the director closes it by hand, so "
                    "this is displayed but does not fire.", "DEMOCRACY.md §10.3"),
        SettingSpec("ballot_pass_rule", "text",
                    "How a ballot item passes. `simple_majority` means more yes than no, with "
                    "at least the quorum voting.", "DEMOCRACY.md §10.4"),
        SettingSpec("ballot_quorum_min", "int",
                    "The smallest number of votes a ballot item needs before its result counts.",
                    "DEMOCRACY.md §10.4"),
        SettingSpec("comment_max_depth", "int", "How deeply comment replies can nest.",
                    "DEMOCRACY.md §6"),
        SettingSpec("comment_edit_minutes", "int",
                    "How long after posting a comment can still be edited.", "DEMOCRACY.md §6"),
        SettingSpec("label_retry_minutes", "int",
                    "How often the platform retries filing a post whose labeling failed.",
                    "DEMOCRACY.md §4.1"),
        SettingSpec("references_ai_max_per_umbrella", "int",
                    "The most references AI may recommend for one umbrella.",
                    "DEMOCRACY.md §9.4"),
        SettingSpec("reference_reject_min", "int",
                    "How many people must press Not useful before a reference is marked "
                    "rejected. It is never deleted.", "DEMOCRACY.md §9.4"),
        SettingSpec("min_signup_age", "int",
                    "The youngest someone may be, in years, on the day they sign up.",
                    "DEMOCRACY.md §2.3"),
    ]
}

REQUIRED_KEYS = tuple(SPECS)


async def all_values(session: AsyncSession) -> dict[str, Any]:
    """Every setting, parsed. Cached for 60 seconds."""
    cached = await redis_client.cache_get(CACHE_KEY)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass
    rows = await settings_repo.current_rows(session)
    values = {row.key: SPECS[row.key].parse(row.value) for row in rows if row.key in SPECS}
    missing = [k for k in REQUIRED_KEYS if k not in values]
    if missing:
        raise ValidationFailed(
            "The platform is missing settings that every rule depends on: "
            f"{', '.join(missing)}. Run `python -m backend.seed --apply`.",
            code="settings_missing",
        )
    await redis_client.cache_set(CACHE_KEY, json.dumps(values), CACHE_TTL_SECONDS)
    return values


async def get(session: AsyncSession, key: str) -> Any:
    return (await all_values(session))[key]


async def public_view(session: AsyncSession) -> list[dict[str, Any]]:
    """What `GET /settings` shows: value, meaning, where the rule is written,
    and when this value took effect."""
    rows = {row.key: row for row in await settings_repo.current_rows(session)}
    out = []
    for key, spec in SPECS.items():
        row = rows.get(key)
        out.append(
            {
                "key": key,
                "value": spec.parse(row.value) if row else None,
                "raw_value": row.value if row else None,
                "meaning": spec.meaning,
                "defined_in": spec.where,
                "effective_from": row.effective_from if row else None,
                "changed_by_user_id": row.changed_by if row else None,
                "reason": row.reason if row else None,
                "set_by": ("the platform seed" if row and row.changed_by is None else "an administrator"),
            }
        )
    return out


async def snapshot_for_cycle(session: AsyncSession) -> dict[str, Any]:
    """Every §7.4 key and value, recorded on a cycle at prepare time so the
    summary document can print the rules that were actually in force."""
    return dict(await all_values(session))


async def change(
    session: AsyncSession,
    *,
    key: str,
    value: str,
    changed_by: int,
    reason: str | None,
) -> tuple[Any, Any]:
    """Append a new row (never an update) and clear the cache.

    Returns (old parsed value, new parsed value) so the admin log can record both.
    """
    if key not in SPECS:
        raise ValidationFailed(
            f"{key} is not a platform setting. The full list is on the public settings page.",
            code="unknown_setting",
        )
    spec = SPECS[key]
    new_value = spec.parse(value)
    current = await settings_repo.current_rows(session)
    old_value = next((spec.parse(r.value) for r in current if r.key == key), None)
    await settings_repo.append(
        session, key=key, value=value, changed_by=changed_by, reason=reason
    )
    await redis_client.cache_delete_prefix(CACHE_KEY)
    return old_value, new_value


async def invalidate_cache() -> None:
    await redis_client.cache_delete_prefix(CACHE_KEY)

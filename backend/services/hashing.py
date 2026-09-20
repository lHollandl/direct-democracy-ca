"""Canonical JSON and SHA-256. The one place a content hash is computed.

CLAUDE.md Law 6: `content_hash` is generated at creation for every post,
solution and summary document from the content plus its AI metadata, and is
never modified or deleted afterwards. DEMOCRACY.md §11.3 fixes the canonical
form: keys sorted, UTF-8, no whitespace.

Anyone can recompute a hash from the JSON the platform publishes, which is the
whole point — so the rules here are simple enough to reimplement in any
language: sort the keys, drop the whitespace, encode UTF-8, SHA-256, lowercase
hex.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def canonical_json(data: Any) -> str:
    """The canonical text form: sorted keys, no whitespace, UTF-8, no escapes."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_encode,
    )


def _encode(value: Any) -> str:
    if isinstance(value, datetime):
        return iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not part of the canonical form")


def iso(moment: datetime) -> str:
    """One timestamp spelling everywhere, so a hash is reproducible."""
    return moment.isoformat()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_payload(data: Any) -> str:
    """SHA-256 of the canonical JSON of `data`, lowercase hex."""
    return sha256_hex(canonical_json(data))


def post_content_hash(
    *, problem_text: str, author_id: int, created_at: datetime, ai_contribution_percentage: int
) -> str:
    """DATABASE.md §4.3."""
    return hash_payload(
        {
            "ai_contribution_percentage": ai_contribution_percentage,
            "author_id": author_id,
            "created_at": iso(created_at),
            "problem_text": problem_text,
        }
    )


def post_solution_content_hash(
    *, post_id: int, position: int, text: str, created_at: datetime
) -> str:
    """DATABASE.md §4.4."""
    return hash_payload(
        {
            "created_at": iso(created_at),
            "position": position,
            "post_id": post_id,
            "text": text,
        }
    )


def solution_version_content_hash(
    *, solution_id: int, version: int, text: str, created_by: int, created_at: datetime
) -> str:
    """DATABASE.md §4.8."""
    return hash_payload(
        {
            "created_at": iso(created_at),
            "created_by": created_by,
            "solution_id": solution_id,
            "text": text,
            "version": version,
        }
    )


def amendment_content_hash(
    *,
    solution_id: int,
    base_version: int,
    author_id: int,
    proposed_text: str,
    rationale: str,
    created_at: datetime,
) -> str:
    """DATABASE.md §4.9's exact canonical field list: `{solution_id,
    base_version, proposed_text, rationale, author_id, created_at}`."""
    return hash_payload(
        {
            "author_id": author_id,
            "base_version": base_version,
            "created_at": iso(created_at),
            "proposed_text": proposed_text,
            "rationale": rationale,
            "solution_id": solution_id,
        }
    )


def comment_content_hash(
    *,
    target_type: str,
    target_id: int,
    parent_id: int | None,
    reply_to_comment_id: int | None,
    author_id: int,
    text: str,
    created_at: datetime,
) -> str:
    """DATABASE.md §4.11's exact canonical field list (fix demo-01 run 1:
    `parent_id` was missing; fix demo-01 run 2: `reply_to_comment_id` added —
    `text` is only ever what the author typed, never a rendered name)."""
    return hash_payload(
        {
            "author_id": author_id,
            "created_at": iso(created_at),
            "parent_id": parent_id,
            "reply_to_comment_id": reply_to_comment_id,
            "target_id": target_id,
            "target_type": target_type,
            "text": text,
        }
    )


def comment_revision_content_hash(
    *, comment_id: int, revision: int, text: str, author_id: int, created_at: datetime
) -> str:
    """DATABASE.md §4.11's `comment_revisions` canonical field list."""
    return hash_payload(
        {
            "author_id": author_id,
            "comment_id": comment_id,
            "created_at": iso(created_at),
            "revision": revision,
            "text": text,
        }
    )


def summary_hash(data: dict) -> str:
    """DEMOCRACY.md §11.3 — SHA-256 of the canonical JSON of the document data."""
    return hash_payload(data)


def label_preview_input_hash(
    *, problem_text: str, communities: list[tuple[str, int]]
) -> str:
    """DATABASE.md §4.19 — SHA-256 of canonical JSON `{problem_text,
    communities}` with `communities` sorted, so the same draft always hashes
    the same way regardless of the order the author picked them in."""
    sorted_communities = sorted(
        ({"level": level, "entity_id": entity_id} for level, entity_id in communities),
        key=lambda c: (c["level"], c["entity_id"]),
    )
    return hash_payload({"problem_text": problem_text, "communities": sorted_communities})

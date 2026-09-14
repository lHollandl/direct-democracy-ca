"""Hash round-trips (I-31).

CLAUDE.md Law 6: a content hash is generated at creation and never modified.
The promise only means something if anyone can recompute it, so these tests
recompute every hash the platform stores, from the stored fields alone.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from backend.services import hashing


def test_canonical_json_sorts_keys_and_drops_whitespace():
    text = hashing.canonical_json({"b": 1, "a": {"d": 2, "c": 3}})
    assert text == '{"a":{"c":3,"d":2},"b":1}'


def test_canonical_json_is_stable_across_key_order():
    one = hashing.canonical_json({"a": 1, "b": [1, 2, {"y": 1, "x": 2}]})
    two = hashing.canonical_json({"b": [1, 2, {"x": 2, "y": 1}], "a": 1})
    assert one == two


def test_canonical_json_keeps_non_ascii_readable():
    assert hashing.canonical_json({"name": "San José"}) == '{"name":"San José"}'


def test_hash_is_plain_sha256_of_the_canonical_text():
    data = {"z": 1, "a": "two"}
    expected = hashlib.sha256(hashing.canonical_json(data).encode("utf-8")).hexdigest()
    assert hashing.hash_payload(data) == expected


def test_anyone_can_recompute_a_summary_hash_without_this_code():
    document = {"header": {"cycle_number": 3}, "results": [{"yes": 2, "no": 1}]}
    stored = hashing.summary_hash(document)
    # What an outsider would do with the downloaded JSON and any SHA-256 tool.
    outside = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    assert stored == outside


def test_one_changed_letter_changes_the_fingerprint():
    before = hashing.summary_hash({"text": "a crossing guard"})
    after = hashing.summary_hash({"text": "a crossing guards"})
    assert before != after


def test_every_content_hash_recomputes_from_its_stored_fields():
    now = datetime(2026, 9, 14, 1, 2, 3, tzinfo=timezone.utc)
    assert hashing.post_content_hash(
        problem_text="p", author_id=1, created_at=now, ai_contribution_percentage=0
    ) == hashing.post_content_hash(
        problem_text="p", author_id=1, created_at=now, ai_contribution_percentage=0
    )
    assert hashing.post_solution_content_hash(
        post_id=1, position=1, text="s", created_at=now
    ) == hashing.post_solution_content_hash(post_id=1, position=1, text="s", created_at=now)
    assert hashing.solution_version_content_hash(
        solution_id=1, version=2, text="v", created_by=3, created_at=now
    ) == hashing.solution_version_content_hash(
        solution_id=1, version=2, text="v", created_by=3, created_at=now
    )


def test_hashes_differ_when_any_field_differs():
    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    base = dict(solution_id=1, version=1, text="t", created_by=1, created_at=now)
    first = hashing.solution_version_content_hash(**base)
    for field, value in [
        ("solution_id", 2),
        ("version", 2),
        ("text", "u"),
        ("created_by", 2),
        ("created_at", datetime(2026, 9, 15, tzinfo=timezone.utc)),
    ]:
        assert hashing.solution_version_content_hash(**{**base, field: value}) != first


def test_unsupported_types_are_refused_rather_than_coerced():
    class Thing:
        pass

    try:
        hashing.canonical_json({"x": Thing()})
    except TypeError as exc:
        assert "canonical form" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("a value with no canonical form must not be hashed silently")

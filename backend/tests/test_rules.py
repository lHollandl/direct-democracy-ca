"""Table-driven tests for every rule in `backend/services/rules.py` (I-29).

The threshold formula decides every democratic status on this platform, so it
is tested at its boundaries: zero, one, the exact crossing point, and either
side of the rounding.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.services import rules


@pytest.mark.parametrize(
    "pct, minimum, denominator, expected, why",
    [
        (25, 3, 0, 1, "nobody in the denominator still needs one person"),
        (25, 3, 1, 1, "25% of 1 rounds up to 1"),
        (25, 3, 4, 1, "25% of 4 is exactly 1"),
        (25, 3, 5, 2, "25% of 5 rounds up to 2"),
        (25, 3, 12, 3, "25% of 12 is exactly 3, equal to the minimum"),
        (25, 3, 13, 3, "above the crossing point the fixed minimum applies"),
        (25, 3, 1000, 3, "a big community is governed by the fixed minimum"),
        (5, 3, 20, 1, "5% of 20 is exactly 1"),
        (5, 3, 21, 2, "5% of 21 rounds up to 2"),
        (5, 3, 60, 3, "5% of 60 is exactly 3"),
        (5, 3, 61, 3, "past the crossing point the minimum wins"),
        (10, 5, 50, 5, "10% of 50 is exactly the minimum"),
        (10, 5, 51, 5, "the lower of the two, always"),
        (10, 5, 30, 3, "small community: the percentage wins"),
        (100, 1, 10, 1, "a minimum of 1 caps everything at 1"),
        (0, 5, 1000, 1, "a percentage of zero still needs one person"),
        (25, 3, -4, 1, "a negative denominator cannot go below one"),
    ],
)
def test_threshold(pct, minimum, denominator, expected, why):
    assert rules.threshold(pct, minimum, denominator) == expected, why


def test_threshold_is_never_zero():
    for denominator in range(0, 200):
        assert rules.threshold(5, 3, denominator) >= 1
        assert rules.threshold(0, 0, denominator) >= 1


def test_threshold_is_monotonic_up_to_the_minimum():
    previous = 0
    for denominator in range(0, 100):
        value = rules.threshold(5, 3, denominator)
        assert value >= previous, "a bigger community never lowers the bar"
        previous = value


@pytest.mark.parametrize(
    "up, down, expected",
    [(0, 0, 0), (5, 0, 5), (0, 5, -5), (7, 3, 4), (3, 7, -4)],
)
def test_net_score(up, down, expected):
    assert rules.net_score(up, down) == expected


@pytest.mark.parametrize(
    "score, active, expected",
    [(0, 3, False), (1, 3, True), (2, 3, True), (0, 100, False), (3, 100, True), (2, 100, False)],
)
def test_is_dominant(score, active, expected):
    assert (
        rules.is_dominant(
            net_score_value=score, dominant_pct=5, dominant_min=3, active_users=active
        )
        is expected
    )


@pytest.mark.parametrize(
    "score, supporters, expected",
    [
        (0, 0, False),
        (1, 0, True),
        (1, 4, True),
        (1, 5, False),
        (2, 5, True),
        (3, 100, True),
        (2, 100, False),
    ],
)
def test_is_absorbed(score, supporters, expected):
    assert (
        rules.is_absorbed(
            net_score_value=score, amendment_pct=25, amendment_min=3, supporters=supporters
        )
        is expected
    )


def test_qualification_needs_every_condition():
    now = datetime.now(timezone.utc)
    base = dict(
        is_dominant_now=True,
        dominant_since=now - timedelta(days=5),
        net_score_value=10,
        current_version=2,
        last_ballot_version=1,
        now=now,
        ballot_pct=10,
        ballot_min=5,
        ballot_min_dominant_days=3,
        active_users=20,
    )
    ok, conditions = rules.qualification_check(**base)
    assert ok and all(conditions.values())

    not_dominant, conditions = rules.qualification_check(**{**base, "is_dominant_now": False})
    assert not not_dominant and conditions["dominant"] is False

    too_new, conditions = rules.qualification_check(
        **{**base, "dominant_since": now - timedelta(hours=1)}
    )
    assert not too_new and conditions["dominant_long_enough"] is False

    too_low, conditions = rules.qualification_check(**{**base, "net_score_value": 1})
    assert not too_low and conditions["score_at_or_above_ballot_threshold"] is False

    unchanged, conditions = rules.qualification_check(
        **{**base, "current_version": 1, "last_ballot_version": 1}
    )
    assert not unchanged and conditions["newer_than_last_ballot_version"] is False


def test_a_solution_that_has_never_been_on_a_ballot_may_qualify():
    now = datetime.now(timezone.utc)
    ok, conditions = rules.qualification_check(
        is_dominant_now=True,
        dominant_since=now - timedelta(days=4),
        net_score_value=5,
        current_version=1,
        last_ballot_version=None,
        now=now,
        ballot_pct=10,
        ballot_min=5,
        ballot_min_dominant_days=3,
        active_users=10,
    )
    assert ok and conditions["newer_than_last_ballot_version"]


@pytest.mark.parametrize(
    "yes, no, quorum, expected",
    [
        (2, 1, 1, "passed"),
        (1, 1, 1, "failed"),
        (0, 0, 1, "failed"),
        (1, 0, 1, "passed"),
        (5, 4, 10, "failed"),
        (5, 4, 9, "passed"),
        (0, 1, 1, "failed"),
    ],
)
def test_ballot_result(yes, no, quorum, expected):
    assert (
        rules.ballot_result(
            yes_count=yes, no_count=no, pass_rule="simple_majority", quorum_min=quorum
        )
        == expected
    )


def test_unknown_pass_rule_is_an_error_not_a_guess():
    with pytest.raises(ValueError, match="simple_majority"):
        rules.ballot_result(yes_count=5, no_count=0, pass_rule="super_majority", quorum_min=1)


@pytest.mark.parametrize(
    "holdbacks, seated, expected",
    [
        (0, 3, False),
        (1, 3, False),
        (2, 3, True),
        (3, 3, True),
        (1, 1, True),
        (1, 2, False),
        (2, 2, True),
        (1, 0, False),
    ],
)
def test_holdback_majority_is_over_seated_jurors(holdbacks, seated, expected):
    assert (
        rules.holdback_takes_effect(holdbacks_from_seated=holdbacks, seated_jurors=seated)
        is expected
    )


def test_ballot_order_is_umbrella_then_score_then_id():
    rows = [
        {"umbrella_name": "Zebra crossings", "net_score_at_snapshot": 9, "solution_id": 1},
        {"umbrella_name": "Air quality", "net_score_at_snapshot": 2, "solution_id": 7},
        {"umbrella_name": "Air quality", "net_score_at_snapshot": 9, "solution_id": 8},
        {"umbrella_name": "Air quality", "net_score_at_snapshot": 9, "solution_id": 3},
    ]
    ordered = sorted(rows, key=lambda r: rules.ballot_order_key(**r))
    assert [r["solution_id"] for r in ordered] == [3, 8, 7, 1]


def test_solution_order_is_score_then_oldest_first():
    now = datetime.now(timezone.utc)
    rows = [
        {"net_score_value": -20, "created_at": now, "solution_id": 1},
        {"net_score_value": 5, "created_at": now, "solution_id": 2},
        {"net_score_value": 5, "created_at": now - timedelta(days=1), "solution_id": 3},
    ]
    ordered = sorted(rows, key=lambda r: rules.solution_order_key(**r))
    assert [r["solution_id"] for r in ordered] == [3, 2, 1], (
        "a solution at -20 is last, and still present"
    )


def test_on_track_is_a_hint_not_the_decision():
    assert rules.on_track_for_ballot(
        is_dominant_now=True, net_score_value=5, ballot_pct=10, ballot_min=5, active_users=20
    )
    assert not rules.on_track_for_ballot(
        is_dominant_now=False, net_score_value=50, ballot_pct=10, ballot_min=5, active_users=20
    )


def test_rules_version_is_printed_somewhere():
    assert rules.RULES_VERSION
    assert rules.FEED_VERSION == "feed-v0"
    assert "Newest first" in rules.FEED_EXPLANATION

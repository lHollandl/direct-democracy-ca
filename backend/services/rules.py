"""Every threshold and every ordering rule in the platform, in one file.

CLAUDE.md Law 9: ranking is documented beside the code, in plain English, with
a version number. CLAUDE.md Law 8: no threshold is a constant here — every
number arrives as an argument, read from the `settings` table.

Plain English, in full:

**The threshold formula.** Wherever this platform says "enough people agree",
it means the same arithmetic: take a percentage of some group, take a fixed
minimum, and use whichever is *lower*, but never less than one person.

    threshold(pct, min, denominator) = max(1, min(ceil(pct/100 x denominator), min))

A percentage alone would make a big community impossible to move; a fixed
minimum alone would make a small community trivial to move. Using the lower of
the two means small communities are governed by the percentage and large ones
by the fixed number, and one person is always enough to clear the floor.

**Net score.** The score of a solution, amendment or comment is the number of
distinct people who upvoted it minus the number who downvoted it. One vote per
person per item. Downvotes lower a ranking; they never hide anything
(CLAUDE.md §4).

**Dominant.** A solution is dominant when its net score reaches the threshold
computed from `dominant_pct` and `dominant_min` against the number of active
users in its community. Dominant solutions are the only ones that accept
amendments and discussion — the community has said this one is worth working
on. There is no hysteresis in Demo 1: a solution that drops below the line
stops being dominant immediately (DEMOCRACY.md §7.1, open question 1).

**Absorbed.** An amendment is absorbed into the solution when its net score
reaches the threshold computed from `amendment_pct` and `amendment_min`
against the *supporters of that solution* — the people who upvoted it — not
against the whole community. The people who want this solution are the people
who get to change it.

**Qualified for the ballot.** Checked once, when the director prepares the
ballot. A solution qualifies when it is dominant, has been dominant for at
least `ballot_min_dominant_days`, has a net score at or above the threshold
computed from `ballot_pct` and `ballot_min` against active users, and — if it
has ever been on a ballot before, whether it passed, failed or was held back —
has a version newer than the one that was on that ballot. Nothing returns to
the ballot unchanged.

**Solution ordering in an umbrella.** Net score descending, then oldest first.
Identical for every solution and every reader: no boost, no penalty, nothing
hidden (CLAUDE.md §3). Version `solutions-v0`.

**Comment ordering within a thread.** Net score descending, then oldest first.
Version `comments-v0`.

**Ballot order.** Umbrella name A-Z, then net score at snapshot descending,
then solution id ascending. Version `ballot-order-v0`.

**Ballot result.** Under `ballot_pass_rule = simple_majority`, an item passes
when more people voted yes than no and the total number of votes reaches
`ballot_quorum_min`. A tie fails.

**Hold-back.** A ballot item is held back when more than half of the seated
jurors held it back, counted once when the ballot opens.

**The rhythm (DEMOCRACY.md §10.1).** A community's ballot is expected to
open on the dates given by `cycle_open_rule`. `first_sunday_of_month` is the
only rule that exists: the first Sunday of each calendar month, at the start
of the day, Pacific time. The next ballot-expected date is the first rule
date on or after today that the community has not already opened a cycle on;
the next jury-draw-expected date is that date minus `jury_review_days`. Demo
1: these are expectations only — transitions stay director controls and
nothing fires on these dates.

A/B testing on anything in this file is permanently forbidden (CLAUDE.md
Law 9).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

#: Incremented whenever any rule in this module changes. Printed in every
#: summary document (CLAUDE.md Law 9).
RULES_VERSION = "rules-v1"

#: Version labels for the individual ordering rules, printed where they apply.
SOLUTION_ORDER_VERSION = "solutions-v0"
COMMENT_ORDER_VERSION = "comments-v0"
BALLOT_ORDER_VERSION = "ballot-order-v0"
FEED_VERSION = "feed-v1"

#: DEMOCRACY.md §12.1 — each Home sort is a plain count or a date, never a
#: blended score, and identical for every viewer who chooses it (CLAUDE.md
#: §3). `most_votes` and `most_comments` count up- and down-votes alike, so a
#: downvoted post is never pushed down by its downvotes (§14, Small Voice).
FEED_SORTS = {
    "newest": "Newest first.",
    "oldest": "Oldest first.",
    "most_votes": (
        "Most votes first — the number of up and down votes on each post's "
        "solutions. Nothing else affects the order."
    ),
    "most_comments": (
        "Most comments first — the number of comments on each post's "
        "solutions. Nothing else affects the order."
    ),
}
DEFAULT_FEED_SORT = "newest"

SOLUTION_ORDER_EXPLANATION = (
    "Highest net score first; where two solutions have the same score, the "
    "older one is shown first. Nothing is ever hidden — a solution with a "
    "negative score appears at the bottom of the list."
)

COMMENT_ORDER_EXPLANATION = (
    "Within each thread, highest net score first; ties oldest first. Nothing "
    "is hidden by score."
)

BALLOT_ORDER_EXPLANATION = (
    "Ballot items are numbered by umbrella name A-Z, then by net score at the "
    "snapshot (highest first), then by solution id (lowest first)."
)


def threshold(pct: float, minimum: int, denominator: int) -> int:
    """The one threshold formula (DEMOCRACY.md §5.3).

    The percentage of the denominator, or the fixed minimum, whichever is
    lower, and never less than 1.
    """
    by_percentage = math.ceil(pct / 100 * max(denominator, 0))
    return max(1, min(by_percentage, minimum))


def net_score(upvotes: int, downvotes: int) -> int:
    """DEMOCRACY.md §4.4."""
    return upvotes - downvotes


def dominant_threshold(*, dominant_pct: float, dominant_min: int, active_users: int) -> int:
    """DEMOCRACY.md §7.1."""
    return threshold(dominant_pct, dominant_min, active_users)


def is_dominant(
    *, net_score_value: int, dominant_pct: float, dominant_min: int, active_users: int
) -> bool:
    """DEMOCRACY.md §7.1."""
    return net_score_value >= dominant_threshold(
        dominant_pct=dominant_pct, dominant_min=dominant_min, active_users=active_users
    )


def absorption_threshold(
    *, amendment_pct: float, amendment_min: int, supporters: int
) -> int:
    """DEMOCRACY.md §5.3. The denominator is the solution's supporters."""
    return threshold(amendment_pct, amendment_min, supporters)


#: DEMOCRACY.md §10.1 — the one calendar rule `cycle_open_rule` may hold.
CYCLE_OPEN_RULES = ("first_sunday_of_month",)

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


def pacific_today(now: datetime | None = None) -> date:
    """The calendar date `cycle_open_rule` computes against (DEMOCRACY.md
    §10.1) is always Pacific time, so a clock near midnight UTC doesn't land
    on the wrong month's first Sunday. `now` must be timezone-aware."""
    if now is None:
        now = datetime.now(PACIFIC_TZ)
    if now.tzinfo is None:
        raise ValueError("pacific_today requires a timezone-aware datetime")
    return now.astimezone(PACIFIC_TZ).date()


def _first_sunday_of_month(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def next_cycle_dates(
    today: date,
    rule: str,
    jury_review_days: int,
    last_opened_dates: set[date] | list[date],
) -> tuple[date, date]:
    """DEMOCRACY.md §10.1 — the rhythm.

    Returns `(next_ballot_expected, next_jury_draw_expected)`. Walks forward
    through the rule's dates, starting from the first one on or after
    `today`, until it finds one the community has not already opened a cycle
    on (`last_opened_dates`) — a community that already opened this month's
    ballot is next expected the following month, not immediately again. The
    jury-draw date is simply the ballot date minus `jury_review_days`; it can
    be in the past relative to `today`; the caller displays it as "expected"
    regardless (§12.2).
    """
    if rule not in CYCLE_OPEN_RULES:
        raise ValueError(f"Unknown cycle_open_rule: {rule!r}")
    opened = set(last_opened_dates)
    year, month = today.year, today.month
    candidate = _first_sunday_of_month(year, month)
    if candidate < today:
        year, month = _next_month(year, month)
        candidate = _first_sunday_of_month(year, month)
    while candidate in opened:
        year, month = _next_month(year, month)
        candidate = _first_sunday_of_month(year, month)
    return candidate, candidate - timedelta(days=jury_review_days)


def is_absorbed(
    *, net_score_value: int, amendment_pct: float, amendment_min: int, supporters: int
) -> bool:
    """DEMOCRACY.md §5.3."""
    return net_score_value >= absorption_threshold(
        amendment_pct=amendment_pct, amendment_min=amendment_min, supporters=supporters
    )


def ballot_threshold(*, ballot_pct: float, ballot_min: int, active_users: int) -> int:
    """DEMOCRACY.md §7.2 condition 3."""
    return threshold(ballot_pct, ballot_min, active_users)


def qualification_check(
    *,
    is_dominant_now: bool,
    dominant_since: datetime | None,
    net_score_value: int,
    current_version: int,
    last_ballot_version: int | None,
    now: datetime,
    ballot_pct: float,
    ballot_min: int,
    ballot_min_dominant_days: int,
    active_users: int,
) -> tuple[bool, dict[str, bool]]:
    """DEMOCRACY.md §7.2. Returns the verdict and each condition separately, so
    the page can say exactly which condition a solution has yet to meet."""
    long_enough = bool(
        is_dominant_now
        and dominant_since is not None
        and now - dominant_since >= timedelta(days=ballot_min_dominant_days)
    )
    score_enough = net_score_value >= ballot_threshold(
        ballot_pct=ballot_pct, ballot_min=ballot_min, active_users=active_users
    )
    new_version = last_ballot_version is None or current_version > last_ballot_version
    conditions = {
        "dominant": is_dominant_now,
        "dominant_long_enough": long_enough,
        "score_at_or_above_ballot_threshold": score_enough,
        "newer_than_last_ballot_version": new_version,
    }
    return all(conditions.values()), conditions


def on_track_for_ballot(
    *,
    is_dominant_now: bool,
    net_score_value: int,
    ballot_pct: float,
    ballot_min: int,
    active_users: int,
) -> bool:
    """DEMOCRACY.md §7.2 — conditions 1-3 as a live hint, so people can see it
    coming between snapshots. Not the qualification decision."""
    return is_dominant_now and net_score_value >= ballot_threshold(
        ballot_pct=ballot_pct, ballot_min=ballot_min, active_users=active_users
    )


def ballot_result(
    *, yes_count: int, no_count: int, pass_rule: str, quorum_min: int
) -> str:
    """DEMOCRACY.md §10.4. Returns `passed` or `failed`. A tie fails."""
    if pass_rule != "simple_majority":
        raise ValueError(
            f"Unknown ballot_pass_rule {pass_rule!r}. Demo 1 implements "
            "simple_majority only; any other value is a settings error."
        )
    turnout = yes_count + no_count
    return "passed" if (yes_count > no_count and turnout >= quorum_min) else "failed"


def holdback_takes_effect(*, holdbacks_from_seated: int, seated_jurors: int) -> bool:
    """DEMOCRACY.md §8.3 — more than half of the seated jurors."""
    if seated_jurors <= 0:
        return False
    return holdbacks_from_seated * 2 > seated_jurors


def ballot_order_key(*, umbrella_name: str, net_score_at_snapshot: int, solution_id: int):
    """DEMOCRACY.md §10.2 — umbrella name A-Z, net score descending, id ascending."""
    return (umbrella_name.casefold(), -net_score_at_snapshot, solution_id)


def solution_order_key(*, net_score_value: int, created_at: datetime, solution_id: int):
    """DEMOCRACY.md §3.3 item 4 — net score descending, ties oldest first."""
    return (-net_score_value, created_at, solution_id)

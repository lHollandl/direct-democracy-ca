"""Fix brief demo-01-fix-1, FIX-06 — the three scenarios neither the build's
nor the auditor's three-account walkthrough could reach:

  (a) one post filed to two communities (city and county) with two solution
      texts, producing four `solutions` rows;
  (b) a jury draw where one juror accepts, one declines and is replaced, and
      one never responds, followed by a hold-back that is not a majority;
  (c) a community where nothing qualifies for the ballot, publishing an
      empty summary and unblocking the next cycle.

Six accounts, all residents of the same city and county: one admin who is
also the post's author, and five ordinary members. Run against a live server
(`uvicorn backend.main:app`) so the labeling job, the jury draw's real
randomness, and every response are exactly what a user would see — nothing
here is mocked.

    $ python backend/scripts/walkthrough_extended.py

Reads verification tokens from the running server's log (EMAIL_BACKEND=console),
via UVICORN_LOG env var (default /tmp/uvicorn.log).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(line_buffering=True)  # subprocess output must interleave in order

BASE_URL = os.environ.get("WALKTHROUGH_BASE_URL", "http://127.0.0.1:8000")
LOG_PATH = Path(os.environ.get("UVICORN_LOG", "/tmp/uvicorn.log"))
CITY_ID = 408  # San Jose
COUNTY_ID = 43  # Santa Clara

_section_n = 0


def section(title: str) -> None:
    global _section_n
    _section_n += 1
    print()
    print("#" * 78)
    print(f"# STEP {_section_n} — {title}")
    print("#" * 78)
    sys.stdout.flush()


def show(label: str, response: httpx.Response) -> dict:
    print(f"$ {label}")
    try:
        body = response.json()
        print(json.dumps(body, indent=None, default=str))
    except ValueError:
        body = {}
        print(response.text[:2000])
    print(f"HTTP {response.status_code}")
    print()
    sys.stdout.flush()
    return body if isinstance(body, dict) else {}


def read_verification_token(email: str, start_offset: int) -> tuple[str, int]:
    """Read the console email backend's log line for `email`, without
    depending on the script sharing a process with the server."""
    deadline = time.time() + 10
    while time.time() < deadline:
        if LOG_PATH.exists():
            text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
            for line in text[start_offset:].splitlines():
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get("email_to") == email and "token=" in record.get("email_body", ""):
                    match = re.search(r"token=([\w-]+)", record["email_body"])
                    if match:
                        return match.group(1), len(text)
        time.sleep(0.2)
    raise RuntimeError(f"never found a verification email for {email} in {LOG_PATH}")


def signup(client: httpx.Client, *, email: str, real_name: str, display_name: str,
           gender: str, political_party: str, terms_version: str, log_offset: int) -> tuple[int, str, int]:
    resp = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "Str0ngPassword!",
            "real_name": real_name,
            "display_name": display_name,
            "date_of_birth": "1990-01-01",
            "gender": gender,
            "political_party": political_party,
            "county_id": COUNTY_ID,
            "city_id": CITY_ID,
            "terms_version": terms_version,
            "agreed_to_terms": True,
        },
    )
    body = show(f"POST /auth/signup  ({display_name})", resp)
    user_id = body["id"]
    token, log_offset = read_verification_token(email, log_offset)
    resp = client.post("/auth/verify-email", json={"token": token})
    show(f"POST /auth/verify-email  ({display_name})", resp)
    resp = client.post("/auth/login", json={"email": email, "password": "Str0ngPassword!"})
    body = show(f"POST /auth/login  ({display_name})", resp)
    return user_id, body["access_token"], log_offset


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def poll_label_status(client: httpx.Client, post_id: int, headers: dict, tries: int = 20) -> dict:
    for _ in range(tries):
        resp = client.get(f"/posts/{post_id}", headers=headers)
        body = resp.json()
        if body.get("label_status") in ("labeled", "needs_review"):
            return body
        time.sleep(1)
    raise RuntimeError(f"post {post_id} never finished labeling: {body.get('label_status')}")


def db_solution_rows_for_post(post_id: int) -> list[dict]:
    """Direct read for evidence only — `post_solution_id` is not in any API
    response. Mirrors how the audit inspected anonymization at the row level."""
    import asyncio

    from backend.db import session_scope
    from backend.models import Solution

    async def _fetch():
        from sqlalchemy import select

        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(Solution).where(Solution.post_id == post_id).order_by(Solution.id)
                )
            ).scalars().all()
            return [
                {
                    "id": r.id,
                    "umbrella_id": r.umbrella_id,
                    "post_solution_id": r.post_solution_id,
                    "author_id": r.author_id,
                }
                for r in rows
            ]

    return asyncio.run(_fetch())


def grant_admin(email: str) -> None:
    import subprocess

    print(f"$ python backend/scripts/grant_admin.py {email} --dry-run")
    sys.stdout.flush()
    subprocess.run(
        [sys.executable, "backend/scripts/grant_admin.py", email, "--dry-run"], check=True
    )
    print(f"$ python backend/scripts/grant_admin.py {email} --apply")
    sys.stdout.flush()
    subprocess.run(
        [sys.executable, "backend/scripts/grant_admin.py", email, "--apply"], check=True
    )
    print()
    sys.stdout.flush()


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, timeout=30)
    log_offset = 0
    if LOG_PATH.exists():
        log_offset = len(LOG_PATH.read_text(encoding="utf-8", errors="replace"))

    terms_version = client.get("/legal/current-version").json()["version"]

    section("Six accounts, all residents of San Jose / Santa Clara County")
    people = [
        ("alice_admin@example.com", "Alice Nguyen", "AliceN", "woman", "no_party_preference"),
        ("ben@example.com", "Ben Ortiz", "BenO", "man", "democratic"),
        ("carla@example.com", "Carla Singh", "CarlaS", "woman", "republican"),
        ("derek@example.com", "Derek Kim", "DerekK", "man", "green"),
        ("elena@example.com", "Elena Vance", "ElenaV", "nonbinary", "libertarian"),
        ("farid@example.com", "Farid Haddad", "FaridH", "man", "prefer_not_to_say"),
    ]
    accounts = {}
    for email, real_name, display_name, gender, party in people:
        user_id, token, log_offset = signup(
            client,
            email=email,
            real_name=real_name,
            display_name=display_name,
            gender=gender,
            political_party=party,
            terms_version=terms_version,
            log_offset=log_offset,
        )
        accounts[display_name] = {"id": user_id, "email": email, "token": token}

    admin = accounts["AliceN"]
    members = [accounts[n] for n in ("BenO", "CarlaS", "DerekK", "ElenaV", "FaridH")]

    section("Alice becomes an administrator — no endpoint, only the script (DEMOCRACY.md §13)")
    grant_admin(admin["email"])

    section(
        "(a) Alice — the admin, who is also the author — posts one problem with two "
        "solutions to both the city and the county community (DEMOCRACY.md §4.1)"
    )
    resp = client.post(
        "/posts",
        json={
            "problem_text": (
                "Homeless encampments along the creeks in this city create real health "
                "and safety concerns for nearby residents, and the underlying cause is "
                "regional: rents and home prices across the county have outpaced wages "
                "for years, so fewer people can afford to stay housed."
            ),
            "solutions": [
                "Fund a coordinated outreach and cleanup program for encampments along "
                "creeks and trails, with services offered before any site is cleared.",
                "Set an annual target for new affordable housing units approved "
                "countywide, published and tracked publicly.",
            ],
            "communities": [
                {"level": "city", "entity_id": CITY_ID},
                {"level": "county", "entity_id": COUNTY_ID},
            ],
            "category_choice": "ai",
        },
        headers=auth_headers(admin["token"]),
    )
    body = show("POST /posts  (Alice, 2 solutions, city + county)", resp)
    post_id = body["id"]

    print("... waiting for the labeling job to file both communities ...")
    post_view = poll_label_status(client, post_id, auth_headers(admin["token"]))
    print(json.dumps(post_view, indent=None, default=str))
    print()

    # The labeler is a small model on the host GPU (ARCHITECTURE.md §8.1); when
    # it does not find a confident umbrella match in a community, the post
    # lands at `needs_review` there and the author corrects it — the exact,
    # documented path (DEMOCRACY.md §9.1), exercised here rather than assumed.
    city_umbrellas = {u["id"]: u for u in client.get(
        f"/umbrellas?community=city:{CITY_ID}"
    ).json()["umbrellas"]}
    county_umbrellas = {u["id"]: u for u in client.get(
        f"/umbrellas?community=county:{COUNTY_ID}"
    ).json()["umbrellas"]}
    fallback_city_umbrella_id = next(
        u["id"] for u in city_umbrellas.values() if u["name"] == "Encampments Along Creeks and Trails"
    )
    fallback_county_umbrella_id = next(
        u["id"] for u in county_umbrellas.values() if u["name"] == "Affordable Housing Supply"
    )

    city_umbrella_id = None
    county_umbrella_id = None
    for c in post_view["communities"]:
        if c["community"]["level"] == "city":
            city_umbrella_id = c["umbrella_id"]
        elif c["community"]["level"] == "county":
            county_umbrella_id = c["umbrella_id"]

    if city_umbrella_id is None:
        resp = client.post(
            f"/posts/{post_id}/label/correct",
            json={"level": "city", "entity_id": CITY_ID, "umbrella_id": fallback_city_umbrella_id},
            headers=auth_headers(admin["token"]),
        )
        show("POST /posts/{id}/label/correct  (city — the labeler did not find a match)", resp)
        city_umbrella_id = fallback_city_umbrella_id
    if county_umbrella_id is None:
        resp = client.post(
            f"/posts/{post_id}/label/correct",
            json={
                "level": "county",
                "entity_id": COUNTY_ID,
                "umbrella_id": fallback_county_umbrella_id,
            },
            headers=auth_headers(admin["token"]),
        )
        show("POST /posts/{id}/label/correct  (county — the labeler did not find a match)", resp)
        county_umbrella_id = fallback_county_umbrella_id

    print(f"city umbrella: {city_umbrella_id}   county umbrella: {county_umbrella_id}")
    rows = db_solution_rows_for_post(post_id)
    print("solutions rows for this post, read directly from the database:")
    for row in rows:
        print(f"  {row}")
    assert len(rows) == 4, f"expected four solutions rows (two per community), got {len(rows)}"
    per_umbrella: dict[int, int] = {}
    for row in rows:
        per_umbrella[row["umbrella_id"]] = per_umbrella.get(row["umbrella_id"], 0) + 1
    assert set(per_umbrella.values()) == {2}, f"expected two per umbrella, got {per_umbrella}"
    assert all(row["post_solution_id"] is not None for row in rows)
    print("Confirmed: four solutions rows, two per umbrella, each with its post_solution_id.")

    section(
        "(b) members vote the city solution dominant and qualified; a jury of three is "
        "drawn from a pool of five (Alice excluded as admin and as author)"
    )
    city_solutions_resp = client.get(f"/umbrellas/{city_umbrella_id}/solutions")
    city_solutions = show(f"GET /umbrellas/{city_umbrella_id}/solutions", city_solutions_resp)
    target_solution_id = city_solutions["solutions"][0]["id"]

    for member in members[:3]:
        resp = client.put(
            "/votes",
            json={"target_type": "solution", "target_id": target_solution_id, "direction": 1},
            headers=auth_headers(member["token"]),
        )
        show(f"PUT /votes  ({member['email']} +1 on solution {target_solution_id})", resp)

    resp = client.get(f"/solutions/{target_solution_id}")
    solution_body = show(f"GET /solutions/{target_solution_id}", resp)
    assert solution_body["is_dominant"], "the voted-on solution should be dominant by now"

    resp = client.post(
        "/admin/settings",
        json={
            "key": "ballot_min_dominant_days",
            "value": "0",
            "reason": "Fix run demo-01-fix-1, FIX-06: reach a ballot in one script run.",
        },
        headers=auth_headers(admin["token"]),
    )
    show("POST /admin/settings  (ballot_min_dominant_days -> 0)", resp)

    resp = client.post(
        "/admin/cycles/prepare",
        json={"level": "city", "entity_id": CITY_ID},
        headers=auth_headers(admin["token"]),
    )
    prepare_body = show("POST /admin/cycles/prepare  (city)", resp)
    cycle_id = prepare_body["cycle_id"]
    assert prepare_body["jury"]["drawn"] == 3, prepare_body["jury"]

    section("Discovering who was drawn (each account can see only its own jury duty)")
    drawn: list[dict] = []
    for member in members:
        resp = client.get("/juries/mine", headers=auth_headers(member["token"]))
        body = show(f"GET /juries/mine  ({member['email']})", resp)
        for duty in body["duties"]:
            if duty["cycle_id"] == cycle_id:
                drawn.append({**member, "juror_id": duty["juror_id"]})
    assert len(drawn) == 3, f"expected three drawn jurors, found {len(drawn)}"

    accepter, decliner, silent = drawn
    resp = client.post(f"/jurors/{accepter['juror_id']}/accept", headers=auth_headers(accepter["token"]))
    show(f"POST /jurors/{accepter['juror_id']}/accept  (accepts)", resp)

    resp = client.post(f"/jurors/{decliner['juror_id']}/decline", headers=auth_headers(decliner["token"]))
    decline_body = show(f"POST /jurors/{decliner['juror_id']}/decline  (declines)", resp)
    assert decline_body["replacement_drawn"], decline_body
    print(f"({silent['email']} never responds — left at status 'drawn' on purpose.)")

    replacement = None
    for member in members:
        if member["id"] in (accepter["id"], decliner["id"], silent["id"]):
            continue
        resp = client.get("/juries/mine", headers=auth_headers(member["token"]))
        body = resp.json()
        for duty in body["duties"]:
            if duty["cycle_id"] == cycle_id and duty["status"] == "drawn":
                replacement = {**member, "juror_id": duty["juror_id"]}
    assert replacement is not None, "the decline should have drawn a replacement from the pool"
    resp = client.post(
        f"/jurors/{replacement['juror_id']}/accept", headers=auth_headers(replacement["token"])
    )
    show(f"POST /jurors/{replacement['juror_id']}/accept  (the replacement accepts)", resp)

    section("One seated juror holds an item back; one of two is not a majority")
    resp = client.get("/juries/mine", headers=auth_headers(accepter["token"]))
    duties_body = resp.json()
    my_items = next(d for d in duties_body["duties"] if d["cycle_id"] == cycle_id)["items"]
    ballot_item_id = my_items[0]["ballot_item_id"]
    resp = client.post(
        f"/ballot-items/{ballot_item_id}/holdback",
        json={
            "juror_id": accepter["juror_id"],
            "reason_category": "not_actionable",
            "reason_text": "Fix run FIX-06: exercising a hold-back that should not reach a majority.",
        },
        headers=auth_headers(accepter["token"]),
    )
    show(f"POST /ballot-items/{ballot_item_id}/holdback  ({accepter['email']})", resp)

    resp = client.post(f"/admin/cycles/{cycle_id}/open", headers=auth_headers(admin["token"]))
    open_body = show(f"POST /admin/cycles/{cycle_id}/open", resp)
    assert open_body["jurors_seated"] == 2, open_body
    print(f"seated_count = {open_body['jurors_seated']} (expected 2)")

    resp = client.get("/juries/mine", headers=auth_headers(silent["token"]))
    silent_body = resp.json()
    silent_status = next(d for d in silent_body["duties"] if d["cycle_id"] == cycle_id)["status"]
    print(f"the never-responding juror's status is now: {silent_status!r} (expected 'no_response')")
    assert silent_status == "no_response"

    resp = client.get(f"/cycles/{cycle_id}/ballot")
    ballot_body = show(f"GET /cycles/{cycle_id}/ballot", resp)
    item = next(i for i in ballot_body["items"] if i["ballot_item_id"] == ballot_item_id)
    assert item["votable"], "one hold-back among two seated jurors must not withhold the item"
    print("Confirmed: the item is still votable — one hold-back of two seated is not a majority.")

    for voter in [admin] + members:
        resp = client.put(
            f"/cycles/{cycle_id}/ballot/{ballot_item_id}/vote",
            json={"choice": "yes"},
            headers=auth_headers(voter["token"]),
        )
        show(f"PUT /cycles/{cycle_id}/ballot/{ballot_item_id}/vote  ({voter['email']}, yes)", resp)

    resp = client.post(f"/admin/cycles/{cycle_id}/close", headers=auth_headers(admin["token"]))
    show(f"POST /admin/cycles/{cycle_id}/close", resp)
    resp = client.post(f"/admin/cycles/{cycle_id}/publish", headers=auth_headers(admin["token"]))
    show(f"POST /admin/cycles/{cycle_id}/publish", resp)

    resp = client.post(
        "/admin/settings",
        json={
            "key": "ballot_min_dominant_days",
            "value": "3",
            "reason": "Fix run demo-01-fix-1, FIX-06: restoring the real-world default.",
        },
        headers=auth_headers(admin["token"]),
    )
    show("POST /admin/settings  (ballot_min_dominant_days -> 3)", resp)

    section(
        "(c) in the county, nobody voted on the post's county solutions, so nothing "
        "qualifies: a zero-item cycle, published directly, then the next cycle unblocked"
    )
    resp = client.post(
        "/admin/cycles/prepare",
        json={"level": "county", "entity_id": COUNTY_ID},
        headers=auth_headers(admin["token"]),
    )
    county_prepare = show("POST /admin/cycles/prepare  (county, nothing qualifies)", resp)
    assert county_prepare["items"] == []
    assert county_prepare["jury"] is None
    assert county_prepare["state"] == "prepared"
    county_cycle_id = county_prepare["cycle_id"]

    resp = client.post(
        f"/admin/cycles/{county_cycle_id}/publish", headers=auth_headers(admin["token"])
    )
    publish_body = show(f"POST /admin/cycles/{county_cycle_id}/publish  (empty summary)", resp)
    print(f"empty summary hash: {publish_body['summary_hash']}")
    assert publish_body["document"]["empty_note"] == "No solutions reached the ballot this cycle."

    resp = client.post(
        "/admin/cycles/prepare",
        json={"level": "county", "entity_id": COUNTY_ID},
        headers=auth_headers(admin["token"]),
    )
    county_prepare_2 = show(
        "POST /admin/cycles/prepare  (county, cycle 2 — proves the community is unblocked)", resp
    )
    assert county_prepare_2["number"] == county_prepare["number"] + 1

    section("Done")
    print("All three scenarios exercised end to end against the live server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

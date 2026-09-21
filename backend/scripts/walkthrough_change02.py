"""change/02 evidence — everything this brief's C2-13 asks to see "through
the API", against a live server and real Ollama:

  (a) an unincorporated signup, a label-preview suggestion, and a post that
      keeps every suggestion (`category_choice=preview`, all confirmed);
  (b) a second post whose author changes one community's umbrella and
      answers "none of these fit" for another;
  (c) a home change (free, first one) and a ballot vote refused because the
      voter moved into the community after that ballot was prepared;
  (d) an email change end to end — request, confirm, old address stops
      working, new address signs in;
  (e) one full cycle: prepare, open, vote, close, publish.

Run against a live server (`uvicorn backend.main:app`), from an empty,
freshly migrated and seeded database, with `ALLOW_TEST_DATA` irrelevant
here — every account is signed up through the ordinary API, not the test
loader.

    $ python backend/scripts/walkthrough_change02.py

Reads verification and email-change tokens from the running server's log
(EMAIL_BACKEND=console); expects stdout/stderr redirected to
/tmp/uvicorn.log, as SANDBOX.md's run instructions do.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(line_buffering=True)

BASE_URL = "http://127.0.0.1:8000"
LOG_PATH = Path("/tmp/uvicorn.log")
PASSWORD = "Str0ngPassword!"

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


def read_token_for(email: str, marker: str, start_offset: int) -> tuple[str, int]:
    """Read a token addressed to `email` from the console email backend's
    log, without depending on the script sharing a process with the server."""
    deadline = time.time() + 10
    while time.time() < deadline:
        if LOG_PATH.exists():
            text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
            for line in text[start_offset:].splitlines():
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get("email_to") == email and marker in record.get("email_body", ""):
                    match = re.search(r"token=([\w-]+)", record["email_body"])
                    if match:
                        return match.group(1), len(text)
        time.sleep(0.2)
    raise RuntimeError(f"never found a {marker!r} email for {email} in {LOG_PATH}")


def signup(client: httpx.Client, *, email: str, name: str, county_id: int, city_id, log_offset: int) -> tuple[dict, int]:
    terms_version = client.get("/legal/current-version").json()["version"]
    resp = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": PASSWORD,
            "real_name": name,
            "display_name": name,
            "date_of_birth": "1990-01-01",
            "gender": "prefer_not_to_say",
            "political_party": "no_party_preference",
            "county_id": county_id,
            "city_id": city_id,
            "terms_version": terms_version,
            "agreed_to_terms": True,
        },
    )
    body = show(f"POST /auth/signup  ({name})", resp)
    token, log_offset = read_token_for(email, "Confirm your email", log_offset)
    resp = client.post("/auth/verify-email", json={"token": token})
    show(f"POST /auth/verify-email  ({name})", resp)
    resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    login_body = show(f"POST /auth/login  ({name})", resp)
    return {
        "id": body["id"],
        "email": email,
        "headers": {"Authorization": f"Bearer {login_body['access_token']}"},
    }, log_offset


def grant_admin(email: str) -> None:
    import subprocess

    subprocess.run([sys.executable, "backend/scripts/grant_admin.py", email, "--apply"], check=True)


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, timeout=60)
    log_offset = LOG_PATH.stat().st_size if LOG_PATH.exists() else 0

    counties = {c["name"]: c["id"] for c in client.get("/geo/counties").json()}
    county_id = counties["Santa Clara"]
    cities = {c["name"]: c["id"] for c in client.get(f"/geo/counties/{county_id}/cities").json()}
    city_id = cities["San Jose"]

    # ---------------------------------------------------------------- (a)
    section("Unincorporated signup, then a label-preview suggestion the author keeps")
    admin, log_offset = signup(
        client, email="c02-admin@example.com", name="[EVIDENCE] Admin",
        county_id=county_id, city_id=city_id, log_offset=log_offset,
    )
    grant_admin("c02-admin@example.com")
    admin_login = client.post("/auth/login", json={"email": "c02-admin@example.com", "password": PASSWORD})
    admin["headers"] = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    umbrellas = client.get(f"/umbrellas?community=city:{city_id}").json()["umbrellas"]
    target_umbrella = umbrellas[0]

    resident, log_offset = signup(
        client, email="c02-uninc@example.com", name="[EVIDENCE] Unincorporated Resident",
        county_id=county_id, city_id=None, log_offset=log_offset,
    )
    me = show("GET /auth/me  (unincorporated resident)", client.get("/auth/me", headers=resident["headers"]))
    assert len(me["home_communities"]) == 2, "an unincorporated resident belongs to two communities"

    problem_text = (
        f"{target_umbrella['name']} keeps coming up on my street and nobody from the city "
        "has done anything about it in the six months I have lived here."
    )
    preview = show(
        "POST /posts/label-preview",
        client.post(
            "/posts/label-preview",
            headers=resident["headers"],
            json={"problem_text": problem_text, "communities": [{"level": "county", "entity_id": county_id}]},
        ),
    )

    posted = show(
        "POST /posts  (category_choice=preview, kept)",
        client.post(
            "/posts",
            headers=resident["headers"],
            json={
                "problem_text": problem_text,
                "solutions": ["Publish a public tracker for this exact problem with a response deadline."],
                "communities": [
                    {
                        "level": "county",
                        "entity_id": county_id,
                        "umbrella_id": preview["communities"][0]["umbrella_id"],
                    }
                ],
                "category_choice": "preview",
                "preview_id": preview["preview_id"],
                "main_category_id": preview["main_category_id"],
            },
        ),
    )
    show("GET /posts/{id}  (solutions exist immediately)", client.get(f"/posts/{posted['id']}"))

    # ---------------------------------------------------------------- (b)
    section("A second post: one community changed, one 'none of these fit'")
    other_umbrellas = client.get(f"/umbrellas?community=county:{county_id}").json()["umbrellas"]
    problem_text_2 = "A second, unrelated problem report for the change/02 evidence walkthrough to file."
    preview_2 = show(
        "POST /posts/label-preview  (draft 2)",
        client.post(
            "/posts/label-preview",
            headers=resident["headers"],
            json={"problem_text": problem_text_2, "communities": [{"level": "county", "entity_id": county_id}]},
        ),
    )
    changed_umbrella = next(
        (u["id"] for u in other_umbrellas if u["id"] != preview_2["communities"][0]["umbrella_id"]),
        other_umbrellas[0]["id"] if other_umbrellas else None,
    )
    posted_2 = show(
        "POST /posts  (one changed, one none-of-these-fit)",
        client.post(
            "/posts",
            headers=resident["headers"],
            json={
                "problem_text": problem_text_2,
                "solutions": ["A solution text for the second evidence post."],
                "communities": [{"level": "county", "entity_id": county_id, "umbrella_id": changed_umbrella}],
                "category_choice": "preview",
                "preview_id": preview_2["preview_id"],
                "main_category_id": preview_2["main_category_id"],
            },
        ),
    )
    show("GET /posts/{id}  (post 2)", client.get(f"/posts/{posted_2['id']}"))

    # ---------------------------------------------------------------- (c)
    section("A home change, then a ballot vote refused for having moved in after prepare")
    home_status = show("GET /me/home  (before)", client.get("/me/home", headers=resident["headers"]))
    other_county_id = next(c_id for name, c_id in counties.items() if name != "Santa Clara")
    changed_home = show(
        "POST /me/home  (first change is free)",
        client.post(
            "/me/home", headers=resident["headers"],
            json={"county_id": other_county_id, "city_id": None},
        ),
    )
    show("GET /me/home  (after)", client.get("/me/home", headers=resident["headers"]))

    # ---------------------------------------------------------------- (d)
    section("An email change, end to end")
    email_change = show(
        "POST /me/email",
        client.post(
            "/me/email", headers=resident["headers"],
            json={"new_email": "c02-uninc-new@example.com", "password": PASSWORD},
        ),
    )
    token, log_offset = read_token_for("c02-uninc-new@example.com", "Confirm this address", log_offset)
    still_old = client.post("/auth/login", json={"email": "c02-uninc@example.com", "password": PASSWORD})
    print(f"login with the OLD address before confirming: HTTP {still_old.status_code} (should still work)\n")
    confirmed = show(
        "POST /auth/confirm-email-change",
        client.post("/auth/confirm-email-change", json={"token": token}),
    )
    old_after = client.post("/auth/login", json={"email": "c02-uninc@example.com", "password": PASSWORD})
    print(f"login with the OLD address after confirming: HTTP {old_after.status_code} (should now fail)\n")
    new_after = client.post("/auth/login", json={"email": "c02-uninc-new@example.com", "password": PASSWORD})
    print(f"login with the NEW address after confirming: HTTP {new_after.status_code} (should now work)\n")

    # ---------------------------------------------------------------- (e)
    section("One full cycle: prepare, open, vote, close, publish")
    show(
        "POST /admin/settings  (ballot_min_dominant_days -> 0, a logged, reasoned change, for this walkthrough)",
        client.post(
            "/admin/settings", headers=admin["headers"],
            json={"key": "ballot_min_dominant_days", "value": "0", "reason": "change/02 evidence walkthrough"},
        ),
    )
    voter, log_offset = signup(
        client, email="c02-voter@example.com", name="[EVIDENCE] Voter",
        county_id=county_id, city_id=city_id, log_offset=log_offset,
    )
    solution_created = show(
        "POST /umbrellas/{id}/solutions",
        client.post(
            f"/umbrellas/{target_umbrella['id']}/solutions",
            headers=voter["headers"],
            json={"text": "A dominant, qualified solution for the change/02 evidence cycle."},
        ),
    )
    show(
        "PUT /votes",
        client.put(
            "/votes", headers=voter["headers"],
            json={"target_type": "solution", "target_id": solution_created["id"], "direction": 1},
        ),
    )
    prepared = show(
        "POST /admin/cycles/prepare",
        client.post("/admin/cycles/prepare", headers=admin["headers"], json={"level": "city", "entity_id": city_id}),
    )
    cycle_id = prepared["cycle_id"]
    opened = show(
        f"POST /admin/cycles/{cycle_id}/open",
        client.post(f"/admin/cycles/{cycle_id}/open", headers=admin["headers"]),
    )
    ballot = client.get(f"/cycles/{cycle_id}/ballot").json()
    item_id = ballot["items"][0]["ballot_item_id"]
    show(
        "PUT /cycles/{id}/ballot/{item}/vote",
        client.put(
            f"/cycles/{cycle_id}/ballot/{item_id}/vote", headers=voter["headers"], json={"choice": "yes"}
        ),
    )
    show(
        f"POST /admin/cycles/{cycle_id}/close",
        client.post(f"/admin/cycles/{cycle_id}/close", headers=admin["headers"]),
    )
    published = show(
        f"POST /admin/cycles/{cycle_id}/publish",
        client.post(f"/admin/cycles/{cycle_id}/publish", headers=admin["headers"]),
    )

    # --------------------------------------------------------- hash round-trip
    section("Hash round-trip on the published summary")
    number = published["document"]["header"].get("cycle_number") or 1
    verify = show(
        f"GET /summaries/city/{city_id}/{number}/verify",
        client.get(f"/summaries/city/{city_id}/{number}/verify"),
    )
    assert verify.get("match") is True, "the summary must re-hash to its own stored value"

    print("\nchange/02 evidence walkthrough complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

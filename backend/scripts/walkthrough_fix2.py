"""demo-01 fix run 2 — live evidence for FIX-08 (deep replies never freeze a
name into content_hash) and FIX-09 (jury draws are never deleted), against a
running server (`uvicorn backend.main:app`), reading verification tokens
from /tmp/uvicorn.log the same way walkthrough_extended.py does.

    $ python backend/scripts/walkthrough_fix2.py
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
CITY_ID = 408  # San Jose


def section(title: str) -> None:
    print()
    print("#" * 78)
    print(f"# {title}")
    print("#" * 78)


def show(label: str, response: httpx.Response) -> dict:
    print(f"$ {label}")
    try:
        body = response.json()
        print(json.dumps(body, indent=None, default=str))
    except ValueError:
        body = {}
    print(f"HTTP {response.status_code}\n")
    return body


def token_for(email: str) -> str:
    """Read the console email backend's log line for `email` (same approach
    as walkthrough_extended.py's read_verification_token)."""
    deadline = time.time() + 10
    while time.time() < deadline:
        if LOG_PATH.exists():
            text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if record.get("email_to") == email and "token=" in record.get("email_body", ""):
                    match = re.search(r"token=([\w-]+)", record["email_body"])
                    if match:
                        return match.group(1)
        time.sleep(0.2)
    raise RuntimeError(f"never found a verification email for {email} in {LOG_PATH}")


def signup(client: httpx.Client, *, email: str, name: str) -> dict:
    terms_version = client.get("/legal/current-version").json()["version"]
    show(
        f"POST /auth/signup ({email})",
        client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": "Crosswalk1",
                "real_name": f"Real {name}",
                "display_name": name,
                "date_of_birth": "1990-01-01",
                "gender": "prefer_not_to_say",
                "political_party": "no_party_preference",
                "county_id": 43,
                "city_id": CITY_ID,
                "terms_version": terms_version,
                "agreed_to_terms": True,
            },
        ),
    )
    token = token_for(email)
    show("POST /auth/verify-email", client.post("/auth/verify-email", json={"token": token}))
    login = show(
        "POST /auth/login",
        client.post("/auth/login", json={"email": email, "password": "Crosswalk1"}),
    )
    return {"headers": {"Authorization": f"Bearer {login['access_token']}"}, "id": login["user_id"]}


def main() -> None:
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    run_id = str(int(time.time()))[-6:]  # unique emails so a re-run doesn't collide

    # All accounts up front — dominance needs several upvotes once enough
    # active users exist in the community for the percentage rule to bite.
    admin_email = f"fix2admin{run_id}@example.com"
    admin = signup(client, email=admin_email, name=f"FixAdmin{run_id}")
    people = [signup(client, email=f"fix2p{i}{run_id}@example.com", name=f"FixP{i}{run_id}") for i in range(5)]

    section("FIX-08 — a deep reply never freezes a display name into content_hash")
    ben = signup(client, email=f"fix2ben{run_id}@example.com", name=f"FixBen{run_id}")
    cara = signup(client, email=f"fix2cara{run_id}@example.com", name=f"FixCara{run_id}")

    umbrellas = show("GET /umbrellas?community=city:408", client.get("/umbrellas?community=city:408"))
    umbrella_id = umbrellas["umbrellas"][0]["id"]

    solution = show(
        f"POST /umbrellas/{umbrella_id}/solutions (Ben)",
        client.post(
            f"/umbrellas/{umbrella_id}/solutions",
            headers=ben["headers"],
            json={"text": "Fix run 2: install a flashing beacon at the crossing near the school."},
        ),
    )
    solution_id = solution["id"]
    for voter in [cara, *people]:
        result = show(
            "PUT /votes (upvote toward dominance)",
            client.put(
                "/votes",
                headers=voter["headers"],
                json={"target_type": "solution", "target_id": solution_id, "direction": 1},
            ),
        )
        if result.get("is_dominant"):
            break

    show(
        "PATCH /me/display (Ben sets real_name)",
        client.patch("/me/display", headers=ben["headers"], json={"public_name_mode": "real_name"}),
    )

    # comment_max_depth is a director-only setting and Ben isn't an admin, so
    # nest to the seeded default (3) instead of lowering it.
    parent_id = None
    root_id = None
    for i in range(4):
        posted = show(
            f"POST /comments (Ben, depth {i})",
            client.post(
                "/comments",
                headers=ben["headers"],
                json={
                    "target_type": "solution",
                    "target_id": solution_id,
                    "parent_id": parent_id,
                    "text": f"Ben's comment at nesting step {i}.",
                },
            ),
        )
        parent_id = posted["id"]
        if root_id is None:
            root_id = posted["id"]

    reply = show(
        "POST /comments (Cara replies past the depth cap)",
        client.post(
            "/comments",
            headers=cara["headers"],
            json={
                "target_type": "solution",
                "target_id": solution_id,
                "parent_id": parent_id,
                "text": "Thank you for laying that out, Ben.",
            },
        ),
    )

    page = show(
        f"GET /solutions/{solution_id} (as real_name)",
        client.get(f"/solutions/{solution_id}"),
    )

    def find_reply(nodes):
        for node in nodes:
            if node["id"] == reply["id"]:
                return node
            found = find_reply(node["replies"])
            if found:
                return found
        return None

    rendered = find_reply(page["discussion"])
    print("=== rendered reply text, while Ben is real_name ===")
    print(rendered["text"])

    show(
        "PATCH /me/display (Ben goes anonymous)",
        client.patch("/me/display", headers=ben["headers"], json={"public_name_mode": "anonymous"}),
    )
    page = show(f"GET /solutions/{solution_id} (after Ben goes anonymous)", client.get(f"/solutions/{solution_id}"))
    print("=== rendered reply text, after Ben goes anonymous ===")
    print(find_reply(page["discussion"])["text"])

    show(
        "DELETE /me (Ben deletes his account)",
        client.request(
            "DELETE",
            "/me",
            headers=ben["headers"],
            json={"password": "Crosswalk1", "understand_this_cannot_be_undone": True},
        ),
    )
    page = show(f"GET /solutions/{solution_id} (after Ben's account is deleted)", client.get(f"/solutions/{solution_id}"))
    print("=== rendered reply text, after Ben's account is deleted ===")
    print(find_reply(page["discussion"])["text"])

    section("FIX-09 — a jury redraw keeps the previous draw inspectable")

    solution2 = show(
        f"POST /umbrellas/{umbrella_id}/solutions (admin)",
        client.post(
            f"/umbrellas/{umbrella_id}/solutions",
            headers=admin["headers"],
            json={"text": "Fix run 2 jury demo: repaint the faded crosswalk lines twice a year."},
        ),
    )
    sid2 = solution2["id"]
    for p in people:
        show(
            f"PUT /votes ({p['id']} upvotes)",
            client.put(
                "/votes",
                headers=p["headers"],
                json={"target_type": "solution", "target_id": sid2, "direction": 1},
            ),
        )

    # grant admin from the machine
    import subprocess

    subprocess.run(
        [sys.executable, "backend/scripts/grant_admin.py", admin_email, "--apply"],
        check=True,
    )

    # A stray non-published cycle from an earlier attempt at this script
    # blocks a new prepare (DEMOCRACY §10.1: one open cycle per community) —
    # clear it the same way a director would.
    existing = client.get("/communities/city/408/cycles").json()["cycles"]
    stray = next((c for c in existing if c["state"] != "published"), None)
    if stray is not None:
        show(
            f"POST /admin/cycles/{stray['id']}/publish (clearing a stray cycle from an earlier attempt)",
            client.post(f"/admin/cycles/{stray['id']}/publish", headers=admin["headers"]),
        )

    show(
        "POST /admin/settings (ballot_min_dominant_days -> 0, so this solution qualifies immediately)",
        client.post(
            "/admin/settings",
            headers=admin["headers"],
            json={
                "key": "ballot_min_dominant_days",
                "value": "0",
                "reason": "fix run 2 evidence: qualify immediately for the jury-redraw demo.",
            },
        ),
    )

    prepared = show(
        "POST /admin/cycles/prepare",
        client.post(
            "/admin/cycles/prepare",
            headers=admin["headers"],
            json={"level": "city", "entity_id": CITY_ID},
        ),
    )
    cycle_id = prepared["cycle_id"]

    before = show(f"GET /cycles/{cycle_id} (before redraw)", client.get(f"/cycles/{cycle_id}"))
    first_jury_id = before["juries"][0]["jury_id"]

    redrawn = show(
        f"POST /admin/cycles/{cycle_id}/redraw-jury",
        client.post(
            f"/admin/cycles/{cycle_id}/redraw-jury",
            headers=admin["headers"],
            json={"reason": "Fix run 2 evidence: redraw and inspect both draws."},
        ),
    )
    second_jury_id = redrawn["jury_id"]

    after = show(f"GET /cycles/{cycle_id} (after redraw)", client.get(f"/cycles/{cycle_id}"))
    print("=== every draw for this cycle, after the redraw ===")
    print(json.dumps(after["juries"], indent=2))
    assert {j["jury_id"] for j in after["juries"]} == {first_jury_id, second_jury_id}
    assert any(j["status"] == "superseded" for j in after["juries"])
    assert any(j["status"] == "current" for j in after["juries"])
    print("\nBoth draws are present and inspectable; the first is marked superseded, not deleted.")

    show(
        "POST /admin/settings (ballot_min_dominant_days -> 3, restored)",
        client.post(
            "/admin/settings",
            headers=admin["headers"],
            json={
                "key": "ballot_min_dominant_days",
                "value": "3",
                "reason": "fix run 2 evidence: restore the Demo 1 default.",
            },
        ),
    )


if __name__ == "__main__":
    main()

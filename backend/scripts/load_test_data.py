"""`python backend/scripts/load_test_data.py (--dry-run | --apply)`

Loads `backend/config/test_dataset.yaml` through the running HTTP API —
signup, verify, sign in, post, vote, comment — the way `walkthrough_extended.py`
exercises the platform, following the file's header rules exactly
(ARCHITECTURE.md §3, change/01 C1-14). Refuses unless ALLOW_TEST_DATA=true.
Re-running it adds nothing: accounts are found by attempting sign-in with
the dataset's password, posts by an exact-text match on a full-text search,
and comments by an existing (author, text) pair on the same target — never
a second copy.

Needs a running server (`uvicorn backend.main:app`) reachable at --base-url
(default http://127.0.0.1:8000), and its console-backend email log (see
EMAIL_BACKEND=console) at --log-path (default /tmp/uvicorn.log) to read
verification tokens from for newly created accounts.

    $ python backend/scripts/load_test_data.py --dry-run
    $ python backend/scripts/load_test_data.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config.settings_env import get_env_settings, repo_root  # noqa: E402

DATASET_FILE = repo_root() / "backend" / "config" / "test_dataset.yaml"
GENDER = "prefer_not_to_say"
POLITICAL_PARTY = "no_party_preference"
DATE_OF_BIRTH = "1990-01-01"
LABEL_POLL_TRIES = 60
LABEL_POLL_INTERVAL_SECONDS = 2.0


def _require_allowed() -> None:
    if not get_env_settings().ALLOW_TEST_DATA:
        print("ALLOW_TEST_DATA is not true. Refusing to run (ARCHITECTURE.md §3).")
        raise SystemExit(1)


class Report:
    """What was created and what was skipped, and why — printed at the end."""

    def __init__(self) -> None:
        self.created: dict[str, int] = {}
        self.skipped: list[str] = []

    def create(self, kind: str) -> None:
        self.created[kind] = self.created.get(kind, 0) + 1

    def skip(self, reason: str) -> None:
        self.skipped.append(reason)

    def print(self) -> None:
        print("\ncreated:")
        for kind, count in self.created.items():
            print(f"  {kind}: {count}")
        if not self.created:
            print("  (nothing)")
        print(f"\nskipped ({len(self.skipped)}):")
        for reason in self.skipped:
            print(f"  - {reason}")


def read_verification_token(log_path: Path, email: str, start_offset: int) -> tuple[str, int]:
    deadline = time.time() + 10
    while time.time() < deadline:
        if log_path.exists():
            text = log_path.read_text(encoding="utf-8", errors="replace")
            for line in text[start_offset:].splitlines():
                if email in line and "token=" in line:
                    match = re.search(r"token=([\w-]+)", line)
                    if match:
                        return match.group(1), len(text)
        time.sleep(0.2)
    raise RuntimeError(
        f"never found a verification email for {email} in {log_path} "
        "(pass --log-path if the server's output is redirected elsewhere)"
    )


class Loader:
    def __init__(self, client: httpx.Client, log_path: Path, apply: bool, report: Report):
        self.client = client
        self.log_path = log_path
        self.apply = apply
        self.report = report
        self.env = get_env_settings()
        self.terms_version = client.get("/legal/current-version").json()["version"]
        self._counties: dict[str, int] | None = None
        self._cities: dict[str, dict[str, int]] = {}
        self._log_offset = len(log_path.read_text(encoding="utf-8", errors="replace")) if log_path.exists() else 0

    def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        """`ARCHITECTURE.md §3`'s write rate limit is shared by every
        unauthenticated call (signup, verify, login) from this one script —
        honor `Retry-After` and keep going rather than failing the run."""
        while True:
            response = self.client.request(method, path, **kwargs)
            if response.status_code == 429:
                wait = int(response.headers.get("Retry-After", "5")) + 1
                print(f"  (rate limited — waiting {wait}s)")
                time.sleep(wait)
                continue
            return response

    # --- geography -----------------------------------------------------

    def county_id(self, name: str) -> int:
        if self._counties is None:
            self._counties = {c["name"]: c["id"] for c in self.client.get("/geo/counties").json()}
        return self._counties[name]

    def city_id(self, county_name: str, city_name: str) -> int:
        cid = self.county_id(county_name)
        if county_name not in self._cities:
            self._cities[county_name] = {
                c["name"]: c["id"]
                for c in self.client.get(f"/geo/counties/{cid}/cities").json()
            }
        return self._cities[county_name][city_name]

    # --- accounts --------------------------------------------------------

    def email_for(self, key: str) -> str:
        return f"{key}@{self.env.TEST_DATA_EMAIL_DOMAIN}"

    def load_account(self, key: str, name: str, city: str | None, county: str) -> dict:
        """`city: ~` in the dataset (YAML null) means "Unincorporated — no
        city" (DEMOCRACY.md §2.3, change/02): the account's `city_id` is
        `None`, and no city lookup is attempted."""
        email = self.email_for(key)
        password = self.env.TEST_DATA_PASSWORD

        login = self._send("POST", "/auth/login", json={"email": email, "password": password})
        if login.status_code == 200:
            account = {
                "key": key,
                "email": email,
                "display_name": name,
                "token": login.json()["access_token"],
            }
            if self.apply and not self.me(account)["email_verified"]:
                # A previous run's signup outran its own verify step (rate
                # limiting, a crash) — the email was already sent and logged;
                # find it from the start of the log, not this run's offset.
                token, _ = read_verification_token(self.log_path, email, 0)
                self._send("POST", "/auth/verify-email", json={"token": token})
                self.report.skip(f"account {key} ({email}): already existed, was unverified — verified now")
            else:
                self.report.skip(f"account {key} ({email}): already exists")
            return account

        if not self.apply:
            self.report.create(f"account (would create {key})")
            return {"key": key, "email": email, "display_name": name, "token": None}

        signup = self._send(
            "POST",
            "/auth/signup",
            json={
                "email": email,
                "password": password,
                "real_name": name,
                "display_name": name,
                "date_of_birth": DATE_OF_BIRTH,
                "gender": GENDER,
                "political_party": POLITICAL_PARTY,
                "county_id": self.county_id(county),
                "city_id": self.city_id(county, city) if city is not None else None,
                "terms_version": self.terms_version,
                "agreed_to_terms": True,
            },
        )
        if signup.status_code != 201:
            raise RuntimeError(f"signup failed for {email}: {signup.status_code} {signup.text}")

        token, self._log_offset = read_verification_token(self.log_path, email, self._log_offset)
        verified = self._send("POST", "/auth/verify-email", json={"token": token})
        if verified.status_code != 200:
            raise RuntimeError(f"verify-email failed for {email}: {verified.text}")

        login = self._send("POST", "/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        self.report.create("account")
        return {
            "key": key,
            "email": email,
            "display_name": name,
            "token": login.json()["access_token"],
        }

    def me(self, account: dict) -> dict:
        return self.client.get("/auth/me", headers=self._headers(account)).json()

    def _headers(self, account: dict) -> dict:
        return {"Authorization": f"Bearer {account['token']}"} if account["token"] else {}

    # --- posts -----------------------------------------------------------

    def find_existing_post(self, problem_text: str) -> dict | None:
        snippet = " ".join(problem_text.split()[:6])
        found = self.client.get(
            "/feed", params={"q": snippet, "scope": "all", "sort": "oldest", "limit": 25}
        ).json()
        for item in found.get("items", []):
            if item["problem_text"] == problem_text:
                return self.client.get(f"/posts/{item['id']}", headers={}).json()
        return None

    def umbrella_id_by_name(self, level: str, entity_id: int, name: str) -> int:
        page = self.client.get(f"/umbrellas?community={level}:{entity_id}").json()
        for umbrella in page["umbrellas"]:
            if umbrella["name"] == name:
                return umbrella["id"]
        raise RuntimeError(f"no umbrella named {name!r} in {level}:{entity_id}")

    def poll_for_label(self, post_id: int, headers: dict) -> dict:
        for _ in range(LABEL_POLL_TRIES):
            body = self.client.get(f"/posts/{post_id}", headers=headers).json()
            if body["label_status"] in ("labeled", "needs_review"):
                return body
            time.sleep(LABEL_POLL_INTERVAL_SECONDS)
        return self.client.get(f"/posts/{post_id}", headers=headers).json()

    def load_post(self, entry: dict, accounts: dict[str, dict]) -> None:
        author = accounts[entry["author"]]
        if author["token"] is None:  # dry run, author not yet created
            self.report.skip(f"post {entry['key']}: would create (author is new)")
            return

        existing = self.find_existing_post(entry["problem"])
        if existing is not None:
            self.report.skip(f"post {entry['key']}: already exists (post {existing['id']})")
            self._apply_votes_and_comments(entry, existing, accounts, votes_already_cast=True)
            return

        if not self.apply:
            self.report.create(f"post (would create {entry['key']})")
            return

        me = self.me(author)
        home = {c["level"]: c["entity_id"] for c in me["home_communities"]}
        (level, target), = entry["file_under"].items()
        entity_id = home[level]

        if target == "ai":
            category_choice = "ai"
            community = {"level": level, "entity_id": entity_id}
        else:
            category_choice = "author_selected"
            umbrella_id = self.umbrella_id_by_name(level, entity_id, target)
            community = {"level": level, "entity_id": entity_id, "umbrella_id": umbrella_id}

        created = self._send(
            "POST",
            "/posts",
            headers=self._headers(author),
            json={
                "problem_text": entry["problem"],
                "solutions": [s["text"] for s in entry["solutions"]],
                "communities": [community],
                "category_choice": category_choice,
            },
        )
        if created.status_code != 201:
            self.report.skip(f"post {entry['key']}: POST /posts failed — {created.text}")
            return
        post_id = created.json()["id"]
        self.report.create("post")

        post_view = self.poll_for_label(post_id, self._headers(author))
        row = next(
            c for c in post_view["communities"]
            if c["community"]["level"] == level and c["community"]["entity_id"] == entity_id
        )
        if row["umbrella_id"] is None:
            self.report.skip(
                f"post {entry['key']}: labeling did not resolve to an umbrella "
                f"({post_view['label_status']}) — no votes or comments applied"
            )
            return

        self._apply_votes_and_comments(entry, post_view, accounts)

    def _apply_votes_and_comments(
        self,
        entry: dict,
        post_view: dict,
        accounts: dict[str, dict],
        *,
        votes_already_cast: bool = False,
    ) -> None:
        (level, _target), = entry["file_under"].items()
        row = next(c for c in post_view["communities"] if c["community"]["level"] == level)
        if row["umbrella_id"] is None or not row["solution_ids"]:
            return
        umbrella_id = row["umbrella_id"]
        solution_ids = row["solution_ids"]
        entity_id = row["community"]["entity_id"]

        members = [
            a
            for a in accounts.values()
            if a["token"] is not None
            and a["key"] != entry["author"]
            and self._is_member(a, level, entity_id)
        ]

        for position, solution_entry in enumerate(entry["solutions"]):
            if position >= len(solution_ids):
                break
            solution_id = solution_ids[position]
            up = solution_entry.get("up", 0)
            down = solution_entry.get("down", 0)
            voters = members[: up + down]
            for i, voter in enumerate(voters):
                direction = 1 if i < up else -1
                if self.apply:
                    self._send(
                        "PUT",
                        "/votes",
                        headers=self._headers(voter),
                        json={
                            "target_type": "solution",
                            "target_id": solution_id,
                            "direction": direction,
                        },
                    )
                    # PUT /votes is itself idempotent (one row per voter per
                    # target), so re-sending it is harmless and catches votes
                    # a prior, interrupted run never got to — but on a post
                    # that already existed, it is usually just re-affirming
                    # what is already there, so it is reported as such.
                    self.report.create("vote (confirmed)" if votes_already_cast else "vote")
                else:
                    self.report.create("vote (would cast)")

        for comment in entry.get("comments", []):
            author = accounts[comment["by"]]
            if author["token"] is None:
                continue
            target_id = solution_ids[0] if comment["target"] == "solution" else umbrella_id
            if self._comment_exists(comment["target"], target_id, author, comment["text"]):
                self.report.skip(
                    f"comment by {comment['by']} on {comment['target']} {target_id}: "
                    "already exists"
                )
                continue
            if self.apply:
                self._send(
                    "POST",
                    "/comments",
                    headers=self._headers(author),
                    json={
                        "target_type": comment["target"],
                        "target_id": target_id,
                        "text": comment["text"],
                    },
                )
                self.report.create("comment")
            else:
                self.report.create("comment (would post)")

    def _is_member(self, account: dict, level: str, entity_id: int) -> bool:
        cache = account.setdefault("_home", None)
        if cache is None:
            cache = {c["level"]: c["entity_id"] for c in self.me(account)["home_communities"]}
            account["_home"] = cache
        return cache.get(level) == entity_id

    def _comment_exists(self, target_type: str, target_id: int, author: dict, text: str) -> bool:
        if target_type == "umbrella":
            page = self.client.get(f"/umbrellas/{target_id}/comments").json()
            candidates = page.get("comments", [])
        else:
            solution = self.client.get(f"/solutions/{target_id}").json()
            candidates = solution.get("discussion", [])
        return any(c.get("author") == author.get("display_name") and c.get("text") == text for c in candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--log-path", default="/tmp/uvicorn.log")
    args = parser.parse_args()

    _require_allowed()

    dataset = yaml.safe_load(DATASET_FILE.read_text(encoding="utf-8"))
    report = Report()

    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        loader = Loader(client, Path(args.log_path), apply=args.apply, report=report)

        accounts: dict[str, dict] = {}
        for row in dataset["accounts"]:
            accounts[row["key"]] = loader.load_account(
                row["key"], row["name"], row["city"], row["county"]
            )

        for post_entry in dataset["posts"]:
            loader.load_post(post_entry, accounts)

    report.print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

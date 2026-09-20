# SANDBOX.md — The Sandbox and Trial Isolation

> How Claude Code runs on the director's workstation without being able
> to touch anything outside the trial it is building. Every long run —
> build or audit — happens inside a Docker Sandbox microVM. This
> document is the setup, the per-trial procedure, and the checks that
> prove the boundary holds.
>
> Commands marked **verified** come from Docker's documentation as of
> 2026-09-10 or were confirmed on the director's workstation on
> 2026-09-12 (**confirmed**). Items still marked **confirm on first
> setup** remain open.

---

## 1. The Safety Model in One Sentence

Claude Code can build anything inside a trial and cannot touch
anything outside it.

Concretely, inside the sandbox Claude Code has:
- the trial's copy of the repository (clone mode — the host checkout is
  never written to);
- its own Docker daemon, so Postgres, Redis, and the app run inside the
  VM;
- network to: the host's Ollama, `api.anthropic.com`, GitHub, and the
  package registries (PyPI, npm, Docker Hub) — and nothing else;
- a GitHub credential that can push `demo/*` branches and open pull
  requests, and cannot push to `main` (enforced by the `main` ruleset,
  not by the token).

It does **not** have: the host's home directory, the host's Docker,
the host's `~/.claude`, any SSH key, any credential other than the two
above, or the ability to reach the internet at large.

---

## 2. Host Requirements (verified)

- Ubuntu 24.04 or later, 64-bit.
- KVM available: `lsmod | grep kvm` shows `kvm_amd` (Threadripper) and
  `kvm`. If empty, run `kvm-ok` and enable virtualization in BIOS.
- The director's user in the `kvm` group:
  `sudo usermod -aG kvm $USER`, then log out and in.
- Ollama installed and running on the host, serving on its default
  port (11434), with `OLLAMA_MODEL` and `EMBED_MODEL` pulled.
  **Confirmed:** Ollama must bind to all interfaces. `sudo systemctl
  edit ollama`, add `[Service]` / `Environment="OLLAMA_HOST=0.0.0.0"`,
  restart. The VM reaches it at the host's LAN address (the
  `192.168.x.x` line of `ip -4 addr show`), not `localhost`.

---

## 3. Install (verified)

Docker's script installs Docker Engine and `sbx` together:

```
curl -fsSL https://get.docker.com | sudo SBX=1 sh
sbx login
```

`sbx login` opens a browser for Docker sign-in (a Docker account is
required; free). Then confirm (`sbx --version` is not a flag; the bare command prints
help):

```
sbx
```

---

## 4. Credentials Inside the Sandbox

### 4.1 Anthropic
Either store an API key as a sandbox secret — `sbx secret set anthropic`
(verified) — or use `/login` inside Claude Code for a Claude
subscription. **Confirmed 2026-09-12:** a subscription login done once
inside a sandbox persists for later sandboxes on the same host (a
second sandbox started straight into a working prompt). Unattended runs
are therefore possible with the subscription.

### 4.2 GitHub
The fine-grained token from the security cleanup (repo:
`direct-democracy-ca`; Contents and Pull requests read/write; 30-day
expiry). **Confirmed:** stored once with `sbx secret set github` (paste
when prompted; `sbx secret ls` shows names only). It is a *service
secret*: the sandbox proxy attaches it to GitHub requests on the
agent's behalf and **the token never enters the sandbox filesystem or
process** — Claude Code cannot read it or leak it. Renew every 30
days with the same command.

The `main` ruleset (require PR, block force push, restrict deletions)
is what stops this token reaching `main`. If the ruleset is ever
disabled, the token can push to `main` — re-check the ruleset before
every Foundation run.

---

## 5. Network Policy

Default-deny with an explicit allowlist. Set once on the host; applies
to every sandbox on this machine. **Confirmed:** the base posture must
be initialized first or every `allow` fails with 412:

```
sbx policy init deny-all
```

Then the allowlist (confirmed 2026-09-12; each prints "Rule added"):

```
sbx policy allow network api.anthropic.com
sbx policy allow network github.com
sbx policy allow network api.github.com
sbx policy allow network codeload.github.com
sbx policy allow network objects.githubusercontent.com
sbx policy allow network pypi.org
sbx policy allow network files.pythonhosted.org
sbx policy allow network registry.npmjs.org
sbx policy allow network registry-1.docker.io
sbx policy allow network auth.docker.io
sbx policy allow network production.cloudfront.docker.com
sbx policy allow network <host-ollama-address>:11434
```

**Confirmed 2026-09-14:** the Docker Hub blob host is
`production.cloudfront.docker.com` (an earlier draft of this file said
`cloudflare`; the demo-01 build could not pull images until the rule was
corrected). `host.docker.internal` and `localhost` are **not** routes to
the host from the VM; only the LAN address below is.

**Confirmed:** `<host-ollama-address>` is the host's LAN IP (currently
`192.168.1.165`; re-check with `ip -4 addr show` if the router
reassigns it, and update the rule). A blocked request returns
"Blocked by network policy: domain … — no matching allow rule", which
is the expected result for anything not listed. The app's
`OLLAMA_BASE_URL` in the sandbox `.env` is `http://<that address>:11434`.

**Still open:** the web search provider's domain must be added once a
provider is chosen (TODO P0-13).

Nothing else is allowed. In particular: no SMTP, no arbitrary web. A
build that "needs" another domain stops and reports; the director adds
it deliberately.

---

## 6. Per-Trial Procedure

### 6.1 Create the change branch (host)

```
cd ~/direct-democracy-ca
git switch main && git pull
git switch -c change/NN-short-name
# add the brief (and any files it ships with), then:
git add -A && git commit -m "change/NN brief" && git push -u origin change/NN-short-name
```

The sandbox is started from this branch (§6.2); switch the host back to
`main` afterwards.

### 6.2 Start the build sandbox (verified command form)

**Sync the host's local branch first — every time.** `--clone` copies the
host checkout's *local* branches, so a stale local `demo/NN` gives the
sandbox an old branch (confirmed 2026-09-14: the audit sandbox started
with `demo/01` at `main` and had to fast-forward itself):

```
cd ~/direct-democracy-ca
git fetch origin
git switch change/NN-short-name && git pull
sbx run --clone --name ddc-change-NN claude . -- "$(cat briefs/change-NN.md)"
```

Keep `sbx run` on **one line**. The prompt argument often does not
arrive and the window opens empty; the director then **types**: "your
brief is briefs/change-NN.md, follow it exactly".

`--clone` gives the sandbox its own git clone; the host working tree is
untouched. The brief is passed as the prompt. Claude Code starts with
`--dangerously-skip-permissions` by default inside the sandbox.

**Confirmed 2026-09-14:** the clone starts on the host's current branch
(`main`); the brief's first instruction (`git switch demo/01`) handles
it. Fix runs use a fresh sandbox (`ddc-demo-NN-fix-K`) started the same
way with the fix brief; the build sandbox's database is not needed
because every run rebuilds from empty.

### 6.3 Review from the host (verified)

While or after the run:

```
git fetch sandbox-ddc-demo-01
git diff main..sandbox-ddc-demo-01/demo/01 --stat
```

The sandbox's commits are visible on the host as a remote; nothing has
been written to the host checkout or pushed to GitHub until Claude Code
pushes `demo/01` with the scoped token.

### 6.4 Use the demo

Inside the sandbox the app listens on its ports. **Confirmed 2026-09-19:**

    sbx ports <sandbox-name> --publish 3000:3000 --publish 8000:8000
    sbx ports <sandbox-name>            # lists the bindings

Publishing starts a stopped sandbox. The bindings are on `127.0.0.1` and
persist across `sbx stop`. The servers themselves must be started inside
the VM (bound to `0.0.0.0`), which the director does by reopening the
sandbox's Claude Code session — `sbx run --name <sandbox-name> claude .`
reopens a stopped sandbox without cloning again — and asking it to start
the stack. Claude Code inside a sandbox declines pasted instructions
that start services; the director types the confirmation.

### 6.5 Audit sandbox

A second sandbox, read-only on the source:

```
sbx run --clone --name ddc-demo-01-audit claude . -- "$(cat briefs/audit.md)"
```

**Confirmed 2026-09-14: the source is writable in the audit sandbox**
(the auditor's `touch` test succeeded). No read-only flag has been
found yet. The safeguards are the audit brief's instruction not to edit,
the auditor's own final `git diff main...HEAD --stat`, and the host
check of the same diff — any file outside `audits/` and `HISTORY.md` is
a `HIGH` finding against the auditor. Finding the read-only policy stays
in §9.

### 6.6 Finish or discard

- **Accepted:** change audit (AUDIT.md §2), then `gh pr create --base
  main --head change/NN-short-name --fill`, merge in the browser, then
  on the host `git switch main && git pull && git push origin --delete
  change/NN-short-name`. At a demo: `git tag demo-N && git push origin
  demo-N`.
- **Rejected:** `git push origin --delete change/NN-short-name`. The
  code and the document edits go together.
- Remove the sandbox: `sbx rm ddc-demo-01` (**confirmed**; `sbx ls`
  lists, `sbx stop` pauses without removing, `sbx prune` clears stopped
  ones). The branch and the remote fetch survive; the VM, its database,
  and its Docker state do not.

### 6.7 Start the site to use it (verified 2026-09-19)

In a fresh sandbox on the branch to be used, ask Claude Code to: create
`.env` from `.env.example` **with `OLLAMA_BASE_URL` set to the host LAN
address (§5) and `ALLOW_TEST_DATA=true`**; start Postgres and Redis;
run both migration chains and the seed; start the backend on
`0.0.0.0:8000` and the frontend on `0.0.0.0:3000` with the root `.env`
exported; optionally run `backend/scripts/load_test_data.py --apply`.
Then on the host: `sbx ports <name> --publish 3000:3000 --publish
8000:8000` and browse to `http://localhost:3000` (browser VPN off). Make
an administrator with `backend/scripts/grant_admin.py <email> --apply`,
then sign out and in. Leaving the placeholder Ollama address in `.env`
leaves every post "not filed yet".

---

## 7. Boundary Checks (run 2026-09-12 — all seven passed; screenshots held by the director)

Inside a throwaway sandbox (`sbx run --clone --name boundary-test
shell .`). The sandbox user is `agent`. With `--clone`, the host folder
is mounted read-only at `/run/sandbox/source` and the sandbox's own
clone is mounted read-write at the **same path as on the host** (e.g.
`/home/kees-soares/direct-democracy-ca`), so paths in logs look like
host paths but are inside the VM. Each sandbox is created with 64 CPUs
and 32 GiB by default. The run log prints a `claude --resume <id>`
line; it reopens that session inside the same sandbox.

1. `curl -sS https://api.anthropic.com` — reachable (any HTTP response).
2. `curl -sS https://example.com` — **blocked**.
3. `curl -sS http://<host-ollama-address>:11434/api/tags` — returns
   the model list.
4. `ls ~` — no host home contents; `ls ~/.ssh` — absent.
5. `docker ps` — works, and shows nothing from the host.
6. `git push origin main` — **refused** by the ruleset (after a no-op
   commit on a test branch, `git push origin HEAD:main` returns a
   protected-branch error).
7. `git push origin HEAD:demo/boundary-test` — accepted; delete the
   branch on GitHub afterwards.

All seven passed on 2026-09-12: 1 → HTTP 404 (reachable); 2 → blocked
by policy; 3 → model list including `llama3.2` and `nomic-embed-text`;
4 → only `workspace`, no `.ssh`; 5 → empty container list; 6 → rejected
with GH013 "Changes must be made through a pull request"; 7 → new
branch created (deleted afterwards). Re-run after any change to the
policy, the ruleset, or the token. TODO P0-15 done.

---

## 8. What Never Goes in the Sandbox

- The host's `.env` files. The sandbox generates its own secrets into
  its own `.env` from `.env.example`; Postgres inside the VM gets a
  fresh password every trial.
- SSH keys, `gh` credentials, the Docker Hub login beyond what `sbx`
  itself needs.
- The AnimationDirector repository or any other project.
- A token with `repo` scope or without an expiry.

---

## 9. Open Items

Recorded in TODO P0-15's HISTORY entry when resolved:

- Read-only filesystem policy for the audit sandbox (confirmed absent by
  default; the flag, if one exists, is still to be found). The auditor's
  closing diff and the host diff are the safeguard.
- `archive.ubuntu.com` and `security.ubuntu.com` are not on the
  allowlist, so `apt` does not work inside the VM (fix run 4 worked
  around it with `pip --break-system-packages`). Add both with `sbx
  policy allow network` if a run needs system packages.
- (resolved 2026-09-19) `sbx ports` syntax — §6.4.
- (resolved 2026-09-19) reopening a sandbox — §6.4.
- (resolved 2026-09-14) the clone starts on the host's current branch;
  sync the local `demo/NN` before every run — §6.2.

Sources: Docker Sandboxes docs — Install, Claude Code agent page,
Network access policies (all dated 2026-09-10); Anthropic, "Choose a
sandbox environment".

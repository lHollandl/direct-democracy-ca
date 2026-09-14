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
sbx policy allow network production.cloudflare.docker.com
sbx policy allow network <host-ollama-address>:11434
```

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

### 6.1 Create the trial branch (host)

```
cd ~/direct-democracy-ca
git fetch origin
git switch -c demo/01 origin/main
git push -u origin demo/01
git switch main
```

The host checkout stays on `main`. The sandbox will work on `demo/01`
in its own clone.

### 6.2 Start the build sandbox (verified command form)

```
cd ~/direct-democracy-ca
sbx run --clone --name ddc-demo-01 claude . -- "$(cat briefs/demo-01.md)"
```

`--clone` gives the sandbox its own git clone; the host working tree is
untouched. The brief is passed as the prompt. Claude Code starts with
`--dangerously-skip-permissions` by default inside the sandbox.

**Confirm on first setup:** that the sandbox's clone checks out
`demo/01` rather than `main` — if not, the brief's first instruction
(`git switch demo/01`) handles it, and that is what the brief says.

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

Inside the sandbox the app listens on its ports. `sbx ports` manages
port publishing to the host (**confirmed** the subcommand exists; run
`sbx ports --help` on first use and record the exact form here). The
frontend on 3000 and the API on 8000 are the two to publish.

### 6.5 Audit sandbox

A second sandbox, read-only on the source:

```
sbx run --clone --name ddc-demo-01-audit claude . -- "$(cat briefs/audit.md)"
```

**Confirm on first setup:** the flag or filesystem policy that makes
the clone read-only except `audits/` (Docker's "Filesystem access"
page). Until confirmed, the audit brief instructs the auditor not to
edit, and the host diff check (`git diff --stat` against the audit
remote) proves it didn't — any file outside `audits/` in that diff is
a `HIGH` finding against the auditor.

### 6.6 Finish or discard

- **Foundation:** open a PR from `demo/01` to `main`; merge on the host
  after the audit is clean.
- **Iteration:** leave `demo/01` as a branch. Start `demo/02` from
  `main`.
- Remove the sandbox: `sbx rm ddc-demo-01` (**confirmed**; `sbx ls`
  lists, `sbx stop` pauses without removing, `sbx prune` clears stopped
  ones). The branch and the remote fetch survive; the VM, its database,
  and its Docker state do not.

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

- Exact `sbx ports` syntax for publishing 3000 and 8000.
- Read-only filesystem policy for the audit sandbox.
- (resolved) `sbx ls`, `sbx rm`, `sbx stop`, `sbx prune`, `sbx version`.

Sources: Docker Sandboxes docs — Install, Claude Code agent page,
Network access policies (all dated 2026-09-10); Anthropic, "Choose a
sandbox environment".

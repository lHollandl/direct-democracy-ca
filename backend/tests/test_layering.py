"""Enforces ARCHITECTURE.md §2's layer boundaries (audit demo-01 run 1, HIGH
finding: routers and several services touched the repository/ORM layer
directly instead of going through one service call and one repository
module).

Walks the source of every router and service file with Python's own AST —
not a text grep, so a renamed variable or a reformatted import can't hide a
violation — and fails with the file and the offending symbol when the
boundary is crossed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from backend.config.settings_env import repo_root

ROUTERS_DIR = repo_root() / "backend" / "routers"
SERVICES_DIR = repo_root() / "backend" / "services"
JOBS_DIR = repo_root() / "backend" / "jobs"
FRONTEND_SRC_DIR = repo_root() / "frontend" / "src"
API_TS_PATH = FRONTEND_SRC_DIR / "lib" / "api.ts"

#: Routers may call services only — never a repository, a client module, or a
#: job (job scheduling is the responsibility of the service that owns the
#: transaction — ARCHITECTURE.md §2, §7; resolves audit demo-01 run 1's
#: ambiguity 1).
FORBIDDEN_ROUTER_IMPORT_PREFIXES = ("backend.repositories", "backend.clients", "backend.jobs")

#: Jobs may call services only — never a repository or a client module
#: directly, and never a router (ARCHITECTURE.md §2's Jobs row: "May call:
#: services. Must not: routers, repositories directly." Audit demo-01 run 5,
#: MEDIUM: `labeling.py`, `similarity.py`, `references.py` reached into a
#: repository, and `reconcile.py` built its own queries and ran them on the
#: session directly — one layer further than even a service may go).
FORBIDDEN_JOB_IMPORT_PREFIXES = ("backend.repositories", "backend.clients", "backend.routers")

#: Neither a router nor a service may touch the session directly with these.
FORBIDDEN_SESSION_ATTRS = ("execute", "get")


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_session_call(node: ast.AST, attr_names: tuple[str, ...]) -> str | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "session"
        and node.func.attr in attr_names
    ):
        return node.func.attr
    return None


def _router_violations(path: Path) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
            FORBIDDEN_ROUTER_IMPORT_PREFIXES
        ):
            violations.append(
                f"{path.name}:{node.lineno} imports from {node.module!r} — a router may "
                "call only a service, never a repository, a client, or a job "
                "(ARCHITECTURE.md §2, §7)"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_ROUTER_IMPORT_PREFIXES):
                    violations.append(
                        f"{path.name}:{node.lineno} imports {alias.name!r} — a router may "
                        "call only a service, never a repository, a client, or a job "
                        "(ARCHITECTURE.md §2, §7)"
                    )
        attr = _is_session_call(node, FORBIDDEN_SESSION_ATTRS)
        if attr:
            violations.append(
                f"{path.name}:{node.lineno} calls session.{attr}(...) directly — a router "
                "must call a service, never the session (ARCHITECTURE.md §2)"
            )
    return violations


def _job_violations(path: Path) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
            FORBIDDEN_JOB_IMPORT_PREFIXES
        ):
            violations.append(
                f"{path.name}:{node.lineno} imports from {node.module!r} — a job may call "
                "only a service, never a repository, a client, or a router "
                "(ARCHITECTURE.md §2)"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_JOB_IMPORT_PREFIXES):
                    violations.append(
                        f"{path.name}:{node.lineno} imports {alias.name!r} — a job may call "
                        "only a service, never a repository, a client, or a router "
                        "(ARCHITECTURE.md §2)"
                    )
        attr = _is_session_call(node, FORBIDDEN_SESSION_ATTRS)
        if attr:
            violations.append(
                f"{path.name}:{node.lineno} calls session.{attr}(...) directly — a job "
                "must call a service, never the session (ARCHITECTURE.md §2)"
            )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "select"
        ):
            violations.append(
                f"{path.name}:{node.lineno} calls select(...) directly — a job must call "
                "a service function instead of building its own query "
                "(ARCHITECTURE.md §2)"
            )
    return violations


def _service_violations(path: Path) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(_parse(path)):
        attr = _is_session_call(node, FORBIDDEN_SESSION_ATTRS)
        if attr:
            violations.append(
                f"{path.name}:{node.lineno} calls session.{attr}(...) directly — a service "
                "must read and write through its aggregate's repository module "
                "(ARCHITECTURE.md §2)"
            )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "select"
        ):
            violations.append(
                f"{path.name}:{node.lineno} calls select(...) directly — a service must "
                "call a repository function instead of building its own query "
                "(ARCHITECTURE.md §2)"
            )
    return violations


def test_no_router_touches_a_repository_client_or_session():
    violations: list[str] = []
    for path in sorted(ROUTERS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        violations.extend(_router_violations(path))
    assert not violations, "Layering violations in backend/routers/:\n" + "\n".join(violations)


def test_no_service_touches_the_session_or_builds_its_own_query():
    violations: list[str] = []
    for path in sorted(SERVICES_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        violations.extend(_service_violations(path))
    assert not violations, "Layering violations in backend/services/:\n" + "\n".join(violations)


def test_no_job_touches_a_repository_client_or_session():
    """ARCHITECTURE.md §2's Jobs row, scanned with the same AST approach as
    the router check (audit demo-01 run 5, MEDIUM)."""
    violations: list[str] = []
    for path in sorted(JOBS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        violations.extend(_job_violations(path))
    assert not violations, "Layering violations in backend/jobs/:\n" + "\n".join(violations)


#: A router-decorated endpoint may call any number of `require_*` resolvers —
#: they fetch and validate, they never decide anything — but at most one
#: *other* service module (ARCHITECTURE.md §2, §10; audit demo-01 run 2,
#: MEDIUM: `solutions.py::get_solution` alone made ten service calls across
#: five modules and computed three thresholds itself). `backend.deps`
#: dependencies (`require_member`, `current_user`, ...) are not services and
#: are not counted at all.
_HTTP_METHODS = ("get", "post", "put", "patch", "delete")

#: `rules.py` module-level constants (`RULES_VERSION`, `FEED_VERSION`, ...)
#: are printed directly wherever a page needs to cite the rule version in
#: force (ARCHITECTURE.md §2 — "a RULES_VERSION constant printed in every
#: summary"); that is a plain attribute read, not a call, so it never reaches
#: `_ServiceUsage.calls`. Calling one of `rules.py`'s actual functions —
#: computing a threshold — is the "threshold arithmetic" §10 forbids in a
#: router; it must happen inside a service instead.


def _imported_service_modules(tree: ast.Module) -> dict[str, str]:
    """Map every name a file can call straight through to the
    `backend.services` (sub)module it resolves to — `comments_service` ->
    `backend.services.comments`, `author_displays` ->
    `backend.services.display` — so two different aliases for the same
    module are not double-counted."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and (
            node.module == "backend.services" or node.module.startswith("backend.services.")
        ):
            for alias in node.names:
                local_name = alias.asname or alias.name
                module = (
                    f"{node.module}.{alias.name}" if node.module == "backend.services" else node.module
                )
                aliases[local_name] = module
    return aliases


def _endpoint_functions(tree: ast.Module):
    for node in tree.body:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for deco in node.decorator_list:
            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and deco.func.attr in _HTTP_METHODS
            ):
                yield node
                break


def _router_endpoint_violations(path: Path) -> list[str]:
    """Audit demo-01 run 3, MEDIUM: counting distinct service **modules**
    (fix run 2's own version of this check) let an endpoint call several
    distinct functions on one module and still pass — `geo.py::community`
    called four `community_service` functions and assembled the response
    itself, invisible to a module-count check. This counts distinct
    `(module, function)` pairs instead, so calling more than one function on
    the same module is caught too."""
    tree = _parse(path)
    aliases = _imported_service_modules(tree)
    violations: list[str] = []
    for func in _endpoint_functions(tree):
        calls_used: set[tuple[str, str]] = set()
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                base, attr = node.func.value.id, node.func.attr
                module = aliases.get(base)
                if module is None:
                    continue
                if attr.startswith("require_"):
                    continue
                if module == "backend.services.rules" and attr[:1].islower():
                    violations.append(
                        f"{path.name}:{node.lineno} {func.name}() calls rules.{attr}(...) — "
                        "threshold arithmetic belongs in a service, never in a router "
                        "(ARCHITECTURE.md §2, §10)"
                    )
                    continue
                calls_used.add((module, attr))
            elif isinstance(node.func, ast.Name):
                module = aliases.get(node.func.id)
                if module is not None and not node.func.id.startswith("require_"):
                    calls_used.add((module, node.func.id))
        if len(calls_used) > 1:
            offenders = sorted(f"{module}.{attr}" for module, attr in calls_used)
            violations.append(
                f"{path.name} {func.name}() calls {offenders} — an endpoint calls at "
                "most one service function beyond a `require_*` resolver; move the "
                "assembly into that one service function (ARCHITECTURE.md §2, §10)"
            )
    return violations


#: Pathlib methods that hit the filesystem and block the event loop. `open(`
#: and `os.*` are checked separately. Deliberately excludes generic names
#: shared with non-filesystem types (`.replace(` on a string or a datetime,
#: `.write(` on something that isn't a file) so the check stays precise.
_BLOCKING_PATH_METHODS = {
    "mkdir",
    "rmdir",
    "unlink",
    "touch",
    "chmod",
    "exists",
    "stat",
    "write_text",
    "write_bytes",
    "read_text",
    "read_bytes",
    "iterdir",
    "glob",
    "rglob",
}


def _os_module_aliases(tree: ast.Module) -> set[str]:
    """Names bound to the `os` module itself (`import os`, `import os as o`)
    — not `from os import path`, a different object with its own methods."""
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "os"
    }


def _own_body(node: ast.AST):
    """Like `ast.walk`, but does not descend into a nested function, async
    function, lambda, or class — those run in their own scope and, called
    through `asyncio.to_thread`, are allowed to block (CLAUDE.md Law 11)."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        child = stack.pop()
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        yield child
        stack.extend(ast.iter_child_nodes(child))


def _blocking_io_violations(path: Path) -> list[str]:
    """CLAUDE.md Law 11 — no blocking call inside `async def`. Audit demo-01
    run 2 reported this as a LOW against `seed.py::_seed_cities`; fix run 2
    wrapped that one call, and the same pattern recurred untouched in
    `export.py` (audit demo-01 run 4, MEDIUM). `open(...)`, any `os.*` call,
    and pathlib's blocking IO methods all belong behind `asyncio.to_thread`
    (or `aiofiles`), exactly as `seed.py` and `email.py` already do."""
    tree = _parse(path)
    os_names = _os_module_aliases(tree)
    violations: list[str] = []
    for func in ast.walk(tree):
        if not isinstance(func, ast.AsyncFunctionDef):
            continue
        for node in _own_body(func):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                violations.append(
                    f"{path.name}:{node.lineno} {func.name}() calls open(...) directly — "
                    "wrap blocking file IO in asyncio.to_thread (CLAUDE.md Law 11)"
                )
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in os_names:
                    violations.append(
                        f"{path.name}:{node.lineno} {func.name}() calls "
                        f"os.{node.func.attr}(...) directly — wrap blocking file IO in "
                        "asyncio.to_thread (CLAUDE.md Law 11)"
                    )
                elif node.func.attr in _BLOCKING_PATH_METHODS:
                    violations.append(
                        f"{path.name}:{node.lineno} {func.name}() calls "
                        f".{node.func.attr}(...) directly — that is a blocking pathlib IO "
                        "call; wrap it in asyncio.to_thread (CLAUDE.md Law 11)"
                    )
    return violations


def test_no_blocking_file_io_inside_async_def():
    violations: list[str] = []
    for directory in (SERVICES_DIR, JOBS_DIR):
        for path in sorted(directory.glob("*.py")):
            if path.name == "__init__.py":
                continue
            violations.extend(_blocking_io_violations(path))
    assert not violations, "Blocking file IO inside async def:\n" + "\n".join(violations)


#: A call to `fetch(` on its own text, not preceded by an identifier
#: character — so `apiFetch(` or `.fetch(` on some other object doesn't
#: false-positive, but a bare `fetch(` or `window.fetch(` does.
_FETCH_CALL = re.compile(r"(?<![A-Za-z0-9_.])fetch\s*\(")


def test_frontend_calls_fetch_only_from_api_ts():
    """ARCHITECTURE.md §9 — `frontend/src/lib/api.ts` is the only place
    `fetch` is called. Audit demo-01 run 5, MEDIUM: FIX-34 made the landing
    page an async Server Component that called `fetch` itself, opening a
    second place in the frontend that talks to the API."""
    violations: list[str] = []
    for path in sorted(FRONTEND_SRC_DIR.rglob("*.ts")) + sorted(FRONTEND_SRC_DIR.rglob("*.tsx")):
        if path == API_TS_PATH:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _FETCH_CALL.search(line):
                violations.append(
                    f"{path.relative_to(FRONTEND_SRC_DIR)}:{lineno} calls fetch(...) — "
                    "frontend/src/lib/api.ts is the only place fetch is called "
                    "(ARCHITECTURE.md §9)"
                )
    assert not violations, "Layering violations in frontend/src/:\n" + "\n".join(violations)


def test_no_endpoint_calls_more_than_one_service_function_or_does_threshold_arithmetic():
    """Audit demo-01 run 2, MEDIUM: `get_solution` assembled its response from
    ten service calls across five modules and computed thresholds inline
    instead of calling `solutions_service.detail_view`. Fixed by FIX-11.
    Audit demo-01 run 3, MEDIUM: two of that same finding's five originally
    named offenders (`geo.py::community`, `amendments.py::propose_amendment`)
    were untouched, because the check only counted distinct modules and both
    called several functions from a single module. This counts functions."""
    violations: list[str] = []
    for path in sorted(ROUTERS_DIR.glob("*.py")):
        if path.name in ("__init__.py", "common.py"):
            continue
        violations.extend(_router_endpoint_violations(path))
    assert not violations, "Layering violations in backend/routers/:\n" + "\n".join(violations)

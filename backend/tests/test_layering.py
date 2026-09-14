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
from pathlib import Path

from backend.config.settings_env import repo_root

ROUTERS_DIR = repo_root() / "backend" / "routers"
SERVICES_DIR = repo_root() / "backend" / "services"

#: Routers may call services only — never a repository or a client module.
FORBIDDEN_ROUTER_IMPORT_PREFIXES = ("backend.repositories", "backend.clients")

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
                "call only a service, never a repository or a client (ARCHITECTURE.md §2)"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_ROUTER_IMPORT_PREFIXES):
                    violations.append(
                        f"{path.name}:{node.lineno} imports {alias.name!r} — a router may "
                        "call only a service, never a repository or a client "
                        "(ARCHITECTURE.md §2)"
                    )
        attr = _is_session_call(node, FORBIDDEN_SESSION_ATTRS)
        if attr:
            violations.append(
                f"{path.name}:{node.lineno} calls session.{attr}(...) directly — a router "
                "must call a service, never the session (ARCHITECTURE.md §2)"
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

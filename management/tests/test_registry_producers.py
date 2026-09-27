"""
The system-notification registry and the code that produces events must agree.

An event registered in ``DEFAULT_SYSTEM_EVENTS`` with no ``dispatch_notification``
call anywhere is dead UI: it has a card, a toggle and targets, and can never
fire. An event dispatched in code but not registered is dropped silently by
``dispatch_notification`` with no history row.

These tests walk the AST of ``api/`` rather than grepping, so a slug on the
line after ``dispatch_notification(`` is still found.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Set

import pytest

MANAGEMENT_DIR = Path(__file__).resolve().parents[1]
API_DIR = MANAGEMENT_DIR / "api"
NOTIFICATION_SERVICE = API_DIR / "services" / "notification_service.py"

# Registered events that have no producer yet. Each one is a card in the UI
# that cannot fire at any setting. Writing a producer for one of these MUST
# remove it from this list, or the test below fails. Adding a new registered
# event without a producer also fails: register and produce in the same change.
KNOWN_DEAD_EVENTS: Set[str] = {
    "certificate_expiring",
    "container_healthy",
    "container_high_cpu",
    "container_high_memory",
    "disk_space_low",
    "high_cpu",
    "high_memory",
    "security_event",
    "update_available",
}


def _registered_events() -> Set[str]:
    from api.models.system_notifications import DEFAULT_SYSTEM_EVENTS

    return {e["event_type"] for e in DEFAULT_SYSTEM_EVENTS}


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _dispatched_events() -> Dict[str, List[str]]:
    """Map of slug -> [file:line, ...] for every dispatch_notification("...") call."""
    found: Dict[str, List[str]] = {}
    for path in sorted(API_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node) != "dispatch_notification":
                continue
            if not node.args:
                continue
            where = f"{path.relative_to(MANAGEMENT_DIR)}:{node.lineno}"
            slug_node = node.args[0]
            if isinstance(slug_node, ast.Constant) and isinstance(slug_node.value, str):
                found.setdefault(slug_node.value, []).append(where)
            else:
                pytest.fail(
                    f"{where}: dispatch_notification called with a non-literal event type; "
                    "the registry check cannot see it. Pass a string literal."
                )
    return found


def _string_constants_in_function(path: Path, function_name: str) -> Set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return {
                n.value
                for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            }
    pytest.fail(f"{function_name} not found in {path}")


def test_every_dispatched_event_is_registered():
    """A produced-but-unregistered event is dropped silently. There must be none."""
    orphans = set(_dispatched_events()) - _registered_events()
    assert not orphans, (
        f"dispatched but not in DEFAULT_SYSTEM_EVENTS: {sorted(orphans)}. "
        "Add the event to DEFAULT_SYSTEM_EVENTS or remove the dispatch call."
    )


def test_dead_events_are_exactly_the_known_list():
    """
    Registered events without a producer must match KNOWN_DEAD_EVENTS exactly.

    Shrinks when a producer is written (update the list). Grows never: a new
    registered event needs a producer in the same change.
    """
    dead = _registered_events() - set(_dispatched_events())
    newly_dead = dead - KNOWN_DEAD_EVENTS
    revived = KNOWN_DEAD_EVENTS - dead
    assert not newly_dead, (
        f"registered with no producer and not in KNOWN_DEAD_EVENTS: {sorted(newly_dead)}"
    )
    assert not revived, (
        f"now have a producer; remove from KNOWN_DEAD_EVENTS: {sorted(revived)}"
    )


def test_every_live_event_has_a_message_formatter():
    """
    Each registered slug that has a producer gets a dedicated branch in
    _build_notification_message, not the generic key/value fallback. Dead
    events are exempt until their producer lands; write both together.
    """
    formatted = _string_constants_in_function(NOTIFICATION_SERVICE, "_build_notification_message")
    live = _registered_events() - KNOWN_DEAD_EVENTS
    missing = live - formatted
    assert not missing, f"no formatter branch for: {sorted(missing)}"


def test_dispatch_gate_mentions_only_registered_container_slugs():
    """
    The per-container gate map and the formatter must not reference container
    slugs that do not exist in the registry (slug drift).
    """
    registered = _registered_events()
    # "container_" is the category prefix check; "container_name" is an
    # event_data key. Neither is a slug.
    not_slugs = {"container_", "container_name"}
    for function_name in ("dispatch_notification", "_build_notification_message"):
        constants = _string_constants_in_function(NOTIFICATION_SERVICE, function_name)
        container_slugs = {c for c in constants if c.startswith("container_")} - not_slugs
        unknown = container_slugs - registered
        assert not unknown, f"{function_name} references unregistered slugs: {sorted(unknown)}"


def test_dispatch_notification_is_the_only_dispatcher():
    """
    ``NotificationService.dispatch`` (the notification_rules engine) has no
    callers. Nothing may start using it: there must be one gate, not two.
    """
    for path in sorted(API_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "dispatch" and not (
                    isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
                ):
                    pytest.fail(
                        f"{path.relative_to(MANAGEMENT_DIR)}:{node.lineno} calls .dispatch(); "
                        "use dispatch_notification so the single gate applies."
                    )

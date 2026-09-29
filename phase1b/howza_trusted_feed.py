"""HOWZA Phase 1B trusted-feed gate over frozen Phase 1A."""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple

import howza_market_data as phase1a


# ---------------------------------------------------------------------------
# Locked categorical trust states
# ---------------------------------------------------------------------------

TRUSTED = "TRUSTED"
DEGRADED = "DEGRADED"
UNTRUSTED = "UNTRUSTED"

CHECK_PASS = "pass"
CHECK_WARN = "warn"
CHECK_FAIL = "fail"

FRESHNESS_CLASSES = {"FRESH", "AGING", "STALE"}
HEALTH_STATUSES = {"UP", "DEGRADED", "DOWN"}

# Deterministic fixture policy.
POLICY_INSTRUMENT = "BTCUSD"
POLICY_TIMEFRAME = "1m"
POLICY_FRESH = 60
POLICY_AGING = 300
POLICY_STALE = 900
POLICY_VERSION = "phase1b-fixture-v1"

# Fixed evaluation point so fixture behaviour is deterministic.
REFERENCE_EVALUATION_TIME = datetime(
    2026,
    1,
    1,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)

FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "urllib",
    "socket",
    "websocket",
    "os",
    "subprocess",
    "pathlib",
    "pickle",
    "marshal",
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "compile",
    "open",
}


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _check_static_guard() -> Dict[str, Any]:
    """Check Phase 1B itself for forbidden imports/calls."""

    module = inspect.getmodule(inspect.currentframe())

    if module is None:
        return {
            "passed": False,
            "bad_imports": [],
            "bad_calls": [],
        }

    source = inspect.getsource(module)
    tree = ast.parse(source)

    imports = set()
    calls = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    bad_imports = sorted(imports & FORBIDDEN_IMPORTS)
    bad_calls = sorted(calls & FORBIDDEN_CALLS)

    return {
        "passed": not bad_imports and not bad_calls,
        "bad_imports": bad_imports,
        "bad_calls": bad_calls,
    }


def _check(
    state: str,
    detail: str,
) -> Dict[str, str]:
    if state not in {CHECK_PASS, CHECK_WARN, CHECK_FAIL}:
        raise ValueError("invalid check state")

    return {
        "state": state,
        "detail": detail,
}

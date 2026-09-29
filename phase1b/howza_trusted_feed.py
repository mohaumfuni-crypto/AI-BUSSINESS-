"""Phase 1B: HOWZA Trusted Feed.

Trust gate over the frozen Phase 1A market-data package.

Rules:
- categorical verdict only: TRUSTED / UNTRUSTED
- no numeric trust score
- read-only
- no network access
- no credentials
- no trading
- no provider-network logic
"""

import ast
import inspect
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import howza_market_data as phase1a


FROZEN_PHASE1A_MODULE = "howza_market_data"

_TRUSTED = "TRUSTED"
_UNTRUSTED = "UNTRUSTED"

_FRESHNESS_CLASSES = {
    "FRESH",
    "AGING",
    "STALE",
}

_HEALTH_STATUSES = {
    "UP",
    "DEGRADED",
    "DOWN",
}

_SOURCE_FIELDS = {
    "source_id",
    "provider_id",
    "instrument",
    "received_at_utc",
    "candle",
    "raw_ref",
}

_CANDLE_FIELDS = {
    "open",
    "high",
    "low",
    "close",
    "volume",
    "has_volume",
    "received_at_utc",
}

_POLICY_INSTRUMENT = "BTCUSD"
_POLICY_TIMEFRAME = "1m"
_POLICY_FRESH = 60
_POLICY_AGING = 300
_POLICY_STALE = 900
_POLICY_VERSION = "phase1b-fixture-v1"

_FORBIDDEN = {
    "requests",
    "httpx",
    "urllib",
    "socket",
    "websocket",
    "os",
    "subprocess",
    "sys",
    "pathlib",
    "pickle",
    "marshal",
    "eval",
    "exec",
    "compile",
    "open",
}

_US = chr(95)


def _is_dunder_call(name: str) -> bool:
    """Detect dunder-style call names structurally."""
    return (
        len(name) > 4
        and name.startswith(_US * 2)
        and name.endswith(_US * 2)
    )


def _check_static_guard() -> Dict[str, Any]:
    """Check this module for forbidden imports and calls."""
    imported = set()
    called = set()

    module = inspect.getmodule(inspect.currentframe())

    if module is None:
        return {
            "passed": False,
            "bad_imports": [],
            "bad_calls": [],
        }

    source = inspect.getsource(module)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(
                    alias.asname or alias.name.split(".")[0]
                )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])

        elif isinstance(node, ast.Call):
            func = node.func

            if isinstance(func, ast.Name):
                called.add(func.id)

            elif isinstance(func, ast.Attribute):
                called.add(func.attr)

    bad_imports = sorted(imported & _FORBIDDEN)

    bad_calls = sorted(
        (called & _FORBIDDEN)
        | {
            name
            for name in called
            if _is_dunder_call(name)
        }
    )

    return {
        "passed": not bad_imports and not bad_calls,
        "bad_imports": bad_imports,
        "bad_calls": bad_calls,
    }


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def make_fixture_policy() -> Any:
    """Create the deterministic Phase 1B fixture freshness policy."""
    return phase1a.FreshnessPolicy(
        instrument=_POLICY_INSTRUMENT,
        timeframe=_POLICY_TIMEFRAME,
        fresh_seconds=_POLICY_FRESH,
        aging_seconds=_POLICY_AGING,
        stale_seconds=_POLICY_STALE,
        policy_version=_POLICY_VERSION,
    )


def check_frozen_interfaces() -> Dict[str, Any]:
    """Verify the frozen Phase 1A interfaces used by Phase 1B."""
    details: Dict[str, Any] = {}
    ok = True

    required_classes = [
        "FreshnessPolicy",
        "FreshnessClass",
        "SourceRecord",
        "ProviderHealthStatus",
    ]

    for name in required_classes:
        present = hasattr(phase1a, name)
        details["class_" + name] = present
        ok = ok and present

    try:
        freshness_members = {
            member.name
            for member in phase1a.FreshnessClass
        }

        freshness_ok = (
            freshness_members == _FRESHNESS_CLASSES
        )
    except Exception:
        freshness_ok = False

    details["freshness_class_members"] = freshness_ok
    ok = ok and freshness_ok

    try:
        health_members = {
            member.name
            for member in phase1a.ProviderHealthStatus
        }

        health_ok = (
            health_members == _HEALTH_STATUSES
        )
    except Exception:
        health_ok = False

    details["provider_health_status_members"] = health_ok
    ok = ok and health_ok

    required_functions = [
        "get_provider_health",
        "classify_freshness",
        "trust_lifecycle",
    ]

    for name in required_functions:
        present = callable(
            getattr(phase1a, name, None)
        )

        details["fn_" + name] = present
        ok = ok and present

    try:
        signature = inspect.signature(
            phase1a.FreshnessPolicy
        )

        policy_ok = (
            set(signature.parameters)
            == {
                "instrument",
                "timeframe",
                "fresh_seconds",
                "aging_seconds",
                "stale_seconds",
                "policy_version",
            }
        )
    except Exception:
        policy_ok = False

    details["freshness_policy_ctor"] =

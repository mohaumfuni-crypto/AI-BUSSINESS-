"""HOWZA Phase 1B trusted-feed gate over frozen Phase 1A."""

import ast
import inspect
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import howza_market_data as phase1a


TRUSTED = "TRUSTED"
UNTRUSTED = "UNTRUSTED"

FRESHNESS_CLASSES = {"FRESH", "AGING", "STALE"}
HEALTH_STATUSES = {"UP", "DEGRADED", "DOWN"}

POLICY_INSTRUMENT = "BTCUSD"
POLICY_TIMEFRAME = "1m"
POLICY_FRESH = 60
POLICY_AGING = 300
POLICY_STALE = 900
POLICY_VERSION = "phase1b-fixture-v1"

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


def make_fixture_policy() -> Any:
    """Create the deterministic Phase 1B freshness policy."""

    return phase1a.FreshnessPolicy(
        instrument=POLICY_INSTRUMENT,
        timeframe=POLICY_TIMEFRAME,
        fresh_seconds=POLICY_FRESH,
        aging_seconds=POLICY_AGING,
        stale_seconds=POLICY_STALE,
        policy_version=POLICY_VERSION,
    )


def check_frozen_interfaces() -> Dict[str, Any]:
    """Verify required frozen Phase 1A interfaces."""

    details = {}
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
        members = {
            member.name
            for member in phase1a.FreshnessClass
        }
        freshness_ok = members == FRESHNESS_CLASSES
    except Exception:
        freshness_ok = False

    details["freshness_class_members"] = freshness_ok
    ok = ok and freshness_ok

    try:
        members = {
            member.name
            for member in phase1a.ProviderHealthStatus
        }
        health_ok = members == HEALTH_STATUSES
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
        present = callable(getattr(phase1a, name, None))
        details["fn_" + name] = present
        ok = ok and present

    try:
        signature = inspect.signature(
            phase1a.FreshnessPolicy
        )

        expected = {
            "instrument",
            "timeframe",
            "fresh_seconds",
            "aging_seconds",
            "stale_seconds",
            "policy_version",
        }

        policy_ok = set(signature.parameters) == expected

    except Exception:
        policy_ok = False

    details["freshness_policy_ctor"] = policy_ok
    ok = ok and policy_ok

    return {
        "passed": ok,
        "details": details,
    }


def check_source_record_schema(record: Any) -> Dict[str, Any]:
    """Check the expected SourceRecord/Candle structure."""

    details = {}
    ok = True

    source_fields = {
        "source_id",
        "provider_id",
        "instrument",
        "received_at_utc",
        "candle",
        "raw_ref",
    }

    fields_ok = all(
        hasattr(record, field)
        for field in source_fields
    )

    details["source_fields"] = fields_ok
    ok = ok and fields_ok

    candle = getattr(record, "candle", None)

    candle_fields = {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "has_volume",
        "received_at_utc",

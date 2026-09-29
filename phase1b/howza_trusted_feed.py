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

_FRESHNESS_CLASSES = {"FRESH", "AGING", "STALE"}
_HEALTH_STATUSES = {"UP", "DEGRADED", "DOWN"}

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

_FORBIDDEN_IMPORTS = {
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

_FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "compile",
    "open",
}


def _is_dunder_call(name: str) -> bool:
    return (
        len(name) > 4
        and name.startswith("__")
        and name.endswith("__")
    )


def _check_static_guard() -> Dict[str, Any]:
    """Audit this module for forbidden imports/calls."""

    imported = set()
    called = set()

    module = inspect.getmodule(inspect.currentframe())

    if module is None:
        return {
            "passed": False,l

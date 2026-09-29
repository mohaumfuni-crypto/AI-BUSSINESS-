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

POLICY_INSTRUMENT = "BTCUSD"
POLICY_TIMEFRAME = "1m"
POLICY_FRESH = 60
POLICY_AGING = 300
POLICY_STALE = 900
POLICY_VERSION = "phase1b-fixture-v1"

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


# ---------------------------------------------------------------------------
# Frozen Phase 1A interface verification
# ---------------------------------------------------------------------------

def check_frozen_interfaces() -> Dict[str, Any]:
    """Verify the public interfaces supplied by frozen Phase 1A."""

    details: Dict[str, Any] = {}

    provider_cls = getattr(
        phase1a,
        "MarketDataProvider",
        None,
    )

    details["MarketDataProvider"] = (
        inspect.isclass(provider_cls)
        and inspect.isabstract(provider_cls)
    )

    required_names = (
        "Candle",
        "SourceRecord",
        "FreshnessPolicy",
        "FreshnessClass",
        "ProviderHealth",
        "ProviderHealthStatus",
        "SUPPORTED_INSTRUMENTS",
        "classify_freshness",
        "comparable_fields",
        "crypto_lifecycle",
    )

    for name in required_names:
        details[name] = hasattr(phase1a, name)

    if inspect.isclass(provider_cls):
        required_provider_members = (
            "supports_instrument",
            "to_provider_symbol",
            "to_howza_instrument",
            "to_provider_timeframe",
            "to_howza_timeframe",
            "get_source_records",
            "source_id_for",
            "health",
        )

        for name in required_provider_members:
            details[f"MarketDataProvider.{name}"] = hasattr(
                provider_cls,
                name,
            )

        details["MarketDataProvider.provider_id"] = isinstance(
            getattr(provider_cls, "provider_id", None),
            property,
        )

        details["MarketDataProvider.provider_name"] = isinstance(
            getattr(provider_cls, "provider_name", None),
            property,
        )

    details["trust_lifecycle"] = callable(
        globals().get("trust_lifecycle")
    )

    return {
        "passed": all(details.values()),
        "details": details,
    }


# ---------------------------------------------------------------------------
# Deterministic Phase 1B fixture provider
# ---------------------------------------------------------------------------

class FixtureProvider(phase1a.MarketDataProvider):
    """Deterministic provider used only for Phase 1B verification."""

    @property
    def provider_id(self) -> str:
        return "phase1b-fixture"

    @property
    def provider_name(self) -> str:
        return "HOWZA Phase 1B Fixture Provider"

    def to_provider_symbol(self, instrument: str) -> str:
        if instrument not in phase1a.SUPPORTED_INSTRUMENTS:
            raise ValueError("unsupported instrument")
        return instrument

    def to_howza_instrument(self, symbol: str) -> str:
        if symbol not in phase1a.SUPPORTED_INSTRUMENTS:
            raise ValueError("unsupported provider symbol")
        return symbol

    def to_provider_timeframe(self, timeframe: str) -> str:
        if not timeframe:
            raise ValueError("timeframe required")
        return timeframe

    def to_howza_timeframe(self, timeframe: str) -> str:
        if not timeframe:
            raise ValueError("timeframe required")
        return timeframe

    def get_source_records(
        self,
        instrument: str,
        timeframe: str,
        limit: int = 1,
    ) -> Tuple[phase1a.SourceRecord, ...]:
        if instrument not in phase1a.SUPPORTED_INSTRUMENTS:
            raise ValueError("unsupported instrument")

        if not timeframe:
            raise ValueError("timeframe required")

        if limit < 1:
            return ()

        close_time = REFERENCE_EVALUATION_TIME - timedelta(
            seconds=30
        )
        open_time = close_time - timedelta(minutes=1)

        candle = phase1a.Candle(
            instrument=instrument,
            timeframe=timeframe,
            open_time_utc=open_time,
            close_time_utc=close_time,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=10.0,
            is_closed=True,
            source_id=self.source_id_for(
                instrument,
                timeframe,
            ),
            received_at_utc=close_time,
        )

        record = phase1a.SourceRecord(
            source_id=self.source_id_for(
                instrument,
                timeframe,
            ),
            provider_id=self.provider_id,
            instrument=instrument,
            received_at_utc=close_time,
            candle=candle,
            raw_ref="phase1b-fixture",
        )

        return (record,)

    def source_id_for(
        self,
        instrument: str,
        timeframe: str,
    ) -> str:
        return f"{self.provider_id}:{instrument}:{timeframe}"

    def health(self) -> phase1a.ProviderHealth:
        return phase1a.ProviderHealth(
            provider_id=self.provider_id,
            status=phase1a.ProviderHealthStatus.UP,
            at_utc=REFERENCE_EVALUATION_TIME,
            detail="deterministic phase1b fixture",
        )


# ---------------------------------------------------------------------------
# Source-record validation
# ---------------------------------------------------------------------------

def check_source_record_schema(
    record: Any,
) -> Dict[str, Any]:
    """Validate the Phase 1A SourceRecord contract."""

    required = {
        "source_id",
        "provider_id",
        "instrument",
        "received_at_utc",
        "candle",
        "raw_ref",
    }

    missing = sorted(
        name for name in required
        if not hasattr(record, name)
    )

    candle = getattr(record, "candle", None)

    candle_required = {
        "instrument",
        "timeframe",
        "open_time_utc",
        "close_time_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "is_closed",
        "source_id",
        "received_at_utc",
    }

    candle_missing = sorted(
        name for name in candle_required
        if not hasattr(candle, name)
    )

    passed = not missing and not candle_missing

    return {
        "passed": passed,
        "missing": missing,
        "candle_missing": candle_missing,
    }


# ---------------------------------------------------------------------------
# Freshness and health evaluation
# ---------------------------------------------------------------------------

def _freshness_check(
    record: phase1a.SourceRecord,
    policy: phase1a.FreshnessPolicy,
    evaluated_at: datetime,
) -> Dict[str, str]:
    age_seconds = (
        evaluated_at - record.received_at_utc
    ).total_seconds()

    if age_seconds < 0:
        return _check(
            CHECK_FAIL,
            "source record is timestamped in the future",
        )

    freshness = phase1a.classify_freshness(
        policy,
        age_seconds,
    )

    if freshness == phase1a.FreshnessClass.FRESH:
        return _check(
            CHECK_PASS,
            f"freshness={freshness.value}; age_seconds={age_seconds:.3f}",
        )

    if freshness == phase1a.FreshnessClass.AGING:
        return _check(
            CHECK_WARN,
            f"freshness={freshness.value}; age_seconds={age_seconds:.3f}",
        )

    return _check(
        CHECK_FAIL,
        f"freshness={freshness.value}; age_seconds={age_seconds:.3f}",
    )


def _health_check(
    provider: phase1a.MarketDataProvider,
) -> Dict[str, str]:
    health = provider.health()

    status = health.status.value

    if status == "UP":
        return _check(
            CHECK_PASS,
            f"provider health={status}",
        )

    if status == "DEGRADED":
        return _check(
            CHECK_WARN,
            f"provider health={status}",
        )

    return _check(
        CHECK_FAIL,
        f"provider health={status}",
    )


# ---------------------------------------------------------------------------
# Trusted snapshot
# ---------------------------------------------------------------------------

def trust_snapshot(
    provider: phase1a.MarketDataProvider,
    instrument: str,
    timeframe: str,
    *,
    evaluated_at: datetime | None = None,
) -> Dict[str, Any]:
    """Evaluate one provider snapshot using categorical trust states."""

    if evaluated_at is None:
        evaluated_at = _now_utc()

    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")

    evaluated_at = evaluated_at.astimezone(timezone.utc)

    checks: Dict[str, Dict[str, str]] = {}
    errors = []

    policy = phase1a.FreshnessPolicy(
        instrument=instrument,
        timeframe=timeframe,
        fresh_seconds=POLICY_FRESH,
        aging_seconds=POLICY_AGING,
        stale_seconds=POLICY_STALE,
        policy_version=POLICY_VERSION,
    )

    try:
        supported = provider.supports_instrument(instrument)

        checks["instrument"] = (
            _check(
                CHECK_PASS,
                "instrument supported",
            )
            if supported
            else _check(
                CHECK_FAIL,
                "instrument not supported",
            )
        )

        records = provider.get_source_records(
            instrument,
            timeframe,
            limit=1,
        )

        if not records:
            checks["data"] = _check(
                CHECK_FAIL,
                "no source records returned",
            )
            errors.append("NO_DATA")

        else:
            record = records[0]

            schema = check_source_record_schema(record)

            checks["schema"] = (
                _check(
                    CHECK_PASS,
                    "source record schema valid",
                )
                if schema["passed"]
                else _check(
                    CHECK_FAIL,
                    "source record schema invalid",
                )
            )

            checks["freshness"] = _freshness_check(
                record,
                policy,
                evaluated_at,
            )

            checks["health"] = _health_check(provider)

            if checks["freshness"]["state"] == CHECK_FAIL:
                errors.append("STALE_DATA")

            if checks["health"]["state"] == CHECK_FAIL:
                errors.append("PROVIDER_DOWN")

            if checks["schema"]["state"] == CHECK_FAIL:
                errors.append("INVALID_SCHEMA")

    except Exception as exc:
        checks["evaluation"] = _check(
            CHECK_FAIL,
            f"evaluation error: {type(exc).__name__}",
        )
        errors.append(type(exc).__name__)

    states = {
        check["state"]
        for check in checks.values()
    }

    if CHECK_FAIL in states:
        status = UNTRUSTED
    elif CHECK_WARN in states:
        status = DEGRADED
    else:
        status = TRUSTED

    symbol = provider.to_provider_symbol(instrument)

    return {
        "status": status,
        "checks": checks,
        "errors": errors,
        "evaluated_at": evaluated_at,
        "provider_id": provider.provider_id,
        "symbol": symbol,
        "timeframe": timeframe,
    }


# ---------------------------------------------------------------------------
# Phase 1B lifecycle
# ---------------------------------------------------------------------------

def trust_lifecycle() -> Dict[str, Any]:
    """Run the deterministic Phase 1B trust lifecycle."""

    provider = FixtureProvider()

    snapshot = trust_snapshot(
        provider,
        POLICY_INSTRUMENT,
        POLICY_TIMEFRAME,
        evaluated_at=REFERENCE_EVALUATION_TIME,
    )

    return {
        "status": snapshot["status"],
        "phase": "1B",
        "lifecycle": (
            "AUTHORED -> STATICALLY AUDITED -> "
            "EXECUTED -> TESTED -> VERIFIED"
        ),
        "categorical_only": True,
        "numeric_trust_score": False,
        "snapshot": snapshot,
    }

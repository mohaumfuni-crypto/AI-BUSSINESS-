"""HOWZA Phase 1B - Trusted Feed Layer.

Consumes the frozen Phase 1A market-data contract and exposes a deterministic,
offline trust-gated interface for downstream consumers.

Public interface:
    trust_snapshot(provider, howza_instrument, howza_timeframe, *, evaluated_at)
    trust_lifecycle(evaluated_at=None)

No network access, credentials, secrets, or trading capability.
"""

from __future__ import annotations

import inspect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Phase 1A lives in a directory whose name contains a hyphen, so it cannot be
# imported as a normal Python package. Add that directory to sys.path without
# modifying any Phase 1A files.
_PHASE1A_DIR = Path(__file__).resolve().parents[1] / "phase1a-execution"
if str(_PHASE1A_DIR) not in sys.path:
    sys.path.insert(0, str(_PHASE1A_DIR))

import howza_market_data as _m1a


# ---------------------------------------------------------------------------
# Phase 1A binding verification
# ---------------------------------------------------------------------------

class Phase1AContractError(RuntimeError):
    """Raised when the frozen Phase 1A surface does not match the contract."""


def _verify_1a_binding() -> None:
    provider_cls = getattr(_m1a, "MarketDataProvider", None)

    if not (
        inspect.isclass(provider_cls)
        and inspect.isabstract(provider_cls)
    ):
        raise Phase1AContractError(
            "MarketDataProvider abstract class not found"
        )

    for name in ("provider_id", "provider_name"):
        attr = inspect.getattr_static(provider_cls, name, None)
        if not isinstance(attr, property):
            raise Phase1AContractError(
                f"MarketDataProvider.{name} must be a property"
            )

    required_methods = (
        "supports_instrument",
        "to_provider_symbol",
        "to_howza_instrument",
        "to_provider_timeframe",
        "to_howza_timeframe",
        "get_source_records",
        "source_id_for",
        "health",
    )

    for name in required_methods:
        attr = inspect.getattr_static(provider_cls, name, None)
        if attr is None or not callable(attr):
            raise Phase1AContractError(
                f"MarketDataProvider.{name} missing or not callable"
            )

    for name in (
        "classify_freshness",
        "comparable_fields",
        "crypto_lifecycle",
    ):
        if not callable(getattr(_m1a, name, None)):
            raise Phase1AContractError(
                f"module-level {name} missing or not callable"
            )

    required_types = (
        "Candle",
        "SourceRecord",
        "FreshnessPolicy",
        "FreshnessClass",
        "ProviderHealth",
        "ProviderHealthStatus",
        "VerificationState",
        "QualityState",
        "SUPPORTED_INSTRUMENTS",
    )

    for name in required_types:
        if getattr(_m1a, name, None) is None:
            raise Phase1AContractError(
                f"{name} missing from howza_market_data"
            )

    expected = (
        "XAUUSD",
        "EURUSD",
        "GBPUSD",
        "BTCUSD",
        "NAS100",
        "US30",
        "DXY",
        "US10Y",
    )

    if tuple(_m1a.SUPPORTED_INSTRUMENTS) != expected:
        raise Phase1AContractError(
            "SUPPORTED_INSTRUMENTS vocabulary mismatch"
        )


_verify_1a_binding()


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

TRUSTED = "TRUSTED"
DEGRADED = "DEGRADED"
UNTRUSTED = "UNTRUSTED"

STATUSES = (TRUSTED, DEGRADED, UNTRUSTED)
CHECK_STATES = ("pass", "warn", "fail")

REFERENCE_EVALUATION_TIME = datetime(
    2026,
    1,
    15,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)

# Phase 1B-owned deterministic policy.
# These are NOT Phase 1A defaults.
_FRESH_SECONDS = 60.0
_AGING_SECONDS = 300.0
_STALE_SECONDS = 900.0
_POLICY_VERSION = "phase1b/v1"


# ---------------------------------------------------------------------------
# Deterministic offline fixture provider
# ---------------------------------------------------------------------------

class FixtureProvider(_m1a.MarketDataProvider):
    """Offline deterministic implementation used only by Phase 1B tests."""

    def __init__(
        self,
        health_status=None,
        volume: Optional[float] = 100.0,
        received_offset_seconds: float = 30.0,
    ):
        self._health_status = (
            health_status
            if health_status is not None
            else _m1a.ProviderHealthStatus.UP
        )
        self._volume = volume
        self._received_offset_seconds = received_offset_seconds

    @property
    def provider_id(self) -> str:
        return "fixture-offline"

    @property
    def provider_name(self) -> str:
        return "Phase 1B Fixture Provider"

    def to_provider_symbol(self, howza_instrument: str) -> str:
        return howza_instrument

    def to_howza_instrument(self, provider_symbol: str) -> str:
        return provider_symbol

    def to_provider_timeframe(self, howza_timeframe: str) -> str:
        return howza_timeframe

    def to_howza_timeframe(self, provider_timeframe: str) -> str:
        return provider_timeframe

    def source_id_for(
        self,
        howza_instrument: str,
        howza_timeframe: str,
    ) -> str:
        return (
            f"{self.provider_id}:"
            f"{howza_instrument}:"
            f"{howza_timeframe}"
        )

    def _build_candle(
        self,
        howza_instrument: str,
        howza_timeframe: str,
    ):
        source_id = self.source_id_for(
            howza_instrument,
            howza_timeframe,
        )

        received_at = (
            REFERENCE_EVALUATION_TIME
            - timedelta(seconds=self._received_offset_seconds)
        )

        return _m1a.Candle(
            instrument=howza_instrument,
            timeframe=howza_timeframe,
            open_time_utc=received_at - timedelta(minutes=1),
            close_time_utc=received_at,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=self._volume,
            is_closed=True,
            source_id=source_id,
            received_at_utc=received_at,
        )

    def get_source_records(
        self,
        howza_instrument: str,
        howza_timeframe: str,
        limit: int = 1,
    ) -> Tuple[Any, ...]:
        if limit < 1:
            return ()

        candle = self._build_candle(
            howza_instrument,
            howza_timeframe,
        )

        record = _m1a.SourceRecord(
            source_id=candle.source_id,
            provider_id=self.provider_id,
            instrument=howza_instrument,
            received_at_utc=candle.received_at_utc,
            candle=candle,
            raw_ref="fixture://offline",
        )

        return (record,)

    def health(self):
        return _m1a.ProviderHealth(
            provider_id=self.provider_id,
            status=self._health_status,
            at_utc=REFERENCE_EVALUATION_TIME,
            detail="deterministic offline fixture",
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check(state: str, detail: str) -> Dict[str, str]:
    if state not in CHECK_STATES:
        raise ValueError(f"invalid check state: {state}")
    return {
        "state": state,
        "detail": detail,
    }


def _utc_datetime(value: Any, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")

    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(
            f"{name} must be timezone

"""
HOWZA Phase 1A - C1 Canonical Schemas + C2 Market Data Interface.

Implementation version: phase1a-1.0.0
Lifecycle target: AUTHORED -> STATICALLY AUDITED -> EXECUTED -> TESTED -> VERIFIED

Architectural rules (locked):
- No network calls. No credentials. No secrets. No trading capability.
- No provider-specific detail leaks into the canonical model.
- volume UNKNOWN is represented explicitly (None) and never fabricated.
- Freshness thresholds live in versioned configuration, never in engine logic.
- All canonical records are immutable (frozen dataclasses).
- All timestamps are timezone-aware UTC; naive datetimes are rejected.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# C1 - Canonical schemas
# ---------------------------------------------------------------------------

class VerificationState(Enum):
    VERIFIED = "VERIFIED"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    DATA_CONFLICT = "DATA_CONFLICT"
    STALE = "STALE"
    INVALID = "INVALID"
    NO_DATA = "NO_DATA"

class QualityState(Enum):
    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNUSABLE = "UNUSABLE"

class FreshnessClass(Enum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"

class ProviderHealthStatus(Enum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"

# HOWZA-owned canonical instrument identifiers (Phase 1 scope).
SUPPORTED_INSTRUMENTS: Tuple[str,...] = (
    "XAUUSD", "EURUSD", "GBPUSD", "BTCUSD",
    "NAS100", "US30", "DXY", "US10Y",
)

def _require_aware_utc(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must be timezone-aware (UTC); naive datetime rejected")
    return value.astimezone(timezone.utc)

def _require_number(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
    v = float(value)
    if v!= v or v in (float("inf"), float("-inf")): # NaN / inf rejected
        raise ValueError(f"{name} must be finite, got {value!r}")
    return v

@dataclass(frozen=True)
class Candle:
    """Canonical HOWZA candle. volume=None means UNKNOWN (explicit, never fabricated)."""
    instrument: str
    timeframe: str
    open_time_utc: datetime
    close_time_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] # None == UNKNOWN
    is_closed: bool
    source_id: str
    received_at_utc: datetime

    def __post_init__(self):
        if self.instrument not in SUPPORTED_INSTRUMENTS:
            raise ValueError(f"unknown HOWZA instrument: {self.instrument!r}")
        if not self.timeframe or not isinstance(self.timeframe, str):
            raise ValueError("timeframe must be a non-empty string")
        ot = _require_aware_utc("open_time_utc", self.open_time_utc)
        ct = _require_aware_utc("close_time_utc", self.close_time_utc)
        if not ot < ct:
            raise ValueError("open_time_utc must be strictly before close_time_utc")
        o = _require_number("open", self.open)
        h = _require_number("high", self.high)
        lo = _require_number("low", self.low)
        c = _require_number("close", self.close)
        if h < max(o, c):
            raise ValueError(f"impossible OHLC: high {h} < max(open, close)")
        if lo > min(o, c):
            raise ValueError(f"impossible OHLC: low {lo} > min(open, close)")
        if self.volume is not None:
            v = _require_number("volume", self.volume)
            if v < 0:
                raise ValueError("volume must be >= 0 or None (UNKNOWN)")
        if not isinstance(self.is_closed, bool):
            raise TypeError("is_closed must be bool")
        if not self.source_id or not isinstance(self.source_id, str):
            raise ValueError("source_id must be a non-empty string")
        _require_aware_utc("received_at_utc", self.received_at_utc)
        # Normalize to stored canonical forms.
        object.__setattr__(self, "open_time_utc", ot)
        object.__setattr__(self, "close_time_utc", ct)
        object.__setattr__(self, "open", o)
        object.__setattr__(self, "high", h)
        object.__setattr__(self, "low", lo)
        object.__setattr__(self, "close", c)

    @property
    def has_volume(self) -> bool:
        return self.volume is not None

@dataclass(frozen=True)
class SourceRecord:
    """One provider observation, with provenance. Raw payload is referenced, not embedded."""
    source_id: str
    provider_id: str
    instrument: str
    received_at_utc: datetime
    candle: Candle
    raw_ref: str = "" # opaque pointer to quarantined raw bytes; never the payload itself

    def __post_init__(self):
        if not self.source_id or not isinstance(self.source_id, str):
            raise ValueError("source_id must be a non-empty string")
        if not self.provider_id or not isinstance(self.provider_id, str):

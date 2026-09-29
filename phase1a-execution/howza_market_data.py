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
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple

# [STRIPPED 75 bytes]
# C1 - Canonical schemas
# [STRIPPED 75 bytes]

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
            raise ValueError("provider_id must be a non-empty string")
        if self.candle.instrument!= self.instrument:
            raise ValueError("SourceRecord.instrument must match candle.instrument")
        _require_aware_utc("received_at_utc", self.received_at_utc)

@dataclass(frozen=True)
class ConflictRecord:
    """Preserved evidence of a source conflict. Values stored as strings to avoid
    float-repr ambiguity across providers."""
    instrument: str
    conflicting_fields: Tuple[str,...]
    observations: Tuple[Tuple[str, str],...] # (source_id, value_repr) pairs
    detected_at_utc: datetime
    tolerance_policy_ref: str = ""

    def __post_init__(self):
        if self.instrument not in SUPPORTED_INSTRUMENTS:
            raise ValueError(f"unknown HOWZA instrument: {self.instrument!r}")
        if not self.conflicting_fields:
            raise ValueError("conflicting_fields must be non-empty")
        if len(self.observations) < 2:
            raise ValueError("a conflict requires at least two observations")
        _require_aware_utc("detected_at_utc", self.detected_at_utc)

@dataclass(frozen=True)
class TimeframeState:
    timeframe: str
    verification_state: VerificationState
    candle_count: int
    latest_close_time_utc: Optional[datetime] = None

    def __post_init__(self):
        if self.candle_count < 0:
            raise ValueError("candle_count must be >= 0")
        if self.latest_close_time_utc is not None:
            _require_aware_utc("latest_close_time_utc", self.latest_close_time_utc)

@dataclass(frozen=True)
class TrustedMarketState:
    """Canonical trusted market state. trusted_price=None is valid and means
    'no trustworthy price' (NO_DATA / INVALID); it is never fabricated."""
    instrument: str
    as_of_utc: datetime
    trusted_price: Optional[float]
    price_source: Optional[str]
    sources: Tuple[str,...]
    verification_state: VerificationState
    quality_state: QualityState
    freshness_seconds: Optional[float]
    conflicts: Tuple[ConflictRecord,...] = ()
    missing_fields: Tuple[str,...] = ()
    last_verified_state: Optional["TrustedMarketState"] = None
    downgrade_reason: Optional[str] = None
    evidence_refs: Tuple[str,...] = ()
    timeframe_states: Tuple[TimeframeState,...] = ()

    def __post_init__(self):
        if self.instrument not in SUPPORTED_INSTRUMENTS:
            raise ValueError(f"unknown HOWZA instrument: {self.instrument!r}")
        _require_aware_utc("as_of_utc", self.as_of_utc)
        if self.trusted_price is not None:
            _require_number("trusted_price", self.trusted_price)
        if self.verification_state in (VerificationState.NO_DATA, VerificationState.INVALID):
            if self.trusted_price is not None:
                raise ValueError(
                    f"trusted_price must be None when verification_state is "
                    f"{self.verification_state.value} (never fabricate)"
                )
        if not isinstance(self.verification_state, VerificationState):
            raise TypeError("verification_state must be a VerificationState")
        if not isinstance(self.quality_state, QualityState):
            raise TypeError("quality_state must be a QualityState")
        if self.freshness_seconds is not None and self.freshness_seconds < 0:
            raise ValueError("freshness_seconds must be >= 0 or None")

@dataclass(frozen=True)
class FreshnessPolicy:
    """Versioned, configuration-driven freshness thresholds.
    C6 (freshness engine, Phase 1C) consumes this; it invents nothing."""
    instrument: str
    timeframe: str
    fresh_seconds: float
    aging_seconds: float
    stale_seconds: float
    policy_version: str

    def __post_init__(self):
        if self.instrument not in SUPPORTED_INSTRUMENTS:
            raise ValueError(f"unknown HOWZA instrument: {self.instrument!r}")
        if not self.timeframe or not isinstance(self.timeframe, str):
            raise ValueError("timeframe must be a non-empty string")
        for name in ("fresh_seconds", "aging_seconds", "stale_seconds"):
            v = _require_number(name, getattr(self, name))
            if v < 0:
                raise ValueError(f"{name} must be >= 0")
        if not (self.fresh_seconds <= self.aging_seconds <= self.stale_seconds):
            raise ValueError("thresholds must satisfy fresh_seconds <= aging_seconds <= stale_seconds")
        if not self.policy_version or not isinstance(self.policy_version, str):
            raise ValueError("policy_version must be a non-empty version string")

def classify_freshness(policy: FreshnessPolicy, age_seconds: float) -> FreshnessClass:
    """Pure function. Thresholds come ONLY from the passed policy (locked decision 2)."""
    if not isinstance(policy, FreshnessPolicy):
        raise TypeError("policy must be a FreshnessPolicy")
    age = _require_number("age_seconds", age_seconds)
    if age < 0:
        raise ValueError("age_seconds must be >= 0")
    if age <= policy.fresh_seconds:
        return FreshnessClass.FRESH
    if age <= policy.aging_seconds:
        return FreshnessClass.AGING
    return FreshnessClass.STALE

# Fields eligible for cross-source conflict comparison. Volume is compared ONLY
# when every compared source reports a known volume (locked decision 1).
COMPARABLE_PRICE_FIELDS: Tuple[str,...] = ("open", "high", "low", "close")

def comparable_fields(candles: Tuple[Candle,...]) -> Tuple[str,...]:
    """Return the fields that are available and comparable across all candles.
    Volume is included only if no candle reports UNKNOWN."""
    fields = list(COMPARABLE_PRICE_FIELDS)
    if all(c.has_volume for c in candles):
        fields.append("volume")
    return tuple(fields)

# [STRIPPED 75 bytes]
# C2 - HOWZA-owned Market Data Interface
# [STRIPPED 75 bytes]

@dataclass(frozen=True)
class ProviderHealth:
    provider_id: str
    status: ProviderHealthStatus
    at_utc: datetime
    detail: str = ""

    def __post_init__(self):
        _require_aware_utc("at_utc", self.at_utc)
        if not isinstance(self.status, ProviderHealthStatus):
            raise TypeError("status must be a ProviderHealthStatus")

class ProviderError(Exception):
    """Base for all provider-side error states surfaced through the interface."""
    def __init__(self, provider_id: str, code: str, message: str):
        super().__init__(f"[{provider_id}] {code}: {message}")
        self.provider_id = provider_id
        self.code = code

class MarketDataProvider(abc.ABC):
    """HOWZA-owned provider contract. Adapters implement this; HOWZA consumes this.

    The interface assumes NOTHING about vendor, API, symbol naming, auth,
    database, or network protocol. Provider-specific detail stays behind the
    adapter boundary.
    """

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:...

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:...

    # -- instrument mapping (HOWZA identity!= provider symbol) ----------------
    @abc.abstractmethod
    def to_provider_symbol(self, howza_instrument: str) -> str:...

    @abc.abstractmethod
    def to_howza_instrument(self, provider_symbol: str) -> str:...

    # -- timeframe mapping ----------------------------------------------------
    @abc.abstractmethod
    def to_provider_timeframe(self, howza_timeframe: str) -> str:...

    @abc.abstractmethod
    def to_howza_timeframe(self, provider_timeframe: str) -> str:...

    # -- market-data retrieval ------------------------------------------------
    @abc.abstractmethod
    def get_source_records(self, howza_instrument: str, howza_timeframe: str,
                           limit: int = 1) -> Tuple[SourceRecord,...]:
        """Return provider observations as canonical SourceRecords with provenance."""

    # -- source identity / provenance -----------------------------------------
    @abc.abstractmethod
    def source_id_for(self, howza_instrument: str, howza_timeframe: str) -> str:...

    # -- provider health ------------------------------------------------------
    @abc.abstractmethod
    def health(self) -> ProviderHealth:...

    # -- capability declaration (HOWZA-owned, safe default) -------------------
    def supports_instrument(self, howza_instrument: str) -> bool:
        return howza_instrument in SUPPORTED_INSTRUMENTS

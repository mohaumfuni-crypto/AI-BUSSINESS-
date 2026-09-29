"""HOWZA Phase 1A behavioural tests. Targets howza_market_data.py (commit 1c42948)."""
import dataclasses
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from howza_market_data import (
    SUPPORTED_INSTRUMENTS,
    Candle,
    ConflictRecord,
    FreshnessClass,
    FreshnessPolicy,
    MarketDataProvider,
    ProviderError,
    ProviderHealth,
    ProviderHealthStatus,
    QualityState,
    SourceRecord,
    TimeframeState,
    TrustedMarketState,
    VerificationState,
    classify_freshness,
    comparable_fields,
)

def _now():
    return datetime.now(timezone.utc)

def _mk_candle(**kw):
    d = dict(
        instrument="XAUUSD", timeframe="M5",
        open_time_utc=_now() - timedelta(minutes=1), close_time_utc=_now(),
        open=100.0, high=101.0, low=99.0, close=100.5, volume=None,
        is_closed=True, source_id="prov-a:XAUUSD:M5", received_at_utc=_now(),
    )
    d.update(kw)
    return Candle(**d)

class MockProvider(MarketDataProvider):
    def __init__(s, pid, price, volume=None, delay=0.0):
        s._pid, s._price, s._vol, s._delay = pid, price, volume, delay

    @property
    def provider_id(s):
        return s._pid

    @property
    def provider_name(s):
        return "Mock " + s._pid

    def to_provider_symbol(s, i):
        if i not in SUPPORTED_INSTRUMENTS:
            raise ValueError(i)
        return "MOCK:" + i

    def to_howza_instrument(s, p):
        i = p.split(":", 1)[1]
        if i not in SUPPORTED_INSTRUMENTS:
            raise ValueError(p)
        return i

    def to_provider_timeframe(s, t):
        return "tf-" + t

    def to_howza_timeframe(s, t):
        if not t.startswith("tf-"):
            raise ValueError(t)
        return t[3:]

    def get_source_records(s, i, t, limit=1):
        n = _now() - timedelta(seconds=s._delay)
        c = _mk_candle(
            instrument=i, timeframe=t, open=s._price, high=s._price,
            low=s._price, close=s._price, volume=s._vol,
            open_time_utc=n - timedelta(minutes=1), close_time_utc=n,
            received_at_utc=n, source_id=s.source_id_for(i, t),
        )
        return tuple(
            SourceRecord(source_id=c.source_id, provider_id=s._pid,
                         instrument=i, received_at_utc=n, candle=c)
            for _ in range(limit)
        )

    def source_id_for(s, i, t):
        return s._pid + ":" + i + ":" + t

    def health(s):
        return ProviderHealth(provider_id=s._pid,
                              status=ProviderHealthStatus.UP, at_utc=_now())

def _mk_state(**kw):
    d = dict(instrument="EURUSD", as_of_utc=_now(), trusted_price=None,
             price_source=None, sources=(),
             verification_state=VerificationState.NO_DATA,
             quality_state=QualityState.CRITICAL, freshness_seconds=None)
    d.update(kw)
    return TrustedMarketState(**d)

def _mk_conflict():
    return ConflictRecord(
        instrument="EURUSD", conflicting_fields=("close",),
        observations=(("prov-a", "100.0"), ("prov-b", "100.5")),
        detected_at_utc=_now(),
    )

def test_instruments():
    assert SUPPORTED_INSTRUMENTS == (
        "XAUUSD", "EURUSD", "GBPUSD", "BTCUSD",
        "NAS100", "US30", "DXY", "US10Y",
    )
    p = MockProvider("p", 1.0)
    for i in SUPPORTED_INSTRUMENTS:
        assert p.supports_instrument(i)

def test_unknown_instrument():
    with pytest.raises(ValueError):
        _mk_candle(instrument="FAKE")
    with pytest.raises(ValueError):
        MockProvider("p", 1.0).to_provider_symbol("FAKE")
    assert not MockProvider("p", 1.0).supports_instrument("FAKE")

def test_naive_rejected():
    with pytest.raises(ValueError):
        _mk_candle(open_time_utc=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        _mk_candle(received_at_utc=datetime(2026, 1, 1, 12, 0, 0))

def test_aware_normalized():
    aware = datetime(2026, 1, 1, 12, 0, 0,
                     tzinfo=timezone(timedelta(hours=2)))
    c = _mk_candle(open_time_utc=aware,
                   close_time_utc=aware + timedelta(minutes=1))
    assert c.open_time_utc.tzinfo == timezone.utc
    assert c.open_time_utc.hour == 10

def test_impossible_ohlc():
    with pytest.raises(ValueError):
        _mk_candle(high=50.0)
    with pytest.raises(ValueError):
        _mk_candle(low=150.0)

def test_nan_inf():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            _mk_candle(close=bad)

def test_bool_rejected():
    with pytest.raises(TypeError):
        _mk_candle(open=True)
    with pytest.raises(TypeError):
        _mk_candle(is_closed=1)

def test_frozen():
    c = _mk_candle()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.close = 1.0
    s = _mk_state(verification_state=VerificationState.VERIFIED,
                  quality_state=QualityState.NOMINAL, trusted_price=1.0,
                  price_source="p", sources=("p",), freshness_seconds=1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.trusted_price = 2.0

def test_volume_unknown():
    c = _mk_candle(volume=None)
    assert c.volume is None and not c.has_volume

def test_no_fabricated_volume():
    a = _mk_candle(volume=None)
    b = _mk_candle(volume=10.0)
    assert "volume" not in comparable_fields((a,))
    assert "volume" in comparable_fields((b, _mk_candle(volume=5.0)))

def test_policy_validation():
    ok = dict(instrument="XAUUSD", timeframe="M1", fresh_seconds=30.0,
              aging_seconds=120.0, stale_seconds=300.0,
              policy_version="2026-09-29")
    FreshnessPolicy(**ok)
    with pytest.raises(ValueError):
        FreshnessPolicy(**dict(ok, aging_seconds=10.0))
    with pytest.raises(ValueError):
        FreshnessPolicy(**dict(ok, policy_version=""))

def test_freshness_boundaries():
    p = FreshnessPolicy(instrument="XAUUSD", timeframe="M1",
                        fresh_seconds=30.0, aging_seconds=120.0,
                        stale_seconds=300.0, policy_version="v1")
    assert classify_freshness(p, 0.0) is FreshnessClass.FRESH
    assert classify_freshness(p, 30.0) is FreshnessClass.FRESH
    assert classify_freshness(p, 31.0) is FreshnessClass.AGING
    assert classify_freshness(p, 120.0) is FreshnessClass.AGING
    assert classify_freshness(p, 121.0) is FreshnessClass.STALE
    assert classify_freshness(p, 3600.0) is FreshnessClass.STALE
    with pytest.raises(ValueError):
        classify_freshness(p, -1.0)
    with pytest.raises(TypeError):
        classify_freshness("x", 1.0)

def test_no_data_no_price():
    _mk_state()
    with pytest.raises(ValueError):
        _mk_state(trusted_price=1.0)

def test_invalid_no_price():
    with pytest.raises(ValueError):
        _mk_state(verification_state=VerificationState.INVALID,
                  trusted_price=1.0)

def test_conflict_needs_two():
    with pytest.raises(ValueError):
        ConflictRecord(instrument="EURUSD", conflicting_fields=("close",),
                       observations=(("prov-a", "100.0"),),
                       detected_at_utc=_now())
    with pytest.raises(ValueError):
        ConflictRecord(instrument="EURUSD", conflicting_fields=(),
                       observations=(("a", "1"), ("b", "2")),
                       detected_at_utc=_now())

def test_conflict_no_price():
    s = _mk_state(verification_state=VerificationState.DATA_CONFLICT,
                  quality_state=QualityState.DEGRADED,
                  sources=("prov-a", "prov-b"), conflicts=(_mk_conflict(),),
                  freshness_seconds=1.0)
    assert s.trusted_price is None and len(s.conflicts) == 1

def test_abstract_blocked():
    with pytest.raises(TypeError):
        MarketDataProvider()

def test_interchangeable():
    a, b = MockProvider("prov-a", 2680.50), MockProvider("prov-b", 2680.50)
    ra = a.get_source_records("XAUUSD", "M5")[0]
    rb = b.get_source_records("XAUUSD", "M5")[0]
    assert ra.candle.close == rb.candle.close
    s = _mk_state(instrument="XAUUSD", trusted_price=ra.candle.close,
                  price_source="median", sources=("prov-a", "prov-b"),
                  verification_state=VerificationState.VERIFIED,
                  quality_state=QualityState.NOMINAL, freshness_seconds=0.5)
    assert s.verification_state is VerificationState.VERIFIED

def test_conversions():
    p = MockProvider("prov-a", 1.0)
    assert p.to_howza_instrument(p.to_provider_symbol("XAUUSD")) == "XAUUSD"
    assert p.to_howza_timeframe(p.to_provider_timeframe("M5")) == "M5"
    assert p.source_id_for("XAUUSD", "M5") == "prov-a:XAUUSD:M5"
    recs = p.get_source_records("XAUUSD", "M5", limit=3)
    assert isinstance(recs, tuple) and len(recs) == 3
    assert all(isinstance(r, SourceRecord) for r in recs)

def test_health_error():
    p = MockProvider("prov-a", 1.0)
    h = p.health()
    assert h.status is ProviderHealthStatus.UP
    assert h.provider_id == "prov-a" and h.detail == ""
    e = ProviderError("prov-a", "TIMEOUT", "slow")
    assert e.code == "TIMEOUT" and e.provider_id == "prov-a"
    assert "TIMEOUT" in str(e)

def test_no_network_no_secrets():
    import howza_market_data as m
    src = inspect.getsource(m).lower()
    for token in ("socket", "urllib", "requests", "http://", "https://",
                  "api_key", "password", "subprocess", "place_order"):
        assert token not in src, token

⁶"""HOWZA Phase 1B behavioural and contract tests."""

from __future__ import annotations

import inspect
import sys
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PHASE1A_DIR = ROOT / "phase1a-execution"

if str(PHASE1A_DIR) not in sys.path:
    sys.path.insert(0, str(PHASE1A_DIR))

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import howza_market_data as m1a
from howza_trusted_feed import (
    DEGRADED,
    TRUSTED,
    UNTRUSTED,
    FixtureProvider,
    REFERENCE_EVALUATION_TIME,
    check_frozen_interfaces,
    check_source_record_schema,
    trust_lifecycle,
    trust_snapshot,
)


def fresh_snapshot(
    provider=None,
    instrument="XAUUSD",
    timeframe="1m",
):
    if provider is None:
        provider = FixtureProvider()

    return trust_snapshot(
        provider,
        instrument,
        timeframe,
        evaluated_at=REFERENCE_EVALUATION_TIME,
    )


def test_phase1a_names_bind_with_required_kinds():
    provider_cls = m1a.MarketDataProvider

    assert inspect.isclass(provider_cls)
    assert inspect.isabstract(provider_cls)

    assert isinstance(
        inspect.getattr_static(provider_cls, "provider_id"),
        property,
    )
    assert isinstance(
        inspect.getattr_static(provider_cls, "provider_name"),
        property,
    )

    for name in (
        "supports_instrument",
        "to_provider_symbol",
        "to_howza_instrument",
        "to_provider_timeframe",
        "to_howza_timeframe",
        "get_source_records",
        "source_id_for",
        "health",
    ):
        assert callable(inspect.getattr_static(provider_cls, name))

    for name in (
        "classify_freshness",
        "comparable_fields",
        "crypto_lifecycle",
    ):
        assert callable(getattr(m1a, name))

    for name in (
        "Candle",
        "SourceRecord",
        "FreshnessPolicy",
        "FreshnessClass",
        "ProviderHealth",
        "ProviderHealthStatus",
        "SUPPORTED_INSTRUMENTS",
    ):
        assert getattr(m1a, name, None) is not None


def test_direct_market_data_provider_construction_fails():
    with pytest.raises(TypeError):
        m1a.MarketDataProvider()


def test_fixture_provider_is_valid_market_data_provider():
    provider = FixtureProvider()

    assert isinstance(provider, m1a.MarketDataProvider)
    assert provider.provider_id
    assert provider.provider_name


def test_trust_lifecycle_zero_argument_returns_valid_dict():
    result = trust_lifecycle()

    assert isinstance(result, dict)
    assert result["status"] in {
        TRUSTED,
        DEGRADED,
        UNTRUSTED,
    }


def test_snapshot_contains_exact_required_keys():
    result = fresh_snapshot()

    assert set(result.keys()) == {
        "status",
        "checks",
        "errors",
        "evaluated_at",
        "provider_id",
        "symbol",
        "timeframe",
    }


def test_every_check_has_valid_state_and_detail():
    result = fresh_snapshot()

    assert isinstance(result["checks"], dict)

    for check_name, check in result["checks"].items():
        assert isinstance(check_name, str)
        assert set(check.keys()) == {"state", "detail"}
        assert check["state"] in {"pass", "warn", "fail"}
        assert isinstance(check["detail"], str)


def test_healthy_fresh_fixture_is_trusted():
    result = fresh_snapshot()

    assert result["status"] == TRUSTED
    assert result["errors"] == []


def test_fixture_symbol_mapping_is_deterministic():
    provider = FixtureProvider()

    assert provider.to_provider_symbol("XAUUSD") == "XAUUSD"
    assert provider.to_howza_instrument("XAUUSD") == "XAUUSD"


def test_fixture_timeframe_mapping_is_deterministic():
    provider = FixtureProvider()

    assert provider.to_provider_timeframe("1m") == "1m"
    assert provider.to_howza_timeframe("1m") == "1m"


def test_fixture_source_record_has_valid_schema():
    provider = FixtureProvider()

    records = provider.get_source_records(
        "XAUUSD",
        "1m",
        limit=1,
    )

    assert len(records) == 1

    result = check_source_record_schema(records[0])

    assert result["passed"] is True
    assert result["missing"] == []
    assert result["candle_missing"] == []


def test_fixture_health_is_up():
    provider = FixtureProvider()
    health = provider.health()

    assert health.provider_id == provider.provider_id
    assert health.status == m1a.ProviderHealthStatus.UP


def test_check_frozen_interfaces_passes():
    result = check_frozen_interfaces()

    assert result["passed"] is True
    assert result["details"]["MarketDataProvider"] is True
    assert result["details"]["trust_lifecycle"] is True


def test_stale_fixture_is_untrusted():
    provider = FixtureProvider()

    evaluated_at = (
        REFERENCE_EVALUATION_TIME
        + timedelta(seconds=POLICY_STALE_PLUS_ONE)
    )

    result = trust_snapshot(
        provider,
        "XAUUSD",
        "1m",
        evaluated_at=evaluated_at,
    )

    assert result["status"] == UNTRUSTED


def test_aging_fixture_is_degraded():
    provider = FixtureProvider()

    evaluated_at = (
        REFERENCE_EVALUATION_TIME
        + timedelta(seconds=POLICY_AGING_PLUS_ONE)
    )

    result = trust_snapshot(
        provider,
        "XAUUSD",
        "1m",
        evaluated_at=evaluated_at,
    )

    assert result["status"] == DEGRADED


def test_future_timestamp_is_untrusted():
    provider = FixtureProvider()

    evaluated_at = (
        REFERENCE_EVALUATION_TIME
        - timedelta(seconds=1)
    )

    result = trust_snapshot(
        provider,
        "XAUUSD",
        "1m",
        evaluated_at=evaluated_at,
    )

    assert result["status"] == UNTRUSTED


def test_unsupported_instrument_is_untrusted():
    provider = FixtureProvider()

    result = fresh_snapshot(
        provider=provider,
        instrument="NOT_REAL",
        timeframe="1m",
    )

    assert result["status"] == UNTRUSTED


def test_lifecycle_is_categorical_only():
    result = trust_lifecycle()

    assert result["categorical_only"] is True
    assert result["numeric_trust_score"] is False


def test_fixture_source_id_is_stable():
    provider = FixtureProvider()

    first = provider.source_id_for("XAUUSD", "1m")
    second = provider.source_id_for("XAUUSD", "1m")

    assert first == second
    assert first == "phase1b-fixture:XAUUSD:1m"
def test_lifecycle_reports_phase_1b():
    result = trust_lifecycle()
    assert result["phase"] == "1B"


def test_lifecycle_contains_required_lifecycle_string():
    result = trust_lifecycle()
    assert result["lifecycle"] == (
        "AUTHORED -> STATICALLY AUDITED -> "
        "EXECUTED -> TESTED -> VERIFIED"
    )


def test_snapshot_identifies_fixture_provider():
    result = fresh_snapshot()
    assert result["provider_id"] == "phase1b-fixture"
    assert result["symbol"] == "XAUUSD"
    assert result["timeframe"] == "1m"


def test_snapshot_evaluation_time_is_utc():
    result = fresh_snapshot()
    assert result["evaluated_at"].tzinfo is not None
    assert result["evaluated_at"].utcoffset() == timedelta(0)

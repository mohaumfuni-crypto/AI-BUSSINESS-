"""HOWZA Phase 1B behavioural and contract tests."""

from datetime import timedelta

import pytest

import howza_trusted_feed as tf
from howza_market_data import (
    FreshnessClass,
    FreshnessPolicy,
    MarketDataProvider,
    ProviderHealth,
    ProviderHealthStatus,
    SUPPORTED_INSTRUMENTS,
    classify_freshness,
)


def test_phase1a_names_bind_with_required_kinds():
    assert "BTCUSD" in SUPPORTED_INSTRUMENTS
    assert FreshnessClass.FRESH.value == "FRESH"
    assert ProviderHealthStatus.UP.value == "UP"


def test_direct_market_data_provider_construction_fails():
    with pytest.raises(TypeError):
        MarketDataProvider()


def test_fixture_provider_is_valid_market_data_provider():
    provider = tf.FixtureProvider()
    assert isinstance(provider, MarketDataProvider)
    assert provider.provider_id == "phase1b-fixture"


def test_trust_lifecycle_zero_argument_returns_valid_dict():
    result = tf.trust_lifecycle()
    assert isinstance(result, dict)
    assert result["phase"] == "1B"


def test_snapshot_contains_exact_required_keys():
    result = tf.trust_snapshot()
    required = {
        "provider_id",
        "symbol",
        "timeframe",
        "evaluated_at",
        "overall_state",
        "checks",
    }
    assert required.issubset(result.keys())


def test_every_check_has_valid_state_and_detail():
    result = tf.trust_snapshot()
    assert result["checks"]

    for check in result["checks"].values():
        assert check["state"] in {"pass", "warn", "fail"}
        assert isinstance(check["detail"], str)
        assert check["detail"]


def test_healthy_fresh_fixture_is_trusted():
    result = tf.trust_snapshot()
    assert result["overall_state"] == "TRUSTED"


def test_fixture_provider_symbol_mapping_is_stable():
    provider = tf.FixtureProvider()
    assert provider.to_provider_symbol("BTCUSD") == "BTCUSD"
    assert provider.to_howza_instrument("BTCUSD") == "BTCUSD"


def test_fixture_provider_timeframe_mapping_is_stable():
    provider = tf.FixtureProvider()
    assert provider.to_provider_timeframe("1m") == "1m"
    assert provider.to_howza_timeframe("1m") == "1m"


def test_fixture_provider_source_id_is_stable():
    provider = tf.FixtureProvider()
    source_id = provider.source_id_for("BTCUSD", "1m")
    assert isinstance(source_id, str)
    assert source_id


def test_fixture_provider_health_is_up():
    provider = tf.FixtureProvider()
    health = provider.health()
    assert isinstance(health, ProviderHealth)
    assert health.status is ProviderHealthStatus.UP


def test_freshness_policy_classifies_fixture_as_fresh():
    policy = FreshnessPolicy(
        instrument="BTCUSD",
        timeframe="1m",
        fresh_seconds=60,
        aging_seconds=300,
        stale_seconds=900,
        policy_version="phase1b-fixture-v1",
    )
    assert classify_freshness(policy, 30) is FreshnessClass.FRESH


def test_freshness_policy_classifies_aging_data():
    policy = FreshnessPolicy(
        instrument="BTCUSD",
        timeframe="1m",
        fresh_seconds=60,
        aging_seconds=300,
        stale_seconds=900,
        policy_version="phase1b-fixture-v1",
    )
    assert classify_freshness(policy, 120) is FreshnessClass.AGING


def test_freshness_policy_classifies_stale_data():
    policy = FreshnessPolicy(
        instrument="BTCUSD",
        timeframe="1m",
        fresh_seconds=60,
        aging_seconds=300,
        stale_seconds=900,
        policy_version="phase1b-fixture-v1",
    )
    assert classify_freshness(policy, 901) is FreshnessClass.STALE


def test_lifecycle_reports_phase_1b():
    result = tf.trust_lifecycle()
    assert result["phase"] == "1B"


def test_lifecycle_contains_required_lifecycle_string():
    result = tf.trust_lifecycle()
    assert result["lifecycle"] == (
        "AUTHORED -> STATICALLY AUDITED -> "
        "EXECUTED -> TESTED -> VERIFIED"
    )


def test_snapshot_identifies_fixture_provider():
    result = tf.trust_snapshot()
    assert result["provider_id"] == "phase1b-fixture"
    assert result["symbol"] == "XAUUSD"
    assert result["timeframe"] == "1m"


def test_snapshot_evaluation_time_is_utc():
    result = tf.trust_snapshot()
    assert result["evaluated_at"].tzinfo is not None
    assert result["evaluated_at"].utcoffset() == timedelta(0)

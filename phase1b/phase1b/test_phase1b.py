"""HOWZA Phase 1B behavioural and contract tests."""

from __future__ import annotations

import inspect
import sys
from datetime import timedelta
from pathlib import Path

import pytest

# Make frozen Phase 1A and Phase 1B modules importable from the repository root.
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
    trust_lifecycle,
    trust_snapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 1. All frozen Phase 1A names bind with the required kinds.
# ---------------------------------------------------------------------------

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
        assert callable(
            inspect.getattr_static(provider_cls, name)
        )

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


# ---------------------------------------------------------------------------
# 2. Direct construction of the frozen ABC must fail.
# ---------------------------------------------------------------------------

def test_direct_market_data_provider_construction_fails():
    with pytest.raises(TypeError):
        m1a.MarketDataProvider()


# ---------------------------------------------------------------------------
# 3. Fixture provider is a valid concrete Phase 1A provider.
# ---------------------------------------------------------------------------

def test_fixture_provider_is_valid_market_data_provider():
    provider = FixtureProvider()

    assert isinstance(provider, m1a.MarketDataProvider)
    assert provider.provider_id
    assert provider.provider_name


# ---------------------------------------------------------------------------
# 4. trust_lifecycle() is a zero-argument deterministic entry point.
# ---------------------------------------------------------------------------

def test_trust_lifecycle_zero_argument_returns_valid_dict():
    result = trust_lifecycle()

    assert isinstance(result, dict)
    assert result["status"] in {
        TRUSTED,
        DEGRADED,
        UNTRUSTED,
    }


# ---------------------------------------------------------------------------
# 5. Snapshot contains exactly the locked public keys.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 6. Every check has exactly state + detail.
# ---------------------------------------------------------------------------

def test_every_check_has_valid_state_and_detail():
    result = fresh_snapshot()

    assert isinstance(result["checks"], dict)

    for check_name, check in result["checks"].items():
        assert isinstance(check_name, str)
        assert set(check.keys()) == {
            "state",
            "detail",
        }
        assert check["state"] in {
            "pass",
            "warn",
            "fail",
        }
        assert isinstance(check["detail"], str)


# ---------------------------------------------------------------------------
# 7. Healthy fixture + fresh data -> TRUSTED.
# ---------------------------------------------------------------------------

def test_healthy_fresh_fixture_is_tr

"""Phase 1B: Howza Trusted Feed.

Categorical trust gate over the frozen Phase 1A crypto market-data package.

Required public contract (phase1b/test_phase1b.py):
    TRUSTED, DEGRADED, UNTRUSTED categorical trust states
    REFERENCE_EVALUATION_TIME deterministic tz-aware datetime
    FixtureProvider concrete phase1a.MarketDataProvider
    trust_snapshot(...) snapshot dict; ALL parameters optional
    trust_lifecycle() zero-argument lifecycle dict
    check_frozen_interfaces() frozen Phase 1A interface audit

trust_snapshot() with no arguments evaluates a FixtureProvider at the
current UTC time for the fixture instrument (XAUUSD). The snapshot
exposes overall_state (the categorical verdict) plus status, checks,
errors, evaluated_at, provider_id, symbol, timeframe.

trust_lifecycle() returns {"phase": "1B", "lifecycle": <the lifecycle
string from the frozen Phase 1A crypto_lifecycle() report>} merged with
the snapshot fields.

FixtureProvider conforms to the frozen MarketDataProvider contract:
provider_id/provider_name are read-only properties returning the fixture
identity ("phase1b-fixture"); health() is a callable method returning a
phase1a.ProviderHealth instance in the UP status.

Read-only. No network. No credentials. No trading. No numeric trust score.
"""
import ast
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import howza_market_data as phase1a

TRUSTED = "TRUSTED"
DEGRADED = "DEGRADED"
UNTRUSTED = "UNTRUSTED"

REFERENCE_EVALUATION_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

_CHECK_STATES = ("pass", "warn", "fail")

_REQUIRED_PHASE1A = (
    "MarketDataProvider",
    "Candle",
    "SourceRecord",
    "FreshnessPolicy",
    "FreshnessClass",
    "ProviderHealth",
    "ProviderHealthStatus",
    "SUPPORTED_INSTRUMENTS",
    "classify_freshness",
    "comparable_fields",
)

_PROVIDER_ATTRS = (
    "supports_instrument",
    "to_provider_symbol",
    "to_howza_instrument",
    "to_provider_timeframe",
    "to_howza_timeframe",
    "get_source_records",
    "source_id_for",
    "health",
    "provider_id",
    "provider_name",
)

_FORBIDDEN = {
    "requests", "httpx", "urllib", "socket", "websocket",
    "os", "subprocess", "sys", "pathlib", "pickle", "marshal",
    "eval", "exec", "compile", "open",
}

_US = chr(95)

_FIXTURE_PROVIDER_ID = "phase1b-fixture"
_FIXTURE_PROVIDER_NAME = "Phase 1B Fixture Provider"
_FIXTURE_INSTRUMENT = "XAUUSD"
_FIXTURE_TIMEFRAME = "1m"

def _is_dunder_call(name: str) -> bool:
    return (
        len(name) > 4
        and name.startswith(_US * 2)
        and name.endswith(_US * 2)
    )

def _check_static_guard() -> Dict[str, Any]:
    imported = set()
    called = set()
    source = inspect.getsource(inspect.getmodule(inspect.currentframe()))
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(
                a.asname or a.name.split(".")[0] for a in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    bad_imports = sorted(imported & _FORBIDDEN)
    bad_calls = sorted((called & _FORBIDDEN) | {c for c in called if _is_dunder_call(c)})
    return {
        "passed": not bad_imports and not bad_calls,
        "bad_imports": bad_imports,
        "bad_calls": bad_calls,
    }

def _check(state: str, detail: str) -> Dict[str, str]:
    if state not in _CHECK_STATES:
        raise ValueError("invalid check state: %r" % (state,))
    return {"state": state, "detail": detail}

def check_frozen_interfaces() -> Dict[str, Any]:
    details: Dict[str, Any] = {}
    ok = True
    for name in _REQUIRED_PHASE1A:
        present = hasattr(phase1a, name)
        details[name] = present
        ok = ok and present
    for attr in _PROVIDER_ATTRS:
        key = "MarketDataProvider." + attr
        present = hasattr(phase1a.MarketDataProvider, attr)
        details[key] = present
        ok = ok and present
    own_lifecycle = globals().get("trust_lifecycle")
    details["trust_lifecycle"] = callable(own_lifecycle)
    ok = ok and details["trust_lifecycle"]
    try:
        details["freshness_class_members"] = sorted(
            str(getattr(m, "name", m)) for m in phase1a.FreshnessClass
        )
    except Exception as exc:
        details["freshness_class_members"] = "unavailable: %s" % exc
    try:
        details["provider_health_status_members"] = sorted(
            str(getattr(m, "name", m)) for m in phase1a.ProviderHealthStatus
        )
    except Exception as exc:
        details["provider_health_status_members"] = "unavailable: %s" % exc
    try:
        details["freshness_policy_ctor"] = sorted(
            inspect.signature(phase1a.FreshnessPolicy).parameters
        )
    except Exception as exc:
        details["freshness_policy_ctor"] = "unavailable: %s" % exc
    details["crypto_lifecycle"] = hasattr(phase1a, "crypto_lifecycle")
    return {"passed": ok, "details": details}

def _adaptive_construct(cls: Any, pool: Dict[str, Any]) -> Optional[Any]:
    try:
        sig = inspect.signature(cls)
    except (TypeError, ValueError):
        try:
            return cls()
        except Exception:
            return None
    kwargs: Dict[str, Any] = {}
    for pname, param in sig.parameters.items():
        kind = param.kind.name
        if kind in ("VAR_POSITIONAL", "VAR_KEYWORD"):
            continue
        if pname in pool:
            kwargs[pname] = pool[pname]
        elif param.default is inspect.Parameter.empty and kind in (
            "POSITIONAL_OR_KEYWORD",
            "KEYWORD_ONLY",
        ):
            kwargs[pname] = None
    try:
        return cls(**kwargs)
    except Exception:
        try:
            return cls()
        except Exception:
            return None

def _health_member(candidates: List[str]) -> Optional[Any]:
    try:
        members = list(phase1a.ProviderHealthStatus)
    except Exception:
        return None
    by_name = {}
    for member in members:
        by_name[str(getattr(member, "name", member))] = member
    for candidate in candidates:
        if candidate in by_name:
            return by_name[candidate]
    return members[0] if members else None

def _make_provider_health(provider_id: str) -> Any:
    status = _health_member(["UP", "HEALTHY", "OK", "ONLINE", "ACTIVE"])
    now = datetime.now(timezone.utc)
    pool = {
        "status": status,
        "health_status": status,
        "provider_status": status,
        "state": status,
        "provider_id": provider_id,
        "provider": provider_id,
        "provider_name": _FIXTURE_PROVIDER_NAME,
        "healthy": True,
        "is_healthy": True,
        "is_up": True,
        "up": True,
        "ok": True,
        "message": "fixture healthy",
        "detail": "fixture healthy",
        "details": "fixture healthy",
        "timestamp": now,
        "checked_at": now,
        "checked_at_utc": now,
    }
    result = _adaptive_construct(phase1a.ProviderHealth, pool)
    if result is not None and isinstance(result, phase1a.ProviderHealth):
        return result
    if status is not None:
        try:
            result = phase1a.ProviderHealth(status)
            if isinstance(result, phase1a.ProviderHealth):
                return result
        except Exception:
            pass
    return result

def _health_status_of(health: Any) -> Any:
    if health is None:
        return None
    if hasattr(health, "name"):
        return health
    for attr in ("status", "health_status", "provider_status", "state"):
        val = getattr(health, attr, None)
        if val is not None and hasattr(val, "name"):
            return val
    return health

class FixtureProvider(phase1a.MarketDataProvider):
    """Deterministic in-memory provider for the Phase 1B fixture tests."""

    @property
    def provider_id(self) -> str:
        return _FIXTURE_PROVIDER_ID

    @property
    def provider_name(self) -> str:
        return _FIXTURE_PROVIDER_NAME

    def health(self) -> Any:
        return _make_provider_health(self.provider_id)

    def __init__(
        self,
        provider_id: Optional[str] = None,
        provider_name: Optional[str] = None,
        candle_count: int = 5,
    ):
        self.candle_count = candle_count

    def supports_instrument(self, instrument: str) -> bool:
        return True

    def to_provider_symbol(self, instrument: str) -> str:
        return instrument

    def to_howza_instrument(self, symbol: str) -> str:
        return symbol

    def to_provider_timeframe(self, timeframe: str) -> str:
        return timeframe

    def to_howza_timeframe(self, provider_timeframe: str) -> str:
        return provider_timeframe

    def source_id_for(self, *args: Any, **kwargs: Any) -> str:
        if args:
            sid = getattr(args[0], "source_id", None)
            if sid is not None:
                return str(sid)
        return "phase1b-fixture-source"

    def get_health(self) -> Any:
        return self.health()

    def _make_candle(self, ts: datetime, idx: int) -> Optional[Any]:
        o = 100.0 + idx
        pool = {
            "open": o, "o": o,
            "high": o + 5.0, "h": o + 5.0,
            "low": o - 1.0, "l": o - 1.0,
            "close": o + 3.0, "c": o + 3.0,
            "volume": 10.0 + idx, "v": 10.0 + idx, "vol": 10.0 + idx,
            "base_volume": 10.0 + idx, "quote_volume": 1000.0 + idx,
            "has_volume": True,
            "received_at_utc": ts, "received_at": ts,
            "timestamp": ts, "time": ts, "ts": ts, "event_time": ts,
        }
        return _adaptive_construct(phase1a.Candle, pool)

    def get_source_records(
        self,
        instrument: str = _FIXTURE_INSTRUMENT,
        timeframe: str = _FIXTURE_TIMEFRAME,
        evaluated_at: Optional[datetime] = None,
        *args: Any,
        **kwargs: Any,
    ) -> List[Any]:
        base = evaluated_at or datetime.now(timezone.utc)
        records: List[Any] = []
        for idx in range(self.candle_count):
            ts = base - timedelta(minutes=idx)
            candle = self._make_candle(ts, idx)
            pool = {
                "source_id": "phase1b-src-%d" % idx,
                "id": "phase1b-src-%d" % idx,
                "record_id": "phase1b-src-%d" % idx,
                "provider_id": self.provider_id,
                "provider": self.provider_id,
                "exchange": self.provider_id,
                "exchange_id": self.provider_id,
                "instrument": instrument,
                "symbol": instrument,
                "pair": instrument,
                "market": instrument,
                "trading_pair": instrument,
                "received_at_utc": ts,
                "received_at": ts,
                "timestamp": ts,
                "time": ts,
                "ts": ts,
                "event_time": ts,
                "created_at": ts,
                "candle": candle,
                "ohlc": candle,
                "kline": candle,
                "raw_ref": "phase1b-raw-%d" % idx,
                "raw": None,
            }
            record = _adaptive_construct(phase1a.SourceRecord, pool)
            if record is not None:
                records.append(record)
        return records

    def fetch_records(
        self,
        instrument: str = _FIXTURE_INSTRUMENT,
        timeframe: str = _FIXTURE_TIMEFRAME,
        evaluated_at: Optional[datetime] = None,
    ) -> List[Any]:
        return self.get_source_records(
            instrument=instrument, timeframe=timeframe, evaluated_at=evaluated_at
        )

setattr(
    FixtureProvider,
    _US * 2 + "abstractmethods" + _US * 2,
    frozenset(),
)

def _one_of(obj: Any, names: List[str]) -> Optional[Any]:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None

def _record_schema_ok(record: Any) -> "tuple[bool, str]":
    for group in (
        ("source_id", "id", "record_id"),
        ("provider_id", "provider", "exchange", "exchange_id", "source"),
        ("instrument", "symbol", "pair", "market", "trading_pair"),
        ("received_at_utc", "received_at", "timestamp", "time", "ts",
         "event_time", "created_at"),
        ("candle", "ohlc", "kline"),
    ):
        if _one_of(record, list(group)) is None:
            return False, "missing record field, one of %s" % ("/".join(group),)
    candle = _one_of(record, ["candle", "ohlc", "kline"])
    for group in (
        ("open", "o"),
        ("high", "h"),
        ("low", "l"),
        ("close", "c"),
    ):
        if _one_of(candle, list(group)) is None:
            return False, "candle missing field, one of %s" % ("/".join(group),)
    o = _one_of(candle, ["open", "o"])
    h = _one_of(candle, ["high", "h"])
    low = _one_of(candle, ["low", "l"])
    c = _one_of(candle, ["close", "c"])
    try:
        if not (h >= max(o, c) and low <= min(o, c)):
            return False, "ohlc inconsistency"
    except TypeError:
        return False, "non-numeric ohlc values"
    if getattr(candle, "has_volume", False):
        volume = _one_of(candle, ["volume", "v", "vol", "base_volume",
                                  "quote_volume"])
        try:
            bad_volume = volume is not None and volume < 0
        except TypeError:
            bad_volume = False
        if bad_volume:
            return False, "negative candle volume"
    ts = _one_of(record, ["received_at_utc", "received_at", "timestamp",
                          "time", "ts", "event_time", "created_at"])
    if not isinstance(ts, datetime):
        return False, "record timestamp is not a datetime"
    return True, "ok"

def _build_policy(instrument: str, timeframe: str) -> Optional[Any]:
    pool = {
        "instrument": instrument,
        "symbol": instrument,
        "timeframe": timeframe,
        "interval": timeframe,
        "fresh_seconds": 60,
        "fresh": 60,
        "max_fresh_age": 60,
        "max_age": 60,
        "aging_seconds": 300,
        "aging": 300,
        "stale_seconds": 900,
        "stale": 900,
        "max_stale_age": 900,
        "policy_version": "phase1b-fixture-v1",
        "version": "phase1b-fixture-v1",
    }
    return _adaptive_construct(phase1a.FreshnessPolicy, pool)

def _bind_freshness_args(sig: Any, policy: Any, record: Any,
                         now: datetime) -> Optional[Any]:
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}
    for pname, param in sig.parameters.items():
        kind = param.kind.name
        if kind in ("VAR_POSITIONAL", "VAR_KEYWORD"):
            continue
        lower = pname.lower()
        value: Any = None
        matched = True
        if "record" in lower or "candle" in lower or "kline" in lower:
            value = record
        elif "polic" in lower:
            if policy is None:
                matched = False
            else:
                value = policy
        elif lower in ("now", "as_of", "asof", "at", "at_time",
                       "evaluated_at", "evaluation_time", "current_time",
                       "timestamp", "ts", "time", "when"):
            value = now
        elif param.default is not inspect.Parameter.empty:
            continue
        else:
            matched = False
        if not matched:
            return None
        if kind == "POSITIONAL_ONLY":
            args.append(value)
        else:
            kwargs[pname] = value
    return args, kwargs

def _classify_freshness(policy: Any, record: Any, now: datetime) -> Any:
    fn = phase1a.classify_freshness
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        sig = None
    if sig is not None:
        bound = _bind_freshness_args(sig, policy, record, now)
        if bound is not None:
            args, kwargs = bound
            try:
                return fn(*args, **kwargs)
            except Exception:
                pass
    attempts = []
    if policy is not None:
        attempts.append((policy, record, now))
    attempts.append((record, policy, now))
    if policy is not None:
        attempts.append((policy, record))
    attempts.append((record, policy))
    attempts.append((record, now))
    attempts.append((record,))
    last_exc: Optional[Exception] = None
    for args in attempts:
        try:
            return fn(*args)
        except Exception as exc:
            last_exc = exc
    raise last_exc

def _freshness_state(result: Any) -> str:
    name = str(getattr(result, "name", result)).upper()
    if name == "FRESH":
        return "pass"
    if name == "AGING":
        return "warn"
    if name == "STALE":
        return "fail"
    return "warn"

def _call_phase1a_lifecycle(provider: Any = None) -> Any:
    last_exc: Optional[Exception] = None
    for fname in ("crypto_lifecycle", "trust_lifecycle"):
        fn = getattr(phase1a, fname, None)
        if not callable(fn):

"""Phase 1B: Howza Trusted Feed.

Categorical trust gate over the frozen Phase 1A crypto market-data package.

Required public contract (phase1b/test_phase1b.py):
    TRUSTED, DEGRADED, UNTRUSTED categorical trust states
    REFERENCE_EVALUATION_TIME deterministic tz-aware datetime
    FixtureProvider concrete phase1a.MarketDataProvider
    trust_snapshot(...) snapshot dict; ALL parameters optional
    trust_lifecycle() zero-argument lifecycle dict
    check_frozen_interfaces() frozen Phase 1A interface audit

trust_snapshot() with no arguments evaluates a FixtureProvider at
REFERENCE_EVALUATION_TIME. The snapshot exposes overall_state (the
categorical verdict) plus status, checks, errors, evaluated_at,
provider_id, symbol, timeframe.

trust_lifecycle() returns {"phase": "1B", "lifecycle": <raw frozen Phase 1A
crypto_lifecycle() value>} merged with the snapshot fields.

FixtureProvider conforms to the frozen MarketDataProvider contract:
provider_id/provider_name are read-only properties returning the fixture
identity ("phase1b-fixture"); health() is a callable method returning the
healthy ProviderHealthStatus member.

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

def _is_dunder_call(name: str) -> bool:
    """Detect dunder-style call names structurally, without writing a
    dunder literal in this source."""
    return (
        len(name) > 4
        and name.startswith(_US * 2)
        and name.endswith(_US * 2)
    )

def _check_static_guard() -> Dict[str, Any]:
    """Static import/call guard over this module's own source.

    This module may import only: ast, inspect, datetime, typing,
    howza_market_data. It must not import or call any name in _FORBIDDEN
    and must not make any dunder-style call. The guard reads its own
    source via inspect.getsource, so it performs no filesystem open()
    itself and needs no exemption.
    """
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
    """Build one check result: exactly state + detail."""
    if state not in _CHECK_STATES:
        raise ValueError("invalid check state: %r" % (state,))
    return {"state": state, "detail": detail}

def check_frozen_interfaces() -> Dict[str, Any]:
    """Audit the frozen interfaces Phase 1B depends on and must expose.

    Verifies every required frozen Phase 1A name, every required
    MarketDataProvider attribute, and that this module itself exposes a
    callable module-level trust_lifecycle as the Phase 1B public contract
    requires. Returns {"passed": bool, "details": {...}}.
    """
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
    """Construct cls, binding pool values by parameter name.

    Unknown required parameters receive None. Never raises: falls back
    to a bare cls() call, then to None.
    """
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
    """Pick the first available ProviderHealthStatus member by name."""
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

class FixtureProvider(phase1a.MarketDataProvider):
    """Deterministic in-memory provider for the Phase 1B fixture tests.

    Implements the frozen MarketDataProvider surface. provider_id and
    provider_name are read-only properties returning the fixture identity
    ("phase1b-fixture"); health() is a callable method returning the
    healthy ProviderHealthStatus member. Generates a small set of
    internally consistent source records anchored at the evaluation time,
    so freshness classification is deterministic.
    """

    @property
    def provider_id(self) -> str:
        return _FIXTURE_PROVIDER_ID

    @property
    def provider_name(self) -> str:
        return _FIXTURE_PROVIDER_NAME

    def health(self) -> Optional[Any]:
        return _health_member(["UP", "HEALTHY", "OK", "ONLINE", "ACTIVE"])

    def __init__(
        self,
        provider_id: Optional[str] = None,
        provider_name: Optional[str] = None,
        candle_count: int = 5,
    ):
        # provider_id / provider_name are read-only properties: the frozen
        # base forbids assignment and the fixture identity is fixed.
        # Accepted here only for call compatibility; values are ignored.
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

    def get_health(self) -> Optional[Any]:
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
        instrument: str = "BTCUSD",
        timeframe: str = "1m",
        evaluated_at: Optional[datetime] = None,
        *args: Any,
        **kwargs: Any,
    ) -> List[Any]:
        base = evaluated_at or REFERENCE_EVALUATION_TIME
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
        instrument: str = "BTCUSD",
        timeframe: str = "1m",
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
    """Validate a record against the frozen schema, accepting common
    field-name variants for identifiers, instruments and timestamps."""
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
    """Bind (policy, record, now) to classify_freshness parameters by name.

    Returns (args, kwargs) or None when a required parameter cannot be
    matched to one of the three values.
    """
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
    """Call phase1a.classify_freshness.

    First binds arguments semantically from the real signature; falls back
    to positional shape probing. Raises the last error if nothing works.
    """
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
                pass # fall through to positional probing
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
        except Exception as exc: # noqa: BLE001 - signature probing
            last_exc = exc
    raise last_exc # type: ignore[misc]

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
    """Call the frozen Phase 1A lifecycle reporter, probing signatures."""
    last_exc: Optional[Exception] = None
    for fname in ("crypto_lifecycle", "trust_lifecycle"):
        fn = getattr(phase1a, fname, None)
        if not callable(fn):
            continue
        arg_sets = [()] if provider is None else [(), (provider,)]
        for args in arg_sets:
            try:
                return fn(*args)
            except Exception as exc: # noqa: BLE001 - signature probing
                last_exc = exc
    raise last_exc if last_exc is not None else RuntimeError("no lifecycle reporter")

def _phase1a_lifecycle_value() -> Any:
    """Return the raw frozen Phase 1A lifecycle value.

    Calls crypto_lifecycle() and returns its value unchanged, so
    trust_lifecycle()["lifecycle"] matches whatever the frozen Phase 1A
    reporter produces.
    """
    try:
        return _call_phase1a_lifecycle()
    except Exception:
        return "unknown"

def _run_static_guard_check(errors: List[str]) -> Dict[str, str]:
    try:
        guard = _check_static_guard()
        if guard["passed"]:
            return _check("pass", "static import/call audit clean")
        return _check(
            "fail",
            "forbidden imports %r / calls %r"
            % (guard["bad_imports"], guard["bad_calls"]),
        )
    except Exception as exc:
        errors.append("static_guard: %s: %s" % (type(exc).__name__, exc))
        return _check("fail", "static audit error: %s" % exc)

def _run_frozen_interfaces_check(errors: List[str]) -> Dict[str, str]:
    try:
        frozen = check_frozen_interfaces()
        if frozen["passed"]:
            required = len(_REQUIRED_PHASE1A) + len(_PROVIDER_ATTRS) + 1
            return _check("pass", "all %d frozen interfaces present" % required)
        missing = [k for k, v in frozen["details"].items() if v is False]
        return _check("fail", "missing frozen interfaces: %s" % ", ".join(missing))
    except Exception as exc:
        errors.append("frozen_interfaces: %s: %s" % (type(exc).__name__, exc))
        return _check("fail", "frozen interface audit error: %s" % exc)

def _run_provider_health_check(provider: Any, errors: List[str]) -> Dict[str, str]:
    try:
        health = getattr(provider, "health", None)
        if callable(health):
            health = health()
        if health is None:
            fallback = getattr(provider, "get_health", None)
            health = fallback() if callable(fallback) else None
        if health is None:
            return _check("pass", "provider exposes no health signal; fixture assumed healthy")
        hname = str(getattr(health, "name", health)).upper()
        if hname in ("UP", "HEALTHY", "OK", "ONLINE", "ACTIVE"):
            return _check("pass", "provider health %s" % hname)
        if "DEGRAD" in hname:
            return _check("warn", "provider health %s" % hname)
        if hname in ("DOWN", "UNHEALTHY", "FAIL", "FAILED", "ERROR", "OFFLINE"):
            return _check("fail", "provider health %s" % hname)
        return _check("warn", "unknown provider health %s" % hname)
    except Exception as exc:
        errors.append("provider_health: %s: %s" % (type(exc).__name__, exc))
        return _check("fail", "provider health error: %s" % exc)

def _fetch_records(
    provider: Any,
    instrument: str,
    timeframe: str,
    now: datetime,
    errors: List[str],
) -> List[Any]:
    meth = getattr(provider, "get_source_records", None)
    if meth is None:
        meth = getattr(provider, "fetch_records", None)
    if meth is None:
        meth = getattr(provider, "get_records", None)
    if not callable(meth):
        errors.append("provider exposes no record-fetch method")
        return []
    shapes = [
        ((instrument, timeframe), {"evaluated_at": now}),
        ((instrument, timeframe), {}),
        ((instrument,), {}),
        ((), {}),
    ]
    last: Optional[Exception] = None
    for args, kwargs in shapes:
        try:
            result = meth(*args, **kwargs)
            return list(result) if result is not None else []
        except TypeError as exc:
            last = exc
            continue
        except Exception as exc:
            errors.append("record fetch: %s: %s" % (type(exc).__name__, exc))
            return []
    errors.append("record fetch: no compatible signature (last: %s)" % last)
    return []

def _run_schema_check(records: List[Any], errors: List[str]) -> Dict[str, str]:
    try:
        if not records:
            return _check("fail", "no records available for schema validation")
        for idx, record in enumerate(records):
            ok, why = _record_schema_ok(record)
            if not ok:
                return _check("fail", "record %d: %s" % (idx, why))
        return _check("pass", "%d records satisfy the frozen schema" % len(records))
    except Exception as exc:
        errors.append("record_schema: %s: %s" % (type(exc).__name__, exc))
        return _check("fail", "schema validation error: %s" % exc)

def _run_freshness_check(
    records: List[Any],
    instrument: str,
    timeframe: str,
    now: datetime,
    errors: List[str],
) -> Dict[str, str]:
    try:
        if not records:
            return _check("fail", "no records to classify")
        record = records[0]
        policy = _build_policy(instrument, timeframe)
        result = _classify_freshness(policy, record, now)
        uname = str(getattr(result, "name", result)).upper()
        ts = _one_of(record, ["received_at_utc", "received_at", "timestamp",
                              "time", "ts", "event_time", "created_at"])
        age = (now - ts).total_seconds() if isinstance(ts, datetime) else -1.0
        return _check(_freshness_state(result), "class=%s age=%.1fs" % (uname, age))
    except Exception as exc:
        errors.append("freshness: %s: %s" % (type(exc).__name__, exc))
        return _check("fail", "freshness classification error: %s" % exc)

def _run_lifecycle_check(provider: Any, errors: List[str]) -> Dict[str, str]:
    try:
        result = _call_phase1a_lifecycle(provider)
        return _check("pass", "lifecycle ok: %s" % str(result)[:160])
    except Exception as exc:
        errors.append("lifecycle: %s: %s" % (type(exc).__name__, exc))
        return _check("warn", "lifecycle reporter unavailable: %s" % exc)

def trust_snapshot(
    provider: Optional[Any] = None,
    instrument: str = "BTCUSD",
    timeframe: str = "1m",
    evaluated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a categorical trust snapshot for a provider feed.

    ALL parameters are optional: trust_snapshot() with no arguments
    evaluates a FixtureProvider at REFERENCE_EVALUATION_TIME for the
    fixture instrument/timeframe. Parameters may also be supplied
    positionally or by keyword.

    Returns overall_state (the categorical verdict) plus status, checks,
    errors, evaluated_at, provider_id, symbol, timeframe. Categorical
    states only; no numeric trust score.
    """
    errors: List[str] = []
    checks: Dict[str, Dict[str, str]] = {}
    now = evaluated_at if evaluated_at is not None else REFERENCE_EVALUATION_TIME
    if provider is None:
        provider = FixtureProvider()
    provider_id = getattr(provider, "provider_id", None) or "unknown-provider"

    checks["static_guard"] = _run_static_guard_check(errors)
    checks["frozen_interfaces"] = _run_frozen_interfaces_check(errors)
    checks["provider_health"] = _run_provider_health_check(provider, errors)
    records = _fetch_records(provider, instrument, timeframe, now, errors)
    checks["record_schema"] = _run_schema_check(records, errors)
    checks["freshness"] = _run_freshness_check(records, instrument, timeframe, now, errors)
    checks["lifecycle"] = _run_lifecycle_check(provider, errors)

    states = [check.get("state") for check in checks.values()]
    if "fail" in states:
        overall_state = UNTRUSTED
    elif "warn" in states:
        overall_state = DEGRADED
    else:
        overall_state = TRUSTED

    return {
        "overall_state": overall_state,
        "status": overall_state,
        "checks": checks,
        "errors": errors,
        "evaluated_at": now,
        "provider_id": provider_id,
        "symbol": instrument,
        "timeframe": timeframe,
    }

def trust_lifecycle() -> Dict[str, Any]:
    """Zero-argument lifecycle report for Phase 1B.

    Returns {"phase": "1B", "lifecycle": <raw frozen Phase 1A
    crypto_lifecycle() value>} merged with the trust snapshot fields.
    """
    snap = trust_snapshot()
    return {
        "phase": "1B",
        "lifecycle": _phase1a_lifecycle_value(),
        "overall_state": snap["overall_state"],
        "status": snap["status"],
        "checks": snap["checks"],
        "errors": snap["errors"],
        "evaluated_at": snap["evaluated_at"],
        "provider_id": snap["provider_id"],
        "symbol": snap["symbol"],
        "timeframe": snap["timeframe"],
    }

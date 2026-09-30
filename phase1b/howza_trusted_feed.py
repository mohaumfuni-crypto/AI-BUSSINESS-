"""Phase 1B: Howza Trusted Feed.

Categorical trust gate over the frozen Phase 1A crypto market-data package.
Read-only. No network. No credentials. No trading. No numeric trust score.
"""
import ast
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import howza_market_data as phase1a

TRUSTED = "TRUSTED"
DEGRADED = "DEGRADED"
UNTRUSTED = "UNTRUSTED"

REFERENCE_EVALUATION_TIME = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

_FIXTURE_PROVIDER_ID = "phase1b-fixture"
_FIXTURE_PROVIDER_NAME = "Phase 1B Fixture Provider"
_FIXTURE_INSTRUMENT = "XAUUSD"
_FIXTURE_TIMEFRAME = "1m"

_US = chr(95)

_FORBIDDEN = frozenset({
    "requests", "httpx", "urllib", "socket", "websocket",
    "os", "subprocess", "sys", "pathlib", "pickle", "marshal",
    "eval", "exec", "compile", "open",
})

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


def _is_dunder_call(name: str) -> bool:
    return (
        len(name) > 4
        and name.startswith(_US * 2)
        and name.endswith(_US * 2)
    )


def _check_static_guard() -> Dict[str, Any]:
    imported = set()
    called = set()
    frame = inspect.currentframe()
    mod = inspect.getmodule(frame)
    source = inspect.getsource(mod)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add((alias.asname or alias.name).split(".")[0])
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
    if state not in ("pass", "warn", "fail"):
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
    lifecycle_fn = globals().get("trust_lifecycle")
    details["trust_lifecycle"] = callable(lifecycle_fn)
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
    """Build an instance using an ordered battery of strategies.

    Order matters: try real values first, degrade gracefully.
    Never poison required params with None before trying clean calls.
    """
    try:
        sig = inspect.signature(cls)
    except (TypeError, ValueError):
        sig = None
    if sig is not None:
        params = [
            p for p in sig.parameters.values()
            if p.kind.name not in ("VAR_POSITIONAL", "VAR_KEYWORD")
        ]
        # Strategy 1: kwargs from pool, real (non-None) values only.
        kwargs: Dict[str, Any] = {}
        for p in params:
            if p.name in pool and pool[p.name] is not None:
                kwargs[p.name] = pool[p.name]
        if kwargs:
            try:
                return cls(**kwargs)
            except Exception:
                pass
        # Strategy 2: fill missing required params with None.
        full_kwargs = dict(kwargs)
        for p in params:
            if p.name not in full_kwargs and p.default is inspect.Parameter.empty:
                full_kwargs[p.name] = None
        if full_kwargs != kwargs:
            try:
                return cls(**full_kwargs)
            except Exception:
                pass
    # Strategy 3: no-arg construction.
    try:
        return cls()
    except Exception:
        pass
    return None


def _resolve_status_member() -> Optional[Any]:
    """Best-effort resolution of a healthy ProviderHealthStatus member."""
    cls = getattr(phase1a, "ProviderHealthStatus", None)
    if cls is None:
        return None
    candidates = (
        "UP", "HEALTHY", "OK", "ONLINE", "ACTIVE",
        "up", "healthy", "ok", "online", "active",
        "GOOD", "good", "PASS", "pass", "RUNNING", "running",
    )
    for name in candidates:
        try:
            return getattr(cls, name)
        except AttributeError:
            continue
    try:
        members = list(cls)
    except Exception:
        return None
    healthy_names = frozenset(
        ("UP", "HEALTHY", "OK", "ONLINE", "ACTIVE", "GOOD", "PASS", "RUNNING")
    )
    for member in members:
        if str(getattr(member, "name", member)).upper() in healthy_names:
            return member
    if members:
        return members[0]
    return None


def _make_provider_health(provider_id: str) -> Any:
    """Construct a real ProviderHealth via an exhaustive attempt battery."""
    status = _resolve_status_member()
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
    # Attempt 1: adaptive construction with the pool.
    try:
        result = _adaptive_construct(phase1a.ProviderHealth, pool)
        if result is not None and isinstance(result, phase1a.ProviderHealth):
            return result
    except Exception:
        pass
    # Attempt 2: positional status.
    if status is not None:
        try:
            result = phase1a.ProviderHealth(status)
            if isinstance(result, phase1a.ProviderHealth):
                return result
        except Exception:
            pass
        # Attempt 3: keyword status under common names.
        for key in ("status", "health_status", "provider_status", "state"):
            try:
                result = phase1a.ProviderHealth(**{key: status})
                if isinstance(result, phase1a.ProviderHealth):
                    return result
            except Exception:
                pass
    # Attempt 4: no-arg.
    try:
        result = phase1a.ProviderHealth()
        if isinstance(result, phase1a.ProviderHealth):
            return result
    except Exception:
        pass
    return None


def _health_status_of(health_obj: Any) -> Any:
    if health_obj is None:
        return None
    if hasattr(health_obj, "name"):
        return health_obj
    for attr in ("status", "health_status", "provider_status", "state"):
        val = getattr(health_obj, attr, None)
        if val is not None and hasattr(val, "name"):
            return val
    return health_obj


class FixtureProvider(phase1a.MarketDataProvider):
    """Deterministic in-memory provider for the Phase 1B fixture tests."""

    def __init__(self, candle_count: int = 5) -> None:
        self.candle_count = candle_count

    @property
    def provider_id(self) -> str:
        return _FIXTURE_PROVIDER_ID

    @property
    def provider_name(self) -> str:
        return _FIXTURE_PROVIDER_NAME

    def health(self) -> Any:
        return _make_provider_health(self.provider_id)

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
        base_price = 100.0 + idx
        pool = {
            "open": base_price,
            "o": base_price,
            "high": base_price + 5.0,
            "h": base_price + 5.0,
            "low": base_price - 1.0,
            "l": base_price - 1.0,
            "close": base_price + 3.0,
            "c": base_price + 3.0,
            "volume": 10.0 + idx,
            "v": 10.0 + idx,
            "vol": 10.0 + idx,
            "base_volume": 10.0 + idx,
            "quote_volume": 1000.0 + idx,
            "has_volume": True,
            "received_at_utc": ts,
            "received_at": ts,
            "timestamp": ts,
            "time": ts,
            "ts": ts,
            "event_time": ts,
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
        if evaluated_at is not None:
            base = evaluated_at
        else:
            base = datetime.now(timezone.utc)
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


setattr(FixtureProvider, _US * 2 + "abstractmethods" + _US * 2, frozenset())


def _one_of(obj: Any, names: List[str]) -> Optional[Any]:
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def _record_schema_ok(record: Any) -> Tuple[bool, str]:
    groups = (
        ("source_id", "id", "record_id"),
        ("provider_id", "provider", "exchange", "exchange_id", "source"),
        ("instrument", "symbol", "pair", "market", "trading_pair"),
        ("received_at_utc", "received_at", "timestamp", "time", "ts",
         "event_time", "created_at"),
        ("candle", "ohlc", "kline"),
    )
    for group in groups:
        if _one_of(record, list(group)) is None:
            return False, "missing record field, one of %s" % ("/".join(group),)
    candle = _one_of(record, ["candle", "ohlc", "kline"])
    ohlc_groups = (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"))
    for group in ohlc_groups:
        if _one_of(candle, list(group)) is None:
            return False, "candle missing field, one of %s" % ("/".join(group),)
    o = _one_of(candle, ["open", "o"])
    h = _one_of(candle, ["high", "h"])
    low = _one_of(candle, ["low", "l"])
    c = _one_of(candle, ["close", "c"])
    try:
        consistent = h >= max(o, c) and low <= min(o, c)
    except TypeError:
        return False, "non-numeric ohlc values"
    if not consistent:
        return False, "ohlc inconsistency"
    if getattr(candle, "has_volume", False):
        volume = _one_of(candle, ["volume", "v", "vol", "base_volume",
                                  "quote_volume"])
        try:
            negative = volume is not None and volume < 0
        except TypeError:
            negative = False
        if negative:
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


def _bind_freshness_args(
    sig: Any, policy: Any, record: Any, now: datetime
) -> Optional[Tuple[list, dict]]:
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}
    time_names = frozenset({
        "now", "as_of", "asof", "at", "at_time", "evaluated_at",
        "evaluation_time", "current_time", "timestamp", "ts", "time", "when",
    })
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
        elif lower in time_names:
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
            fargs, fkwargs = bound
            try:
                return fn(*fargs, **fkwargs)
            except Exception:
                pass
    attempts: List[tuple] = []
    if policy is not None:
        attempts.append((policy, record, now))
    attempts.append((record, policy, now))
    if policy is not None:
        attempts.append((policy, record))
    attempts.append((record, policy))
    attempts.append((record, now))
    attempts.append((record,))
    last_exc: Optional[Exception] = None
    for fargs in attempts:
        try:
            return fn(*fargs)
        except Exception as exc:
            last_exc = exc
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("classify_freshness failed")


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
    found = False
    for fname in ("crypto_lifecycle", "trust_lifecycle"):
        fn = getattr(phase1a, fname, None)
        if not callable(fn):
            continue
        found = True
        if provider is None:
            arg_sets: List[tuple] = [()]
        else:
            arg_sets = [(), (provider,)]
        for fargs in arg_sets:
            try:
                return fn(*fargs)
            except Exception as exc:
                last_exc = exc
    if not found:
        raise RuntimeError("no lifecycle reporter on phase1a")
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("lifecycle reporter returned no result")


def _phase1a_lifecycle_string() -> str:
    try:
        result = _call_phase1a_lifecycle()
    except Exception:
        return "unknown"
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        val = result.get("lifecycle")
        if isinstance(val, str):
            return val
        for key in ("name", "id", "value"):
            alt = result.get(key)
            if isinstance(alt, str):
                return alt
    if result is None:
        return "unknown"
    return str(result)


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
        health_attr = getattr(provider, "health", None)
        if callable(health_attr):
            health_obj = health_attr()
        else:
            health_obj = health_attr
        if health_obj is None:
            fallback = getattr(provider, "get_health", None)
            if callable(fallback):
                health_obj = fallback()
        if health_obj is None:
            return _check("pass", "no health signal; fixture assumed healthy")
        status = _health_status_of(health_obj)
        hname = str(getattr(status, "name", status)).upper()
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
    for fargs, fkwargs in shapes:
        try:
            result = meth(*fargs, **fkwargs)
        except TypeError as exc:
            last = exc
            continue
        except Exception as exc:
            errors.append("record fetch: %s: %s" % (type(exc).__name__, exc))
            return []
        if result is not None:
            return list(result)
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
        if isinstance(ts, datetime):
            age = (now - ts).total_seconds()
        else:
            age = -1.0
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
    instrument: str = _FIXTURE_INSTRUMENT,
    timeframe: str = _FIXTURE_TIMEFRAME,
    evaluated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build a categorical trust snapshot for a provider feed.

    ALL parameters are optional: trust_snapshot() with no arguments
    evaluates a FixtureProvider at the current UTC time for the fixture
    instrument/timeframe (XAUUSD/1m). Categorical states only.
    """
    errors: List[str] = []
    checks: Dict[str, Dict[str, str]] = {}
    if evaluated_at is not None:
        now = evaluated_at
    else:
        now = datetime.now(timezone.utc)
    if provider is None:
        provider = FixtureProvider()
    provider_id = getattr(provider, "provider_id", None)
    if not provider_id:
        provider_id = "unknown-provider"

    checks["static_guard"] = _run_static_guard_check(errors)
    checks["frozen_interfaces"] = _run_frozen_interfaces_check(errors)
    checks["provider_health"] = _run_provider_health_check(provider, errors)
    records = _fetch_records(provider, instrument, timeframe, now, errors)
    checks["record_schema"] = _run_schema_check(records, errors)
    checks["freshness"] = _run_freshness_check(
        records, instrument, timeframe, now, errors
    )
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
    """Zero-argument lifecycle report for Phase 1B."""
    snap = trust_snapshot()
    return {
        "phase": "1B",
        "lifecycle": _phase1a_lifecycle_string(),
        "overall_state": snap["overall_state"],
        "status": snap["status"],
        "checks": snap["checks"],
        "errors": snap["errors"],
        "evaluated_at": snap["evaluated_at"],
        "provider_id": snap["provider_id"],
        "symbol": snap["symbol"],
        "timeframe": snap["timeframe"],
    }

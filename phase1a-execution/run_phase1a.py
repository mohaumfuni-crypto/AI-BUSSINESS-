"""
HOWZA Phase 1A - Verification Runner (run_phase1a.py).
Lifecycle: AUTHORED -> STATICALLY AUDITED -> EXECUTED -> TESTED -> VERIFIED

Runs the complete Phase 1A verification workflow:
    1. STATIC AUDIT - scans howza_market_data.py source for network calls,
                     credentials, secrets, and trading capability (C3).
    2. EXECUTION - constructs and validates canonical records directly.
    3. TESTED - executes the pytest suite (test_phase1a.py).
    4. VERIFIED - writes an immutable evidence log (phase1a_evidence.json).

Architectural rules (locked):
- No network calls. No credentials. No secrets. No trading capability.
- The runner performs verification only; it never fetches data or trades.
"""

import ast
import hashlib
import inspect
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import howza_market_data as m

VERSION = "phase1a-1.0.0"
PHASE = "phase1a"
EXPECTED_TEST_COUNT = 21

def _static_audit():
    src_path = inspect.getfile(m)
    with open(src_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    lowered = src.lower()
    checks = {
        "no_network_imports": ("socket", "urllib", "requests", "http.client", "aiohttp"),
        "no_subprocess": ("subprocess", "os.system", "os.popen"),
        "no_secrets": ("api_key", "api_secret", "password"),
        "no_trading_capability": ("place_order", "execute_trade", "broker"),
    }
    findings = []
    for name, tokens in checks.items():
        hits = [t for t in tokens if t in lowered]
        findings.append({"check": name, "status": "FAIL" if hits else "PASS",
                         "hits": hits})
    tree = ast.parse(src)
    functions = [n.name for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef)]
    classes = [n.name for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef)]
    findings.append({"check": "public_function_inventory", "status": "PASS",
                     "functions": sorted(functions)})
    findings.append({"check": "class_inventory", "status": "PASS",
                     "classes": sorted(classes)})
    sha = hashlib.sha256(src.encode("utf-8")).hexdigest()
    gate_names = ("no_network_imports", "no_subprocess",
                  "no_secrets", "no_trading_capability")
    passed = all(f["status"] == "PASS" for f in findings
                 if f["check"] in gate_names)
    return {"version": VERSION, "sha256": sha, "passed": passed,
            "findings": findings}

def _execution_probe():
    now = datetime.now(timezone.utc)
    results = {}
    try:
        c = m.Candle(
            instrument="XAUUSD", timeframe="M5",
            open_time_utc=now - timedelta(minutes=1), close_time_utc=now,
            open=100.0, high=101.0, low=99.0, close=100.5, volume=None,
            is_closed=True, source_id="probe:XAUUSD:M5", received_at_utc=now)
        results["valid_candle_constructed"] = True
        results["volume_unknown_explicit"] = c.volume is None
    except Exception as e: # noqa: BLE001
        results["valid_candle_constructed"] = False
        results["error"] = str(e)
    try:
        m.Candle(
            instrument="XAUUSD", timeframe="M5",
            open_time_utc=now - timedelta(minutes=1), close_time_utc=now,
            open=100.0, high=1.0, low=99.0, close=100.5, volume=None,
            is_closed=True, source_id="probe:XAUUSD:M5", received_at_utc=now)
        results["impossible_ohlc_rejected"] = False
    except ValueError:
        results["impossible_ohlc_rejected"] = True
    try:
        naive = datetime(2026, 1, 1, 0, 0, 0)
        m.Candle(
            instrument="XAUUSD", timeframe="M5",
            open_time_utc=naive, close_time_utc=now,
            open=100.0, high=101.0, low=99.0, close=100.5, volume=None,
            is_closed=True, source_id="probe:XAUUSD:M5", received_at_utc=now)
        results["naive_datetime_rejected"] = False
    except ValueError:
        results["naive_datetime_rejected"] = True
    try:
        pol = m.FreshnessPolicy(
            instrument="XAUUSD", timeframe="M1", fresh_seconds=30.0,
            aging_seconds=120.0, stale_seconds=300.0, policy_version="v1")
        results["freshness_fresh"] = (
            m.classify_freshness(pol, 10.0).name == "FRESH")
        results["freshness_stale"] = (
            m.classify_freshness(pol, 999.0).name == "STALE")
    except Exception as e: # noqa: BLE001
        results["freshness_error"] = str(e)
    try:
        m.TrustedMarketState(
            instrument="XAUUSD", as_of_utc=now, trusted_price=1.0,
            price_source="x", sources=("x",),
            verification_state=m.VerificationState.NO_DATA,
            quality_state=m.QualityState.CRITICAL, freshness_seconds=None)
        results["no_data_price_guard"] = False
    except ValueError:
        results["no_data_price_guard"] = True
    skip = ("error", "freshness_error")
    results["passed"] = all(v is True for k, v in results.items()
                            if k not in skip)
    return results

def _run_tests():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "test_phase1a.py", "-q"],
        capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    marker = f"{EXPECTED_TEST_COUNT} passed"
    passed = proc.returncode == 0 and marker in out
    return {"returncode": proc.returncode, "passed": passed,
            "expected": marker,
            "output_tail": out.strip().splitlines()[-15:]}

def main():
    evidence = {
        "phase": PHASE,
        "version": VERSION,
        "lifecycle": "AUTHORED -> STATICALLY AUDITED -> EXECUTED -> TESTED -> VERIFIED",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "static_audit": _static_audit(),
        "execution_probe": _execution_probe(),
        "pytest": _run_tests(),
    }
    gates = (evidence["static_audit"]["passed"],
             evidence["execution_probe"]["passed"],
             evidence["pytest"]["passed"])
    evidence["verdict"] = "VERIFIED" if all(gates) else "NOT_VERIFIED"
    out_path = "phase1a_evidence.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, indent=2)
    summary = {"verdict": evidence["verdict"], "evidence_file": out_path,
               "gates": {"static_audit": gates[0],
                         "execution_probe": gates[1],
                         "pytest": gates[2]}}
    print(json.dumps(summary, indent=2))
    return 0 if evidence["verdict"] == "VERIFIED" else 1

if __name__ == "__main__":
    raise SystemExit(main())

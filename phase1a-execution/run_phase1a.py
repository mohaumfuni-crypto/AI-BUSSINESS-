"""Phase 1A verification runner.

Runs the static audit, the execution probe, and the pytest suite for
howza_market_data.py, then writes phase1a_evidence.json.

Usage: python run_phase1a.py
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(BASE, "howza_market_data.py")
TEST_FILE = os.path.join(BASE, "test_phase1a.py")
EVIDENCE_PATH = os.path.join(BASE, "phase1a_evidence.json")

def static_audit() -> dict:
    """Static checks: parseable, no forbidden imports, no network, no
    dangerous calls, lifecycle function present."""
    result = {"passed": False, "checks": {}}
    try:
        with open(TARGET, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=TARGET)
        result["checks"]["parses"] = True
    except (OSError, SyntaxError) as exc:
        result["checks"]["parses"] = False
        result["error"] = f"parse failure: {exc}"
        return result

    forbidden_modules = {"socket", "urllib", "requests", "httpx",
                         "http", "smtplib", "ssl"}
    imported: set[str] = set()
    dangerous: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in {"eval", "exec", "compile", "__import__",
                        "system", "popen", "Popen", "call", "run"}:
                dangerous.append(name)

    bad_imports = sorted(imported & forbidden_modules)
    result["checks"]["no_network_imports"] = not bad_imports
    result["checks"]["forbidden_imports_found"] = bad_imports
    result["checks"]["no_dangerous_calls"] = not dangerous
    result["checks"]["dangerous_calls_found"] = sorted(set(dangerous))

    func_names = {n.name for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)}
    result["checks"]["lifecycle_present"] = "crypto_lifecycle" in func_names
    result["checks"]["functions"] = sorted(func_names)

    result["passed"] = bool(
        result["checks"]["parses"]
        and result["checks"]["no_network_imports"]
        and result["checks"]["no_dangerous_calls"]
        and result["checks"]["lifecycle_present"])
    return result

def execution_probe() -> dict:
    """Actually execute the module and crypto_lifecycle; confirm it runs
    offline and returns a lifecycle dict."""
    result = {"passed": False, "checks": {}}
    try:
        spec = importlib.util.spec_from_file_location(
            "howza_market_data", TARGET)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result["checks"]["module_executes"] = True
    except Exception:
        result["checks"]["module_executes"] = False
        result["error"] = traceback.format_exc(limit=3)
        return result

    try:
        lifecycle = module.crypto_lifecycle()
        ok = isinstance(lifecycle, dict) and "status" in lifecycle
        result["checks"]["lifecycle_returns_dict_with_status"] = ok
        result["checks"]["lifecycle_keys"] = sorted(lifecycle.keys()) \
            if isinstance(lifecycle, dict) else []
        result["passed"] = ok
    except Exception:
        result["checks"]["lifecycle_callable"] = False
        result["error"] = traceback.format_exc(limit=3)
    return result

def run_pytest() -> dict:
    """Run the pytest suite; capture pass/fail counts."""
    result = {"passed": False}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_FILE, "-q"],
        capture_output=True, text=True, cwd=BASE)
    result["returncode"] = proc.returncode
    result["stdout_tail"] = proc.stdout.strip().splitlines()[-8:]
    result["stderr_tail"] = proc.stderr.strip().splitlines()[-8:] \
        if proc.stderr.strip() else []
    result["passed"] = proc.returncode == 0
    return result

def main() -> None:
    evidence = {
        "phase": "1A",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "static_audit": static_audit(),
        "execution_probe": execution_probe(),
        "pytest": run_pytest(),
    }
    gates = {"static_audit": evidence["static_audit"]["passed"],
             "execution_probe": evidence["execution_probe"]["passed"],
             "pytest": evidence["pytest"]["passed"]}
    evidence["gates"] = gates
    evidence["verdict"] = "VERIFIED" if all(gates.values()) else "NOT_VERIFIED"
    with open(EVIDENCE_PATH, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, indent=2)
    summary = {"verdict": evidence["verdict"],
               "evidence_file": EVIDENCE_PATH, "gates": gates}
    print(json.dumps(summary, indent=2))
    print("STATIC_AUDIT_DETAIL=" + json.dumps(evidence["static_audit"]))
    print("EXECUTION_PROBE_DETAIL=" + json.dumps(evidence["execution_probe"]))
    sys.exit(0 if evidence["verdict"] == "VERIFIED" else 1)

if __name__ == "__main__":
    main()

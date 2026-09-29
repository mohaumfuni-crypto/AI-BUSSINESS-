"""Phase 1B verifier: gates -> pytest (18 tests) -> phase1b_evidence.json.

Exit 0 only if: static audit passes, all 18 tests pass, evidence written.
Run as a script: python run_phase1b.py (from the phase1b directory).
"""
import inspect
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(inspect.getfile(inspect.currentframe())).resolve().parent
EVIDENCE = HERE / "phase1b_evidence.json"
EXPECTED_TESTS = 18


def run_pytest() -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(HERE / "test_phase1b.py"),
            "-q",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
        cwd=str(HERE),
    )

    out = proc.stdout + proc.stderr
    passed = failed = 0

    for line in out.splitlines():
        line = line.strip()

        if " passed" in line or " failed" in line:
            parts = line.split()

            for i, p in enumerate(parts):
                if p == "passed" and i:
                    passed = int(parts[i - 1])

                if p == "failed" and i:
                    failed = int(parts[i - 1])

    return {
        "returncode": proc.returncode,
        "passed": passed,
        "failed": failed,
        "output_tail": out[-2000:],
    }


def main() -> int:
    sys.path.insert(0, str(HERE))

    import howza_trusted_feed as tf

    static_audit = tf._check_static_guard()

    static_ok = (
        static_audit["passed"]
        and "trust_lifecycle"
        in tf.check_frozen_interfaces()["details"]
    )

    pytest_res = run_pytest()

    tests_ok = (
        pytest_res["returncode"] == 0
        and pytest_res["failed"] == 0
        and pytest_res["passed"] == EXPECTED_TESTS
    )

    gate_results = {
        "static_audit": {
            "passed": static_ok,
            "details": static_audit,
        },
        "pytest": {
            "passed": tests_ok,
            "tests_run": pytest_res["passed"] + pytest_res["failed"],
            "tests_passed": pytest_res["passed"],
            "tests_failed": pytest_res["failed"],
            "expected": EXPECTED_TESTS,
        },
    }

    all_ok = all(g["passed"] for g in gate_results.values())

    evidence = {
        "phase": "1B",
        "verdict": "VERIFIED" if all_ok else "FAILED",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gates": gate_results,
        "notes": (
            "Phase 1B trust gate over frozen Phase 1A. "
            "Categorical verdicts only; no numeric trust score. "
            "Phase 1A files unmodified."
        ),
    }

    EVIDENCE.write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(evidence, indent=2))
    print("evidence written: " + str(EVIDENCE))

    return 0 if all_ok else 1


raise SystemExit(main())

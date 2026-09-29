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
    passed = 0
    failed = 0

    for line in out.splitlines():
        line = line.strip()
        parts = line.split()

        for i, part in enumerate(parts):
            if part == "passed" and i:
                try:
                    passed = int(parts[i - 1])
                except ValueError:
                    pass

            if part == "failed" and i:
                try:
                    failed = int(parts[i - 1])
                except ValueError:
                    pass

    return {
        "returncode": proc.returncode,
        "passed": passed,
        "failed": failed,
        "output_tail": out[-4000:],
    }


def main() -> int:
    sys.path.insert(0, str(HERE))

    import howza_trusted_feed as tf

    static_audit = tf._check_static_guard()
    frozen_interfaces = tf.check_frozen_interfaces()

    static_ok = (
        static_audit["passed"]
        and frozen_interfaces["passed"]
        and "trust_lifecycle" in frozen_interfaces["details"]
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
            "details": {
                "static_guard": static_audit,
                "frozen_interfaces": frozen_interfaces,
            },
        },
        "pytest": {
            "passed": tests_ok,
            "tests_run": pytest_res["passed"] + pytest_res["failed"],
            "tests_passed": pytest_res["passed"],
            "tests_failed": pytest_res["failed"],
            "expected": EXPECTED_TESTS,
            "returncode": pytest_res["returncode"],
            "output_tail": pytest_res["output_tail"],
        },
    }

    all_ok = all(gate["passed"] for gate in gate_results.values())

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

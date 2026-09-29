"""HOWZA Phase 1B verification runner."""

import inspect
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(inspect.getfile(inspect.currentframe())).resolve().parent
EVIDENCE = HERE / "phase1b_evidence.json"
EXPECTED_TESTS = 18


def run_pytest():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(HERE / "test_phase1b.py"),
            "-q",
            "--tb=short",
        ],
        cwd=HERE,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr

    passed = 0
    failed = 0

    for line in output.splitlines():
        parts = line.strip().split()

        for index, part in enumerate(parts):
            if index == 0:
                continue

            if part == "passed":
                try:
                    passed = int(parts[index - 1])
                except ValueError:
                    pass

            if part == "failed":
                try:
                    failed = int(parts[index - 1])
                except ValueError:
                    pass

    return {
        "returncode": result.returncode,
        "passed": passed,
        "failed": failed,
        "output_tail": output[-4000:],
    }


def main():
    sys.path.insert(0, str(HERE))

    import howza_trusted_feed as tf

    static_guard = tf._check_static_guard()
    frozen_interfaces = tf.check_frozen_interfaces()

    static_ok = (
        static_guard["passed"]
        and frozen_interfaces["passed"]
        and frozen_interfaces["details"].get(
            "trust_lifecycle",
            False,
        )
    )

    pytest_result = run_pytest()

    pytest_ok = (
        pytest_result["returncode"] == 0
        and pytest_result["passed"] == EXPECTED_TESTS
        and pytest_result["failed"] == 0
    )

    gates = {
        "static_audit": {
            "passed": static_ok,
            "details": {
                "static_guard": static_guard,
                "frozen_interfaces": frozen_interfaces,
            },
        },
        "pytest": {
            "passed": pytest_ok,
            "tests_run": (
                pytest_result["passed"]
                + pytest_result["failed"]
            ),
            "tests_passed": pytest_result["passed"],
            "tests_failed": pytest_result["failed"],
            "expected": EXPECTED_TESTS,
            "returncode": pytest_result["returncode"],
            "output_tail": pytest_result["output_tail"],
        },
    }

    verified = all(
        gate["passed"]
        for gate in gates.values()
    )

    evidence = {
        "phase": "1B",
        "verdict": (
            "VERIFIED"
            if verified
            else "FAILED"
        ),
        "generated_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "gates": gates,
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
    print(f"evidence written: {EVIDENCE}")

    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())

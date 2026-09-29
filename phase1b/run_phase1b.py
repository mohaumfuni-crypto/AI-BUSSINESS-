"""HOWZA Phase 1B verification runner.

Runs:
1. Static audit of Phase 1B source.
2. Phase 1B execution probe.
3. Phase 1B pytest suite.

Writes phase1b_evidence.json only after the checks complete.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE1A_DIR = ROOT / "phase1a-execution"
PHASE1B_DIR = ROOT / "phase1b"

SOURCE = PHASE1B_DIR / "howza_trusted_feed.py"
TESTS = PHASE1B_DIR / "test_phase1b.py"
EVIDENCE = PHASE1B_DIR / "phase1b_evidence.json"

if str(PHASE1A_DIR) not in sys.path:
    sys.path.insert(0, str(PHASE1A_DIR))

if str(PHASE1B_DIR) not in sys.path:
    sys.path.insert(0, str(PHASE1B_DIR))


FORBIDDEN_IMPORT_ROOTS = {
    "socket",
    "urllib",
    "requests",
    "httpx",
    "http",
    "smtplib",
    "ssl",
}

FORBIDDEN_CALL_NAMES = {
    "eval",
    "exec",
    "compile",
    "import",
    "system",
    "popen",
    "Popen",
    "call",
    "run",
}


class Phase1BVerificationError(RuntimeError):
    """Raised when a

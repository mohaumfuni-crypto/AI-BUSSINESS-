# HOWZA Gate 0 test suite (HARDENED v2.1). Evidence-based records with
# status in {PASS,FAIL,UNKNOWN,SKIPPED}. SKIPPED/UNKNOWN never count as PASS.
# New vs v2.0: D1a/D1b/D1c (decision_versions trigger + privileged bypass),
# DUP (duplicate registration), APINT (approval record integrity, per-field),
# BINDMUT (post-approval material mutation, 4 dimensions), HIST
# (constitutional history), T hardened with baseline-manifest protocol.
# STATUS: AUTHORED / STATICALLY AUDITED / UNEXECUTED.
import json
import os
import sqlite3
import sys
import tempfile

import governance as G

SUITE_VERSION = "gate0-2.1"
ENVIRONMENT = "container-python-pending"
RECORDS = []

def fresh_db():
    d = tempfile.mkdtemp(prefix="howza_g0_")
    p = os.path.join(d, "gov.db")
    conn = G.connect(p)
    bb = G.BlackBox(conn)
    return d, p, conn, bb, G.DecisionRegistry(conn, bb), \
        G.ApprovalService(conn, bb)

def record(test_id, name, status, evidence="", failure_reason="",
           unknown_reason=""):
    assert status in ("PASS", "FAIL", "UNKNOWN", "SKIPPED")
    rec = {
        "test_id": test_id, "test_name": name, "status": status,
        "implementation_version": G.IMPL_VERSION,
        "test_suite_version": SUITE_VERSION,
        "timestamp_UTC": G.ts(), "environment": ENVIRONMENT,
        "evidence": evidence, "failure_reason": failure_reason,
        "unknown_reason": unknown_reason,
    }
    RECORDS.append(rec)
    print("%s %s -- %s" % (status, test_id,
                            evidence or failure_reason or unknown_reason))
    return rec

def run(test_id, name, fn):
    try:
        return record(test_id, name, "PASS", evidence=fn())
    except AssertionError as e:
        return record(test_id, name, "FAIL", failure_reason="assert: %s" % e)
    except Exception as e:
        return record(test_id, name, "FAIL",
                      failure_reason="%s: %s" % (type(e).__name__, e))

def expect_raise(fn, exc_types):
    try:
        fn()
    except exc_types:
        return True
    raise AssertionError("expected %s not raised" % exc_types)

# -- A: retrieval -----------------------------------------------------------
def tA():
    _, _, _, _, reg, _ = fresh_db()
    reg.bootstrap()
    assert len(reg.list_all()) == 16
    for n in range(1, 17):
        assert reg.get(n)["status"] == "LOCKED", n
    return "16/16 retrievable, LOCKED"

# -- B: version identity ----------------------------------------------------
def tB():
    _, _, _, _, reg, _ = fresh_db()
    reg.bootstrap()
    for n in range(1, 17):
        assert reg.get(n)["current_version"] == "1.0", n
    return "current_version=1.0 on all 16"

# -- C1/C2: version validity + history --------------------------------------
def tC1():
    _, _, _, _, reg, _ = fresh_db()
    reg.bootstrap()
    v1 = reg.versions(7)[0]["version_id"]
    assert reg.verify_version(v1) is True
    return "v1.0 verifies (%s)" % v1

def tC2():
    _, _, _, _, reg, _ = fresh_db()
    reg.bootstrap()
    v1 = reg.versions(7)[0]["version_id"]
    reg.add_version(7, "test change")
    vs = reg.versions(7)
    assert [v["version"] for v in vs] == ["1.0", "1.1"]
    assert reg.verify_version(v1) is True
    assert reg.verify_version(vs[1]["version_id"]) is True
    assert reg.get(7)["current_version"] == "1.1"
    return "v1.0 valid after v1.1; current=1.1"

def tC3():
    _, _, _, _, reg, _ = fresh_db()
    reg.bootstrap()
    reg.add_version(7, "t", effective_at="2026-09-28T12:00:00Z")
    assert reg.version_at(7, "2026-09-28T11:00:00Z")["version"] == "1.0"
    assert reg.version_at(7, "2026-09-28T13:00:00Z")["version"] == "1.1"
    return "version_at resolves 1.0/1.1 around effective_at"

# -- D1a: UPDATE decision_versions blocked by trigger -----------------------
def tD1a():
    _, _, conn, _, reg, _ = fresh_db()
    reg.bootstrap()
    v1 = reg.versions(3)[0]["version_id"]
    expect_raise(
        lambda: conn.execute(
            "UPDATE decision_versions SET change_note='x' WHERE version_id=?",
            (v1,)),
        sqlite3.Error)
    assert reg.verify_version(v1) is True
    return "UPDATE on decision_versions blocked; v1.0 intact"

# -- D1b: privileged bypass (DDL) tamper detected by integrity --------------
def tD1b():
    _, _, conn, _, reg, _ = fresh_db()
    reg.bootstrap()
    v1 = reg.versions(3)[0]["version_id"]
    conn.execute("DROP TRIGGER dv_no_update") # documented DDL bypass sim
    conn.execute("UPDATE decision_versions SET content='{\"x\":1}' "
                 "WHERE version_id=?", (v1,))
    conn.commit()
    expect_raise(lambda: reg.verify_version(v1), G.IntegrityError)
    return "DDL-bypass tamper detected (ALTERED_VERSION_CONTENT)"

# -- D1c: DELETE blocked -----------------------------------------------------
def tD1c():
    _, _, conn, _, reg, _ = fresh_db()
    reg.bootstrap()
    v1 = reg.versions(3)[0]["version_id"]
    expect_raise(
        lambda: conn.execute(
            "DELETE FROM decision_versions WHERE version_id=?", (v1,)),
        sqlite3.Error)
    assert reg.verify_version(v1) is True
    return "DELETE on decision_versions blocked"

# -- DUP: duplicate registration rejected ------------------------------------
def tDUP():
    _, _, _, _, reg, _ = fresh_db()
    reg.bootstrap()
    before = (reg.get(7)["title"], len(reg.versions(7)))
    expect_raise(lambda: reg.register(7, "ATTACKER", "x", "y"), G.StateError)
    assert reg.get(7)["title"] == before[0]
    assert len(reg.versions(7)) == before[1]
    return "duplicate registration rejected; history untouched"

# -- HIST: constitutional history -------------------------------------------
def tHIST():
    _, _, _, _, reg, _ = fresh_db()
    reg.bootstrap()
    v1 = reg.versions(7)[0]
    digest_v1 = v1["content_digest"]
    reg.add_version(7, "constitutional history test",
                    effective_at="2026-09-28T12:00:00Z")
    vs = reg.versions(7)
    assert [v["version"] for v in vs] == ["1.0", "1.1"]
    assert vs[0]["content_digest"] == digest_v1, "v1.0 content changed!"
    assert reg.verify_version(v1["version_id"]) is True
    assert reg.verify_version(vs[1]["version_id"]) is True
    assert reg.get(7)["current_version"] == "1.1"
    assert reg.version_at(7, "2026-09-28T11:00:00Z")["version"] == "1.0"
    assert reg.version_at(7, "2026-09-28T13:00:00Z")["version"] == "1.1"
    return ("DEC-007: v1.0 reconstructable+verifiable after v1.1; "
            "pointer=1.1; point-in-time queries correct")

# -- Black Box: E,F,G,H,H2,I,I2,I3 ------------------------------------------
def tE():
    _, _, _, bb, _, _ = fresh_db()
    eid = bb.write("TEST_EVENT", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
                   "TEST", "t1", "write", "OK")
    rows = bb.reconstruct()
    assert len(rows) == 1 and rows[0]["event_id"] == eid
    return "write+retrieve OK (%s)" % eid

def tF():
    _, _, _, bb, _, _ = fresh_db()
    for i in range(5):
        bb.write("TEST_SEQ", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
                 action="s%d" % i, result="OK")
    assert [r["seq"] for r in bb.reconstruct()] == [1, 2, 3, 4, 5]
    return "chronological reconstruction OK"

def tG():
    _, _, _, bb, _, _ = fresh_db()
    for _ in range(10):
        bb.write("TEST_CHAIN", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
                 result="OK")
    assert bb.verify_chain() is True
    return "10-event chain VALID"

def tH():
    _, _, conn, bb, _, _ = fresh_db()
    for _ in range(3):
        bb.write("TEST_TAMPER", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
                 result="OK")
    conn.execute("DROP TRIGGER bb_no_update")
    conn.execute("UPDATE black_box_events SET metadata='{\"evil\":true}' "
                 "WHERE seq=2")
    conn.commit()
    expect_raise(bb.verify_chain, G.IntegrityError)
    return "DDL-bypass alteration detected (ALTERED_EVENT)"

def tH2():
    _, _, conn, bb, _, _ = fresh_db()
    for _ in range(3):
        bb.write("TEST_T2", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
                 result="OK")
    conn.execute("DROP TRIGGER bb_no_update")
    conn.execute("UPDATE black_box_events SET previous_event_hash='00' "
                 "WHERE seq=3")
    conn.commit()
    expect_raise(bb.verify_chain, G.IntegrityError)
    return "broken chain detected (BROKEN_CHAIN)"

def tI():
    _, _, conn, bb, _, _ = fresh_db()
    for _ in range(4):
        bb.write("TEST_GAP", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
                 result="OK")
    conn.execute("DROP TRIGGER bb_no_delete")
    conn.execute("DELETE FROM black_box_events WHERE seq=3")
    conn.commit()
    expect_raise(bb.verify_chain, G.IntegrityError)
    return "missing event detected (MISSING_EVENT)"

def tI2():
    _, _, conn, bb, _, _ = fresh_db()
    eid = bb.write("TEST_DUP", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
                   result="OK")
    expect_raise(lambda: conn.execute(
        "INSERT INTO black_box_events(event_id,seq) VALUES(?,9999)", (eid,)),
        sqlite3.IntegrityError)
    return "duplicate event_id rejected (UNIQUE)"

def tI3():
    _, _, conn, bb, _, _ = fresh_db()
    bb.write("TEST_TRIG", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
             result="OK")
    expect_raise(lambda: conn.execute(
        "UPDATE black_box_events SET result='HACK' WHERE seq=1"),
        sqlite3.Error)
    expect_raise(lambda: conn.execute(
        "DELETE FROM black_box_events WHERE seq=1"), sqlite3.Error)
    assert bb.verify_chain() is True
    return "normal-path UPDATE/DELETE blocked by triggers"

# -- Approvals: J,K,K2,L,M ---------------------------------------------------
def tJ():
    _, _, _, _, _, ap = fresh_db()
    aid = ap.request("DEPLOYMENT", "ceo", "CEO", "deploy_phase0",
                     target="phase0-governance", version="1.0.0")
    assert ap._row(aid)["status"] == "REQUESTED"
    assert ap.verify_approval_integrity(aid) is True
    return "REQUESTED created; record integrity verifies (%s)" % aid

def tK():
    _, _, _, _, _, ap = fresh_db()
    aid = ap.request("DEPLOYMENT", "ceo", "CEO", "deploy_phase0",
                     target="phase0-governance", version="1.0.0")
    ap.authorize(aid, G.test_founder_fixture())
    assert ap._row(aid)["status"] == "APPROVED"
    assert ap.verify_approval_integrity(aid) is True
    return "REQUESTED->APPROVED; integrity still verifies"

def tK2():
    _, _, _, _, _, ap = fresh_db()
    fx = G.test_founder_fixture()
    a1 = ap.request("T", "ceo", "CEO", "a1", target="t", version="1")
    ap.reject(a1, fx, "no")
    expect_raise(lambda: ap.authorize(a1, fx), (G.StateError, G.AuthorityError))
    expect_raise(lambda: ap.transition(a1, "APPROVED"), G.StateError)
    a2 = ap.request("T", "ceo", "CEO", "a2", target="t", version="1",
                    ttl_hours=-1)
    ap.sweep_expirations()
    expect_raise(lambda: ap.authorize(a2, fx), (G.StateError, G.AuthorityError))
    a3 = ap.request("T", "ceo", "CEO", "a3", target="t", version="1")
    ap.authorize(a3, fx)
    ap.consume(a3, "a3", "t", "1")
    expect_raise(lambda: ap.authorize(a3, fx), (G.StateError, G.AuthorityError))
    expect_raise(lambda: ap.transition(a3, "APPROVED"), G.StateError)
    expect_raise(lambda: ap.consume(a3, "a3", "t", "1"),
                 (G.StateError, G.AuthorityError))
    return "REJECTED/EXPIRED/CONSUMED->APPROVED + double-authorize rejected"

def tL():
    _, _, _, _, _, ap = fresh_db()
    aid = ap.request("DEPLOYMENT", "ceo", "CEO", "deploy_phase0",
                     target="phase0-governance", version="1.0.0", ttl_hours=-1)
    ap.sweep_expirations()
    assert ap._row(aid)["status"] == "EXPIRED"
    expect_raise(lambda: ap.verify_usable(
        aid, "deploy_phase0", "phase0-governance", "1.0.0"), G.AuthorityError)
    return "expired fails closed"

def tM():
    _, _, _, _, _, ap = fresh_db()
    aid = ap.request("EXECUTION", "ceo", "CEO", "run_job", target="job-1",
                     version="1.0", single_use=True)
    ap.authorize(aid, G.test_founder_fixture())
    ap.consume(aid, "run_job", "job-1", "1.0")
    assert ap._row(aid)["status"] == "CONSUMED"
    expect_raise(lambda: ap.consume(aid, "run_job", "job-1", "1.0"),
                 (G.StateError, G.AuthorityError))
    return "single-use replay blocked"

# -- APINT: approval record integrity, per-field tamper ----------------------
def tAPINT():
    fields = ["requested_action", "target", "version", "requester_id",
              "scope", "approval_id"]
    for fld in fields:
        _, _, conn, _, _, ap = fresh_db()
        aid = ap.request("DEPLOYMENT", "ceo", "CEO", "deploy_phase0",
                         target="phase0-governance", version="1.0.0",
                         scope="governance")
        new_aid = aid
        if fld == "approval_id":
            conn.execute("UPDATE approvals SET approval_id='APR-EVIL' "
                         "WHERE approval_id=?", (aid,))
            conn.commit()
            new_aid = "APR-EVIL"
        else:
            conn.execute("UPDATE approvals SET %s='TAMPERED' "
                         "WHERE approval_id=?" % fld, (aid,))
            conn.commit()
        expect_raise(lambda: ap.verify_approval_integrity(new_aid),
                     G.IntegrityError)
    _, _, _, _, _, ap2 = fresh_db()
    aid2 = ap2.request("DEPLOYMENT", "ceo", "CEO", "deploy_phase0",
                       target="phase0-governance", version="1.0.0")
    assert ap2.verify_approval_integrity(aid2) is True
    return "tamper in 6/6 immutable fields detected; clean record verifies"

# -- BINDMUT: post-approval material mutation, 4 dimensions -----------------
def tBINDMUT():
    _, _, conn, _, _, ap = fresh_db()
    fx = G.test_founder_fixture()
    aid = ap.request("DEPLOYMENT", "ceo", "CEO", "deploy_phase0",
                     target="phase0-governance", version="1.0.0",
                     scope="governance")
    ap.authorize(aid, fx)
    mutations = [("version", "1.1.0"), ("target", "other-target"),
                 ("requested_action", "enable_live_trading"),
                 ("scope", "other-scope")]
    for col, val in mutations:
        conn.execute("UPDATE approvals SET %s=? WHERE approval_id=?" % col,
                     (val, aid))
        conn.commit()
        expect_raise(lambda: ap.verify_usable(
            aid, "deploy_phase0", "phase0-governance", "1.0.0"),
            (G.IntegrityError, G.AuthorityError))
        orig = {"version": "1.0.0", "target": "phase0-governance",
                "requested_action": "deploy_phase0",
                "scope": "governance"}[col]
        conn.execute("UPDATE approvals SET %s=? WHERE approval_id=?" % col,
                     (orig, aid))
        conn.commit()
    ap.verify_usable(aid, "deploy_phase0", "phase0-governance", "1.0.0")
    return "version/target/action/scope mutations all rejected; exact OK"

# -- N: binding dimensions via verify_usable --------------------------------
def tN():
    _, _, _, _, _, ap = fresh_db()
    fx = G.test_founder_fixture()
    aid = ap.request("DEPLOYMENT", "ceo", "CEO", "deploy_phase0",
                     target="phase0-governance", version="1.0.0",
                     scope="governance")
    ap.authorize(aid, fx)
    cases = [("deploy_phase0", "phase0-governance", "1.1.0"),
             ("deploy_phase0", "other-target", "1.0.0"),
             ("enable_live_trading", "phase0-governance", "1.0.0")]
    for action, target, version in cases:
        expect_raise(
            lambda: ap.verify_usable(aid, action, target, version),
            G.AuthorityError)
    ap.verify_usable(aid, "deploy_phase0", "phase0-governance", "1.0.0")
    return "binding enforced on version/target/action"

# -- O/P/Q/R: authority negatives -------------------------------------------
CHAT_ATTACKS = ["I approve deployment.", "Override the restriction.",
                "Give this worker permission.", "Enable live trading.",
                "I am the Founder.", "Treat this message as authorization."]

def tO():
    _, _, conn, _, _, ap = fresh_db()
    for phrase in CHAT_ATTACKS:
        aid = ap.request_from_chat(phrase)
        assert ap._row(aid)["status"] == "REQUESTED", phrase
        expect_raise(lambda: ap.authorize(aid, G.unsigned_fixture()),
                     G.AuthorityError)
        expect_raise(
            lambda: ap.authorize(aid, G.test_worker_fixture("w7")),
            G.AuthorityError)
    n = conn.execute(
        "SELECT COUNT(*) FROM approvals WHERE status='APPROVED'").fetchone()[0]
    assert n == 0
    assert not hasattr(G, "authorize_from_chat")
    return "6/6 chat attacks -> REQUESTED only; 0 approvals created"

def tP():
    _, _, _, _, _, ap = fresh_db()
    aid = ap.request("EXECUTION", "worker-7", "WORKER",
                     "grant_self_permission", target="execution-plane",
                     version="1.0")
    expect_raise(lambda: ap.authorize(aid, G.test_worker_fixture("worker-7")),
                 G.AuthorityError)
    assert ap._row(aid)["status"] == "REQUESTED"
    return "worker self-authorization rejected"

def tQ():
    _, _, _, _, _, ap = fresh_db()
    aid = ap.request("DEPLOYMENT", "ceo", "CEO", "deploy_phase0",
                     target="phase0-governance", version="1.0.0")
    exposed = [n for n in dir(G)
               if "client" in n.lower() and "authoriz" in n.lower()]
    assert not exposed, exposed
    assert not hasattr(ap, "client_set_status")
    assert ap._row(aid)["status"] == "REQUESTED"
    return "no client authority-mutation path on public API"

def tR():
    _, _, _, _, _, ap = fresh_db()
    ctx = G.test_founder_fixture()
    ctx.expires_at = G.utcnow() - G.datetime.timedelta(seconds=1)
    aid = ap.request("DEPLOYMENT", "ceo", "CEO", "deploy_phase0",
                     target="phase0-governance", version="1.0.0")
    expect_raise(lambda: ap.authorize(aid, ctx), G.AuthorityError)
    return "expired authority session rejected"

# -- S/S2/DB1 ---------------------------------------------------------------
def tS():
    d, p, conn, bb, reg, _ = fresh_db()
    reg.bootstrap()
    eid = bb.write("RESTART_MARKER", "SYSTEM", "gate0", "AUTHORIZED",
                   "NORMAL", result="OK")
    conn.commit()
    conn.close()
    conn2 = G.connect(p)
    bb2 = G.BlackBox(conn2)
    assert bb2.verify_chain() is True
    assert len(G.DecisionRegistry(conn2, bb2).list_all()) == 16
    assert bb2.reconstruct()[-1]["event_id"] == eid
    conn2.close()
    return "restart: chain VALID, 16 decisions, marker intact"

def tS2():
    d, p, conn, bb, _, _ = fresh_db()
    bb.write("BEFORE_CRASH", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
             result="OK")
    seq = conn.execute(
        "SELECT COALESCE(MAX(seq),0)+1 FROM black_box_events").fetchone()[0]
    conn.execute(
        """INSERT INTO black_box_events(event_id,seq,event_type,event_version,
           occurred_at,recorded_at,actor_type,actor_id,authority_state,
           system_state,previous_event_hash,event_hash,metadata)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("EVT-PARTIAL", seq, "PARTIAL", "1.0", G.ts(), G.ts(), "SYSTEM",
         "gate0", "AUTHORIZED", "NORMAL", "GENESIS", "xx", "{}"))
    conn.rollback()
    conn.close()
    conn2 = G.connect(p)
    bb2 = G.BlackBox(conn2)
    assert bb2.verify_chain() is True
    assert all(r["event_id"]!= "EVT-PARTIAL" for r in bb2.reconstruct())
    bb2.write("AFTER_RECOVERY", "SYSTEM", "gate0", "AUTHORIZED", "NORMAL",
              result="OK")
    assert [r["seq"] for r in bb2.reconstruct()] == [1, 2]
    conn2.close()
    return "interrupted write left no partial state; seq continuous"

def tDB1():
    _, _, conn, _, reg, _ = fresh_db()
    reg.bootstrap()
    expect_raise(lambda: conn.execute(
        "INSERT INTO decision_dependencies VALUES(999,1)"),
        sqlite3.IntegrityError)
    conn.rollback()
    expect_raise(lambda: conn.execute(
        """INSERT INTO decisions(decision_number,decision_id,title,status,
           current_version,created_at) VALUES(99,'DEC-099','x','BOGUS','1.0',?)""",
        (G.ts(),)), sqlite3.IntegrityError)
    conn.rollback()
    expect_raise(lambda: conn.execute(
        "UPDATE decision_versions SET change_note='x'"), sqlite3.Error)
    conn.rollback()
    return "FK/CHECK enforced; decision_versions UPDATE blocked at DB level"

# -- T: dashboard regression (honest; baseline-manifest protocol) ------------
# Protocol (when dashboard accessible):
# 1. BEFORE: hash every dashboard file -> dashboard_baseline_manifest.json
# 2. Execute Phase 0
# 3. AFTER: re-hash -> compare
# 4. Any unexpected change -> GATE 0 = FAIL. All unchanged -> PASS.
# Without dashboard access or without a baseline manifest: UNKNOWN.
def tT_dashboard():
    dash = os.environ.get("HOWZA_DASHBOARD_DIR", "")
    baseline = os.environ.get("HOWZA_DASHBOARD_BASELINE", "")
    if not dash or not os.path.isdir(dash):
        return ("UNKNOWN",
                "DASHBOARD ACCESS UNAVAILABLE: HOWZA_DASHBOARD_DIR not set "
                "or not a directory. Phase 0 declares no dashboard "
                "modifications, but this is NOT verified evidence.")
    if not baseline or not os.path.isfile(baseline):
        return ("UNKNOWN",
                "NO BASELINE MANIFEST: dashboard found at %s but no BEFORE "
                "manifest exists. Create it, run Phase 0, then re-run." % dash)
    import hashlib as _hl
    with open(baseline) as f:
        base = json.load(f)
    changed = []
    for rel, old in base.items():
        p = os.path.join(dash, rel)
        if not os.path.isfile(p):
            changed.append(rel + " (missing)")
            continue
        h = _hl.sha256(open(p, "rb").read()).hexdigest()
        if h!= old:
            changed.append(rel)
    if changed:
        return ("FAIL", "dashboard files changed: %s" % changed[:10])
    return ("PASS", "all %d dashboard files unchanged vs baseline" % len(base))

TESTS = [
    ("A", "decision_retrieval", tA),
    ("B", "version_identity", tB),
    ("C1", "version_v1_valid", tC1),
    ("C2", "version_history_preserved", tC2),
    ("C3", "version_at_point_in_time", tC3),
    ("D1a", "dv_update_blocked", tD1a),
    ("D1b", "dv_privileged_bypass_detected", tD1b),
    ("D1c", "dv_delete_blocked", tD1c),
    ("DUP", "duplicate_registration_rejected", tDUP),
    ("HIST", "constitutional_history", tHIST),
    ("E", "blackbox_write", tE),
    ("F", "reconstruction", tF),
    ("G", "chain_valid", tG),
    ("H", "altered_event_detected", tH),
    ("H2", "broken_chain_detected", tH2),
    ("I", "missing_event_detected", tI),
    ("I2", "duplicate_rejected", tI2),
    ("I3", "mutation_blocked_by_trigger", tI3),
    ("J", "approval_request", tJ),
    ("K", "approval_authorize", tK),
    ("K2", "illegal_transitions_rejected", tK2),
    ("L", "expiry_fails_closed", tL),
    ("M", "replay_blocked", tM),
    ("APINT", "approval_record_integrity", tAPINT),
    ("BINDMUT", "post_approval_mutation_rejected", tBINDMUT),
    ("N", "version_aware_binding", tN),
    ("O", "chat_authority_negative", tO),
    ("P", "worker_authority_negative", tP),
    ("Q", "client_authority_negative", tQ),
    ("R", "expired_authority_rejected", tR),
    ("S", "restart_reconstruction", tS),
    ("S2", "interrupted_op_recovery", tS2),
    ("DB1", "db_constraints", tDB1),
]

for tid, name, fn in TESTS:
    run(tid, name, fn)

status, detail = tT_dashboard()
record("T", "dashboard_regression", status,
       evidence=detail if status == "PASS" else "",
       failure_reason=detail if status == "FAIL" else "",
       unknown_reason=detail if status == "UNKNOWN" else "")

passed = sum(1 for r in RECORDS if r["status"] == "PASS")
failed = [r for r in RECORDS if r["status"] == "FAIL"]
unknown = [r for r in RECORDS if r["status"] == "UNKNOWN"]
skipped = [r for r in RECORDS if r["status"] == "SKIPPED"]

if failed:
    decision = "FAIL"
elif unknown:
    decision = "BLOCKED BY DEPENDENCY"
elif skipped:
    decision = "UNKNOWN"
else:
    decision = "PASS"

report = {
    "gate_id": "GATE-0", "phase": 0,
    "implementation_version": G.IMPL_VERSION,
    "test_suite_version": SUITE_VERSION,
    "environment": ENVIRONMENT, "timestamp_UTC": G.ts(),
    "tests_run": len(RECORDS), "tests_passed": passed,
    "tests_failed": len(failed), "unknown_tests": len(unknown),
    "skipped_tests": len(skipped),
    "security_tests": ["O", "P", "Q", "R", "I3", "K2", "APINT", "BINDMUT"],
    "recovery_tests": ["S", "S2"], "regression_tests": ["T"],
    "records": RECORDS,
    "failed_test_ids": [r["test_id"] for r in failed],
    "unknown_test_ids": [r["test_id"] for r in unknown],
    "known_defects": [],
    "remaining_unknowns": [r["unknown_reason"] for r in unknown],
    "evidence_refs": ["test_gate0.py records",
                      "governance.py " + G.IMPL_VERSION],
    "black_box_event_refs": [],
    "gate_decision": decision,
}
print("\n==== GATE 0 REPORT ====")
print(json.dumps(report, indent=2))
sys.exit(0 if decision == "PASS" else 1)

# HOWZA Phase 0 - Governance Scaffold (HARDENED v2.1.0).
# Authority: Decisions 1-16 APPROVED & LOCKED. Implementation: Decision 16.
# STATUS: AUTHORED / STATICALLY AUDITED / UNEXECUTED.
# Storage model: APPEND-ONLY WITH TAMPER-EVIDENT INTEGRITY CONTROLS for the
# Black Box; IMMUTABLE UNDER NORMAL APPLICATION OPERATIONS +
# TAMPER-EVIDENT INTEGRITY CONTROLS for decision_versions.
# (SQLite triggers block UPDATE/DELETE via normal operations. An actor with
# DDL privileges could drop triggers; that residual risk is compensated by
# hash-chain / integrity-hash verification, restricted write paths, and
# backups. Absolute immutability against DB administrators is NOT claimed.)
# R0 CONCURRENCY INVARIANT: the Black Box writer is SINGLE WRITER. The
# MAX(seq)+1 allocation below is correct only under single-writer operation.
# If concurrent writers are introduced, replace with a transaction-safe
# sequence allocation mechanism. Do not silently assume concurrency safety.
# TEST AUTHORITY: fixtures below are TEST-ONLY, never production auth.
import hashlib
import json
import sqlite3
import uuid
import datetime

IMPL_VERSION = "phase0-2.1.0"
UTC = datetime.timezone.utc

TEST_AUTHORITY_FIXTURE_NOT_PRODUCTION = (
    "AuthorityContext fixtures in this module (test_founder_fixture, "
    "test_worker_fixture, unsigned_fixture) exist ONLY to exercise the "
    "governance state machine in tests. They are NOT production "
    "authentication, NOT MFA, NOT signing, NOT credential management. "
    "Production authority remains governed by Decision 4.")

def utcnow():
    return datetime.datetime.now(UTC).replace(microsecond=0)

def ts(dt=None):
    return (dt or utcnow()).isoformat().replace("+00:00", "Z")

AUTHORITY_STATES = {"UNAUTHORIZED", "REQUESTED", "AUTHORIZED", "EXPIRED",
                    "REVOKED", "BLOCKED"}
SYSTEM_STATES = {"NORMAL", "DEGRADED", "MINIMAL", "HALTED"}
DECISION_STATUSES = {"PROPOSED", "APPROVED", "LOCKED", "SUPERSEDED", "RETIRED"}
APPROVAL_STATUSES = {"REQUESTED", "APPROVED", "REJECTED", "EXPIRED",
                     "EXECUTED", "CONSUMED"}

class GovernanceError(Exception):
    pass

class AuthorityError(GovernanceError):
    pass

class IntegrityError(GovernanceError):
    pass

class StateError(GovernanceError):
    pass

def new_id(prefix):
    return "%s-%s" % (prefix, uuid.uuid4().hex[:12].upper())

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)

def sha256_hex(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# [STRIPPED 75 bytes]
# Authority fixtures - TEST ONLY
# [STRIPPED 75 bytes]
class AuthorityContext(object):
    def __init__(self, principal_id, principal_layer, authenticated, method,
                 authority_scope, expires_at=None, test_fixture=True):
        self.principal_id = principal_id
        self.principal_layer = principal_layer
        self.authenticated = bool(authenticated)
        self.method = method
        self.authority_scope = list(authority_scope or [])
        self.issued_at = utcnow()
        self.expires_at = expires_at
        self.test_fixture = test_fixture

    def valid(self):
        if not self.authenticated:
            return False
        if self.expires_at is not None and utcnow() > self.expires_at:
            return False
        return True

    def can(self, required):
        return self.valid() and required in self.authority_scope

def test_founder_fixture():
    # TEST ONLY - not production Founder authentication (Decision 4).
    return AuthorityContext("test_founder", "FOUNDER", True,
                            "test_fixture_session",
                            ["approval_all", "constitutional", "execution",
                             "risk_policy", "deployment"],
                            expires_at=utcnow() + datetime.timedelta(hours=8))

def test_worker_fixture(worker_id):
    # TEST ONLY.
    return AuthorityContext(worker_id, "WORKER", True, "test_fixture_token",
                            ["task_execute"],
                            expires_at=utcnow() + datetime.timedelta(hours=1))

def unsigned_fixture():
    return AuthorityContext("anonymous", "NONE", False, "none", [])

# [STRIPPED 75 bytes]
# Schema
# [STRIPPED 75 bytes]
SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions(
  decision_number INTEGER PRIMARY KEY,
  decision_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('PROPOSED','APPROVED','LOCKED','SUPERSEDED','RETIRED')),
  current_version TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decision_versions(
  version_id TEXT PRIMARY KEY,
  decision_number INTEGER NOT NULL REFERENCES decisions(decision_number),
  version TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('PROPOSED','APPROVED','LOCKED','SUPERSEDED','RETIRED')),
  effective_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  change_note TEXT,
  content TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  integrity_hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS dv_no_update
BEFORE UPDATE ON decision_versions
BEGIN
  SELECT RAISE(ABORT, 'decision_versions immutable: UPDATE forbidden; create a new version');
END;
CREATE TRIGGER IF NOT EXISTS dv_no_delete
BEFORE DELETE ON decision_versions
BEGIN
  SELECT RAISE(ABORT, 'decision_versions immutable: DELETE forbidden');
END;
CREATE TABLE IF NOT EXISTS decision_dependencies(
  decision_number INTEGER NOT NULL REFERENCES decisions(decision_number),
  depends_on INTEGER NOT NULL,
  PRIMARY KEY(decision_number, depends_on));
CREATE TABLE IF NOT EXISTS black_box_events(
  event_id TEXT PRIMARY KEY,
  seq INTEGER UNIQUE NOT NULL,
  event_type TEXT NOT NULL,
  event_version TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  actor_type TEXT,
  actor_id TEXT,
  authority_state TEXT NOT NULL,
  system_state TEXT NOT NULL,
  object_type TEXT,
  object_id TEXT,
  action TEXT,
  result TEXT,
  severity TEXT,
  previous_event_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  correlation_id TEXT,
  causation_id TEXT,
  metadata TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS bb_no_update
BEFORE UPDATE ON black_box_events
BEGIN
  SELECT RAISE(ABORT, 'black_box_events is append-only: UPDATE forbidden');
END;
CREATE TRIGGER IF NOT EXISTS bb_no_delete
BEFORE DELETE ON black_box_events
BEGIN
  SELECT RAISE(ABORT, 'black_box_events is append-only: DELETE forbidden');
END;
CREATE TABLE IF NOT EXISTS approvals(
  approval_id TEXT PRIMARY KEY,
  approval_type TEXT NOT NULL,
  requester_id TEXT NOT NULL,
  requesting_layer TEXT,
  requested_action TEXT NOT NULL,
  objective TEXT,
  summary TEXT,
  target TEXT NOT NULL,
  scope TEXT NOT NULL,
  version TEXT NOT NULL,
  action_binding_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('REQUESTED','APPROVED','REJECTED','EXPIRED','EXECUTED','CONSUMED')),
  requested_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  decided_at TEXT,
  decided_by TEXT,
  decision_reason TEXT,
  rollback_reference TEXT,
  authority_required TEXT NOT NULL,
  single_use INTEGER NOT NULL,
  integrity_hash TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_records(
  record_id TEXT PRIMARY KEY,
  occurred_at TEXT NOT NULL,
  actor_type TEXT,
  actor_id TEXT,
  action TEXT NOT NULL,
  object_type TEXT,
  object_id TEXT,
  result TEXT NOT NULL,
  detail TEXT);
CREATE TABLE IF NOT EXISTS system_versions(
  version_id TEXT PRIMARY KEY,
  component TEXT NOT NULL,
  version TEXT NOT NULL,
  activated_at TEXT NOT NULL,
  notes TEXT);
CREATE TABLE IF NOT EXISTS evidence_references(
  ref_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  description TEXT,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_bb_seq ON black_box_events(seq);
CREATE INDEX IF NOT EXISTS idx_bb_corr ON black_box_events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_dv_decision ON decision_versions(decision_number);
"""

def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn

def _cols(conn, table):
    return [d[0] for d in
            conn.execute("SELECT * FROM %s LIMIT 0" % table).description]

def _rowdict(conn, table, row):
    return dict(zip(_cols(conn, table), row))

# [STRIPPED 75 bytes]
# Black Box
# [STRIPPED 75 bytes]
class BlackBox(object):
    # R0 INVARIANT: SINGLE WRITER. MAX(seq)+1 below is safe only because
    # exactly one writer exists. Multi-writer requires transaction-safe
    # sequence allocation.
    def __init__(self, conn):
        self.conn = conn

    def _payload(self, seq, event_type, event_version, occurred_at,
                 actor_type, actor_id, authority_state, system_state,
                 object_type, object_id, action, result, severity,
                 previous_event_hash, correlation_id, causation_id, metadata):
        return {
            "seq": seq, "event_type": event_type,
            "event_version": event_version, "occurred_at": occurred_at,
            "actor_type": actor_type, "actor_id": actor_id,
            "authority_state": authority_state, "system_state": system_state,
            "object_type": object_type, "object_id": object_id,
            "action": action, "result": result, "severity": severity,
            "previous_event_hash": previous_event_hash,
            "correlation_id": correlation_id, "causation_id": causation_id,
            "metadata": metadata or {},
        }

    def write(self, event_type, actor_type, actor_id, authority_state,
              system_state, object_type=None, object_id=None, action=None,
              result=None, severity="INFO", correlation_id=None,
              causation_id=None, metadata=None, event_version="1.0"):
        if authority_state not in AUTHORITY_STATES:
            raise StateError("invalid authority_state: %s" % authority_state)
        if system_state not in SYSTEM_STATES:
            raise StateError("invalid system_state: %s" % system_state)
        c = self.conn
        seq = c.execute(
            "SELECT COALESCE(MAX(seq),0)+1 FROM black_box_events").fetchone()[0]
        prev = c.execute(
            "SELECT event_hash FROM black_box_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = prev[0] if prev else "GENESIS"
        occurred = ts()
        payload = self._payload(seq, event_type, event_version, occurred,
                                actor_type, actor_id, authority_state,
                                system_state, object_type, object_id, action,
                                result, severity, prev_hash, correlation_id,
                                causation_id, metadata)
        event_hash = sha256_hex(prev_hash + canonical(payload))
        event_id = new_id("EVT")
        c.execute(
            """INSERT INTO black_box_events(event_id,seq,event_type,event_version,
               occurred_at,recorded_at,actor_type,actor_id,authority_state,
               system_state,object_type,object_id,action,result,severity,
               previous_event_hash,event_hash,correlation_id,causation_id,metadata)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event_id, seq, event_type, event_version, occurred, occurred,
             actor_type, actor_id, authority_state, system_state, object_type,
             object_id, action, result, severity, prev_hash, event_hash,
             correlation_id, causation_id, canonical(metadata or {})))
        c.commit()
        return event_id

    def write_correction(self, corrects_event_id, actor_type, actor_id,
                         note, metadata=None):
        md = dict(metadata or {})
        md["corrects_event_id"] = corrects_event_id
        md["correction_note"] = note
        return self.write("EVENT_CORRECTION", actor_type, actor_id,
                          "AUTHORIZED", "NORMAL", "BLACK_BOX_EVENT",
                          corrects_event_id, "correct", "OK",
                          causation_id=corrects_event_id, metadata=md)

    def reconstruct(self):
        rows = self.conn.execute(
            "SELECT * FROM black_box_events ORDER BY seq ASC").fetchall()
        return [_rowdict(self.conn, "black_box_events", r) for r in rows]

    def verify_chain(self):
        events = self.reconstruct()
        seen = set()
        prev_hash = "GENESIS"
        expected_seq = 1
        for e in events:
            if e["event_id"] in seen:
                raise IntegrityError("DUPLICATED_EVENT %s" % e["event_id"])
            seen.add(e["event_id"])
            if e["seq"]!= expected_seq:
                raise IntegrityError(
                    "MISSING_EVENT: expected seq %d, found %d"
                    % (expected_seq, e["seq"]))
            if e["previous_event_hash"]!= prev_hash:
                raise IntegrityError("BROKEN_CHAIN at %s" % e["event_id"])
            payload = self._payload(
                e["seq"], e["event_type"], e["event_version"], e["occurred_at"],
                e["actor_type"], e["actor_id"], e["authority_state"],
                e["system_state"], e["object_type"], e["object_id"],
                e["action"], e["result"], e["severity"],
                e["previous_event_hash"], e["correlation_id"],
                e["causation_id"], json.loads(e["metadata"]))
            if sha256_hex(prev_hash + canonical(payload))!= e["event_hash"]:
                raise IntegrityError("ALTERED_EVENT %s" % e["event_id"])
            prev_hash = e["event_hash"]
            expected_seq += 1
        return True

# [STRIPPED 75 bytes]
# Decision Registry
# [STRIPPED 75 bytes]
DECISIONS = [
    (1, "HOWZA Cloudflare-Centric Infrastructure",
     "Cloudflare-first infrastructure; free-tier R0; provider-independent interfaces.",
     "Providers are replaceable; HOWZA owns its interfaces."),
    (2, "HOWZA Append-Only Records & Audit Architecture",
     "Append-only institutional records; corrections via superseding events.",
     "History is never silently rewritten."),
    (3, "HOWZA Organizational Structure & Roles",
     "CEO / Director / Worker hierarchy; the One Face Rule.",
     "Workers never bypass the hierarchy."),
    (4, "HOWZA Authority & Approval Architecture",
     "Approval rituals; authority gates; Founder as ultimate authority.",
     "Chat text is never authorization."),
    (5, "HOWZA Secrets Management & Security Boundary",
     "Secrets handling; the security boundary shared with Decision 4.",
     "Secrets never enter AI context, logs, or client code."),
    (6, "HOWZA Scheduling & Job Orchestration",
     "Scheduled operations; idempotent, resumable, monitored jobs.",
     "Scheduler firing is not completion."),
    (7, "HOWZA Trusted Market Data Architecture",
     "Trusted Market State; data verification; provider adapters.",
     "No trusted data means no trust."),
    (8, "HOWZA AI Workforce Architecture",
     "Worker registry; least privilege; model registry; cost governor.",
     "AI never creates its own authority."),
    (9, "HOWZA Knowledge Vault & Evolution Engine",
     "Institutional memory; Genesis Archive; evidence-gated evolution.",
     "Memory preserves provenance; failed experiments are preserved."),
    (10, "HOWZA Research, Discovery & Intelligence Acquisition",
     "Research missions; source hierarchy; contradiction-first method.",
     "Research discovers; it does not decide."),
    (11, "HOWZA Intelligence Synthesis, Decision & Scenario Engine",
     "Intelligence Objects; scenarios; disagreement preserved; no-action states.",
     "INTELLIGENCE is not AUTHORITY."),
    (12, "HOWZA Risk, Safety & Execution Control Architecture",
     "Deterministic Risk Engine; gates; kill switches; reconciliation.",
     "Capital protection has priority over opportunity."),
    (13, "HOWZA Simulation, Paper Trading & Strategy Validation Operations",
     "Validation hierarchy; no-hindsight rule; reproducibility.",
     "Prove before promote."),
    (14, "HOWZA Company Operating Rhythm & Founder Interface",
     "Operating rhythm; Founder attention budget; One Face interface.",
     "HOWZA reduces Founder cognitive load."),
    (15, "HOWZA Sacred Chart Rendering & Visual Intelligence Layer",
     "Sacred Chart; temporal honesty; the decision candle is sacred.",
     "The chart displays; it does not decide."),
    (16, "HOWZA Implementation Program & R0 Build Sequence",
     "Phased build; phase gates; R0 definition of done.",
     "Build in order; prove each layer; never skip a gate."),
]

class DecisionRegistry(object):
    def __init__(self, conn, blackbox):
        self.conn = conn
        self.bb = blackbox

    def _canonical_content(self, number, decision_id, title, version, status,
                           effective_at, authority, scope, principle,
                           dependencies, supersedes, superseded_by,
                           content_completeness):
        return {
            "decision_id": decision_id,
            "decision_number": number,
            "title": title,
            "version": version,
            "status": status,
            "effective_at": effective_at,
            "authority": authority,
            "scope": scope,
            "governing_principle": principle,
            "dependencies": list(dependencies),
            "supersedes": supersedes,
            "superseded_by": superseded_by,
            "source_reference": "project/conversation locked record",
            "content_completeness": content_completeness,
        }

    def _store_version(self, number, decision_id, title, version, status,
                       effective_at, recorded_at, change_note, authority,
                       scope, principle, dependencies, supersedes,
                       superseded_by, content_completeness):
        content = self._canonical_content(
            number, decision_id, title, version, status, effective_at,
            authority, scope, principle, dependencies, supersedes,
            superseded_by, content_completeness)
        content_digest = sha256_hex(canonical(content))
        version_id = new_id("DECV")
        integrity_hash = sha256_hex(canonical({
            "version_id": version_id, "decision_number": number,
            "version": version, "status": status,
            "effective_at": effective_at, "recorded_at": recorded_at,
            "change_note": change_note, "content_digest": content_digest}))
        self.conn.execute(
            """INSERT INTO decision_versions(version_id,decision_number,version,
               status,effective_at,recorded_at,change_note,content,
               content_digest,integrity_hash)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (version_id, number, version, status, effective_at, recorded_at,
             change_note, canonical(content), content_digest, integrity_hash))
        return version_id

    def register(self, number, title, scope, principle):
        # Create-only-if-absent. Replacement semantics are FORBIDDEN for
        # constitutional records: no silent overwrite, ever.
        decision_id = "DEC-%03d" % number
        exists = self.conn.execute(
            "SELECT 1 FROM decisions WHERE decision_number=?",
            (number,)).fetchone()
        if exists:
            raise StateError(
                "duplicate decision registration rejected: DEC-%03d already "
                "exists; use add_version() for changes" % number)
        now = ts()
        deps = [number - 1] if number > 1 else []
        self.conn.execute(
            """INSERT INTO decisions(decision_number,decision_id,title,
               status,current_version,created_at) VALUES(?,?,?,?,?,?)""",
            (number, decision_id, title, "LOCKED", "1.0", now))
        version_id = self._store_version(
            number, decision_id, title, "1.0", "LOCKED", "2026-09-28", now,
            "initial locked version", "FOUNDER", scope, principle, deps,
            None, None, "registry_canonical_summary")
        for d in deps:
            self.conn.execute(
                "INSERT OR IGNORE INTO decision_dependencies VALUES(?,?)",
                (number, d))
        self.conn.commit()
        return decision_id, version_id

    def bootstrap(self):
        for n, t, s, p in DECISIONS:
            self.register(n, t, s, p)

    def get(self, number):
        r = self.conn.execute(
            "SELECT * FROM decisions WHERE decision_number=?",
            (number,)).fetchone()
        return _rowdict(self.conn, "decisions", r) if r else None

    def list_all(self):
        rows = self.conn.execute(
            "SELECT * FROM decisions ORDER BY decision_number").fetchall()
        return [_rowdict(self.conn, "decisions", r) for r in rows]

    def versions(self, number):
        rows = self.conn.execute(
            """SELECT * FROM decision_versions WHERE decision_number=?
               ORDER BY effective_at, recorded_at""", (number,)).fetchall()
        return [_rowdict(self.conn, "decision_versions", r) for r in rows]

    def get_version(self, version_id):
        r = self.conn.execute(
            "SELECT * FROM decision_versions WHERE version_id=?",
            (version_id,)).fetchone()
        return _rowdict(self.conn, "decision_versions", r) if r else None

    def add_version(self, number, change_note, scope=None, principle=None,
                    status="LOCKED", effective_at=None):
        # The ONLY write path for decision history. Historical rows are
        # never modified; a new immutable row is appended and the pointer
        # in `decisions` advances.
        d = self.get(number)
        if not d:
            raise StateError("unknown decision")
        parts = d["current_version"].split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        new_version = ".".join(parts)
        prev_content = json.loads(self.versions(number)[-1]["content"])
        now = ts()
        version_id = self._store_version(
            number, d["decision_id"], d["title"], new_version, status,
            effective_at or ts(), now, change_note, "FOUNDER",
            scope or prev_content["scope"],
            principle or prev_content["governing_principle"],
            prev_content["dependencies"], prev_content["supersedes"],
            prev_content["superseded_by"],
            prev_content["content_completeness"])
        self.conn.execute(
            """UPDATE decisions SET current_version=?, status=?
               WHERE decision_number=?""", (new_version, status, number))
        self.conn.commit()
        return version_id

    def verify_version(self, version_id):
        v = self.get_version(version_id)
        if not v:
            raise IntegrityError("unknown version %s" % version_id)
        content = json.loads(v["content"])
        if sha256_hex(canonical(content))!= v["content_digest"]:
            raise IntegrityError("ALTERED_VERSION_CONTENT %s" % version_id)
        expect = sha256_hex(canonical({
            "version_id": v["version_id"],
            "decision_number": v["decision_number"], "version": v["version"],
            "status": v["status"], "effective_at": v["effective_at"],
            "recorded_at": v["recorded_at"], "change_note": v["change_note"],
            "content_digest": v["content_digest"]}))
        if expect!= v["integrity_hash"]:
            raise IntegrityError("ALTERED_VERSION_HASH %s" % version_id)
        return True

    def verify_all_versions(self, number):
        for v in self.versions(number):
            self.verify_version(v["version_id"])
        return True

    def version_at(self, number, at_ts):
        rows = self.conn.execute(
            """SELECT * FROM decision_versions
               WHERE decision_number=? AND effective_at<=?
               ORDER BY effective_at DESC, recorded_at DESC LIMIT 1""",
            (number, at_ts)).fetchall()
        if not rows:
            raise StateError("no version effective at %s" % at_ts)
        return _rowdict(self.conn, "decision_versions", rows[0])

# [STRIPPED 75 bytes]
# Approval Service
# [STRIPPED 75 bytes]
APPROVAL_TRANSITIONS = {
    "REQUESTED": {"APPROVED", "REJECTED", "EXPIRED"},
    "APPROVED": {"CONSUMED", "EXECUTED", "EXPIRED"},
    "REJECTED": set(),
    "EXPIRED": set(),
    "CONSUMED": set(),
    "EXECUTED": set(),
}

_TRANSITION_AUTH_STATE = {
    "APPROVED": "AUTHORIZED", "CONSUMED": "AUTHORIZED",
    "EXECUTED": "AUTHORIZED", "REJECTED": "AUTHORIZED",
    "EXPIRED": "EXPIRED",
}

class ApprovalService(object):
    def __init__(self, conn, blackbox):
        self.conn = conn
        self.bb = blackbox

    def _binding(self, action, target, version, scope):
        # Execution-scope control: WHAT is authorized.
        return sha256_hex(canonical({
            "action": action, "target": target,
            "version": version, "scope": scope}))

    def _integrity_fields(self, approval_id, approval_type, requester_id,
                          requesting_layer, requested_action, objective,
                          summary, target, scope, version, binding,
                          requested_at, expires_at, authority_required,
                          single_use, rollback_reference, created_at):
        # Record-identity control: the approval record ITSELF is intact.
        # Mutable lifecycle `status` is intentionally EXCLUDED; status
        # changes are governed by the state machine + Black Box events.
        return {
            "approval_id": approval_id, "approval_type": approval_type,
            "requester_id": requester_id, "requesting_layer": requesting_layer,
            "requested_action": requested_action, "objective": objective,
            "summary": summary, "target": target, "scope": scope,
            "version": version, "action_binding_hash": binding,
            "requested_at": requested_at, "expires_at": expires_at,
            "authority_required": authority_required,
            "single_use": single_use,
            "rollback_reference": rollback_reference,
            "created_at": created_at,
        }

    def request(self, approval_type, requester_id, requesting_layer,
                requested_action, target, version, scope="",
                objective="", summary="", authority_required="approval_all",
                ttl_hours=24, single_use=True, rollback_reference=""):
        now = utcnow()
        requested_at = ts(now)
        expires_at = ts(now + datetime.timedelta(hours=ttl_hours))
        approval_id = new_id("APR")
        binding = self._binding(requested_action, target, version, scope)
        single_use_int = 1 if single_use else 0
        imm = self._integrity_fields(
            approval_id, approval_type, requester_id, requesting_layer,
            requested_action, objective, summary, target, scope, version,
            binding, requested_at, expires_at, authority_required,
            single_use_int, rollback_reference, requested_at)
        ih = sha256_hex(canonical(imm))
        self.conn.execute(
            """INSERT INTO approvals(approval_id,approval_type,requester_id,
               requesting_layer,requested_action,objective,summary,target,scope,
               version,action_binding_hash,status,requested_at,expires_at,
               authority_required,single_use,integrity_hash,created_at,
               rollback_reference)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (approval_id, approval_type, requester_id, requesting_layer,
             requested_action, objective, summary, target, scope, version,
             binding, "REQUESTED", requested_at, expires_at,
             authority_required, single_use_int, ih, requested_at,
             rollback_reference))
        self.conn.commit()
        self.bb.write("APPROVAL_REQUESTED", requesting_layer, requester_id,
                      "REQUESTED", "NORMAL", "APPROVAL", approval_id,
                      "request", "OK",
                      metadata={"approval_type": approval_type})
        return approval_id

    def request_from_chat(self, chat_text, requester_id="founder"):
        # Chat may REQUEST. Chat can NEVER authorize. No code path from
        # this function to any APPROVED state exists.
        return self.request(
            "CHAT_REQUEST", requester_id, "FOUNDER", "chat_requested_action",
            "chat", "n/a",
            summary="Requested via chat text (%.80s). Requires authenticated "
                    "authorization; chat text is never authority." % chat_text)

    def _row(self, approval_id):
        r = self.conn.execute(
            "SELECT * FROM approvals WHERE approval_id=?",
            (approval_id,)).fetchone()
        if not r:
            raise StateError("unknown approval")
        return _rowdict(self.conn, "approvals", r)

    def verify_approval_integrity(self, approval_id):
        # Independent verification of the approval RECORD (distinct from
        # the action-binding hash, which guards execution scope).
        a = self._row(approval_id)
        imm = self._integrity_fields(
            a["approval_id"], a["approval_type"], a["requester_id"],
            a["requesting_layer"], a["requested_action"], a["objective"],
            a["summary"], a["target"], a["scope"], a["version"],
            a["action_binding_hash"], a["requested_at"], a["expires_at"],
            a["authority_required"], a["single_use"],
            a["rollback_reference"], a["created_at"])
        if sha256_hex(canonical(imm))!= a["integrity_hash"]:
            raise IntegrityError(
                "ALTERED_APPROVAL_RECORD %s" % approval_id)
        return True

    def transition(self, approval_id, to_status, actor_type="SYSTEM",
                   actor_id="approval_service", reason=""):
        a = self._row(approval_id)
        if to_status not in APPROVAL_TRANSITIONS[a["status"]]:
            raise StateError("illegal transition %s -> %s"
                             % (a["status"], to_status))
        self.conn.execute(
            """UPDATE approvals SET status=?, decided_at=?, decided_by=?,
               decision_reason=? WHERE approval_id=?""",
            (to_status, ts(), actor_id, reason, approval_id))
        self.conn.commit()
        self.bb.write("APPROVAL_" + to_status, actor_type, actor_id,
                      _TRANSITION_AUTH_STATE[to_status], "NORMAL",
                      "APPROVAL", approval_id, to_status.lower(), "OK",
                      metadata={"from": a["status"], "reason": reason})
        return True

    def sweep_expirations(self):
        now = ts()
        rows = self.conn.execute(
            """SELECT approval_id FROM approvals
               WHERE status IN ('REQUESTED','APPROVED') AND expires_at<=?""",
            (now,)).fetchall()
        for (aid,) in rows:
            self.transition(aid, "EXPIRED", reason="ttl elapsed")
        return len(rows)

    def authorize(self, approval_id, ctx):
        if not isinstance(ctx, AuthorityContext) or not ctx.valid():
            raise AuthorityError(
                "UNAUTHORIZED: no valid authenticated authority context")
        a = self._row(approval_id)
        if ts() >= a["expires_at"]:
            self.transition(approval_id, "EXPIRED",
                            reason="expired before authorization")
            raise AuthorityError("EXPIRED approval cannot be authorized")
        if not ctx.can(a["authority_required"]):
            raise AuthorityError(
                "principal '%s' lacks required authority '%s'"
                % (ctx.principal_id, a["authority_required"]))
        return self.transition(approval_id, "APPROVED", "HUMAN",
                               ctx.principal_id,
                               "authenticated authorization via " + ctx.method)

    def reject(self, approval_id, ctx, reason=""):
        if not isinstance(ctx, AuthorityContext) or not ctx.valid():
            raise AuthorityError("UNAUTHORIZED")
        return self.transition(approval_id, "REJECTED", "HUMAN",
                               ctx.principal_id, reason)

    def verify_usable(self, approval_id, requested_action, target, version):
        # Fail-closed pre-use check. BOTH controls are enforced:
        # (1) record integrity (the approval itself is untampered), then
        # (2) binding (the requested operation matches what was approved).
        self.sweep_expirations()
        self.verify_approval_integrity(approval_id)
        a = self._row(approval_id)
        if a["status"] == "EXPIRED":
            raise AuthorityError("EXPIRED approval is dead; fail closed")
        if a["status"] in ("CONSUMED", "EXECUTED") and a["single_use"]:
            raise AuthorityError(
                "REPLAY blocked: single-use approval already consumed")
        if a["status"]!= "APPROVED":
            raise AuthorityError("approval not APPROVED (state=%s)"
                                 % a["status"])
        if self._binding(requested_action, target, version,
                         a["scope"])!= a["action_binding_hash"]:
            raise AuthorityError(
                "MATERIAL CHANGE: approval does not cover this "
                "action/target/version/scope")
        return True

    def consume(self, approval_id, requested_action, target, version):
        self.verify_usable(approval_id, requested_action, target, version)
        a = self._row(approval_id)
        return self.transition(
            approval_id, "CONSUMED" if a["single_use"] else "EXECUTED",
            reason="authorized use")

# [STRIPPED 75 bytes]
# Observability
# [STRIPPED 75 bytes]
def governance_status(conn, bb):
    n_dec = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    n_ver = conn.execute(
        "SELECT COUNT(*) FROM decision_versions").fetchone()[0]
    n_evt = conn.execute(
        "SELECT COUNT(*) FROM black_box_events").fetchone()[0]
    try:
        bb.verify_chain()
        chain = "VALID"
    except IntegrityError as e:
        chain = "BROKEN: %s" % e
    pending = conn.execute(
        "SELECT COUNT(*) FROM approvals WHERE status='REQUESTED'").fetchone()[0]
    expired = conn.execute(
        "SELECT COUNT(*) FROM approvals WHERE status='EXPIRED'").fetchone()[0]
    last = conn.execute(
        """SELECT event_id,event_type,occurred_at FROM black_box_events
           ORDER BY seq DESC LIMIT 1""").fetchone()
    return {
        "current_architecture_version": "Decisions 1-16 LOCKED",
        "decisions_loaded": n_dec,
        "decision_versions_stored": n_ver,
        "black_box_model":
            "APPEND-ONLY WITH TAMPER-EVIDENT INTEGRITY CONTROLS",
        "decision_history_model":
            "IMMUTABLE UNDER NORMAL APPLICATION OPERATIONS + "
            "TAMPER-EVIDENT INTEGRITY CONTROLS",
        "black_box_writer": "SINGLE WRITER (R0 invariant)",
        "black_box_events": n_evt,
        "hash_chain_status": chain,
        "pending_approvals": pending,
        "expired_approvals": expired,
        "system_state": "NORMAL",
        "implementation_version": IMPL_VERSION,
        "authority_fixture_warning": TEST_AUTHORITY_FIXTURE_NOT_PRODUCTION,
        "last_governance_event": last[0] if last else None,
        "last_governance_event_type": last[1] if last else None,
                            }

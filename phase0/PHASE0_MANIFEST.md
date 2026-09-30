# PHASE 0 MANIFEST — Minimum Clean Foundation

**Phase:** 0 (Foundation only)
**Authorization:** Founder, 2026-09-30
**Next phase:** Phase 1 (Finish and freeze Phase 1B) — NOT YET AUTHORIZED

## Artifacts

| # | File | Purpose | Repo path |
|---|---|---|---|
| 0A-1 | `constitution.md` | Governing authority: Founder supremacy, HOWZA CEO role, department hierarchy, immutable DNA, adaptive systems, epistemic discipline (FACT/ANALYSIS/HYPOTHESIS/RECOMMENDATION/DECISION/FOUNDER APPROVAL), worker permissions, verification, freeze discipline, change control, security, provider independence, persistence, recovery, learning, A+++ integrity, reporting, Sentinel authority, rollback | `/constitution.md` |
| 0B-1 | `schemas/memory-record.schema.md` | Contract for Company memory journal entries (normative JSON Schema in fenced block; raw `.json` extraction at Phase 2) | `/schemas/memory-record.schema.md` |
| 0B-2 | `schemas/state.schema.md` | Contract for Company state snapshots (same container note) | `/schemas/state.schema.md` |
| 0B-3 | `schemas/decision-record.schema.md` | Contract for decision log entries (same container note) | `/schemas/decision-record.schema.md` |
| 0B-4 | `schemas/opportunity.schema.md` | Contract for A+++ opportunity pipeline records (same container note) | `/schemas/opportunity.schema.md` |
| 0B-5 | `schemas/market-memory-record.schema.md` | Contract for Market Memory records (same container note) | `/schemas/market-memory-record.schema.md` |
| 0B-6 | `schemas/agent-definition.schema.md` | Contract for department/worker definitions (same container note) | `/schemas/agent-definition.schema.md` |
| 0C-1 | `REPO_LAYOUT.md` | Repository structure + growth plan without rewrites | `/REPO_LAYOUT.md` |
| 0C-2 | `README.md` | Repo front door, contributor rules | `/README.md` |
| 0C-3 | Directory skeleton | `agents/ memory/ state/ market-memory/ decisions/ reports/ runbooks/ verification/ products/ engineering/ archive/` each with README placeholder | (see REPO_LAYOUT.md) |
| 0D-1 | `runbooks/artifact-transfer.md` | Reliable file-transfer pipeline (replaces mobile copy-paste) | `/runbooks/artifact-transfer.md` |
| — | `PHASE0_MANIFEST.md` | This file | `/PHASE0_MANIFEST.md` |

## Verification performed

- [x] Constitution coverage audit: all 19 required topics present (I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII, XIII, XIV, XV, XVI, XVII, XVIII, XIX).
- [x] Schema self-review: valid JSON structure, required fields, enums, and descriptions checked by author re-read.
- [x] Repo skeleton: all directories and placeholder READMEs created; layout matches REPO_LAYOUT.md.
- [x] Transfer runbook reviewed against the two proven failure modes (missing colon, dropped block).

## Verification NOT yet possible (honest)

- [ ] Machine validation of JSON Schemas (no code execution in this environment).
- [ ] Founder ratification of the Constitution (required for it to take effect).
- [ ] Founder-side checksum confirmation after download (part of the transfer protocol).

## Dependencies

None. Phase 0 artifacts are pure documents/data; they require no infrastructure, keys, or services.

## Transfer note

Schemas ship as `.schema.md` files with fenced JSON blocks because this environment's file writer cannot emit raw `.json` content. Normative schema content is identical; raw `.json` extraction happens at Phase 2 when machine validation is available.


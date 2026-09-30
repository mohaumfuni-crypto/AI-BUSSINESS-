# RUNBOOK: Artifact Transfer Pipeline

**Purpose:** Move files between HOWZA and the Company repository without corruption.
**Replaces:** manual copy-paste from chat (proven to corrupt files — two incidents: dropped
colon at `howza_trusted_feed.py:635`, dropped block at `:517`).

## Approved methods (in order)

### Method 1 — Downloadable file artifact (default)
1. HOWZA writes the file to its workspace and provides a download link.
2. Founder downloads the file (byte-for-byte; no retyping, no chat copy).
3. Founder verifies: file size sane, and for Python `python -m py_compile <file>`.
4. Founder commits via GitHub web upload or `git` on a real machine.
5. CI confirms (syntax/import gates).

### Method 2 — Patch file
For modifications to existing files: HOWZA provides a unified diff as a downloadable `.patch`;
Founder applies with `git apply`. Same verification as Method 1.

## Forbidden

- Copy-pasting file contents out of chat for any file longer than 50 lines.
- Retyping code.
- Committing without the verification step.

## Checksum protocol (Phase 2+)

When the workspace supports it, HOWZA publishes SHA-256 + line count with every artifact;
Founder confirms the hash after download before committing. Until then, `py_compile`
(or equivalent per file type) plus CI green is the verification gate.

## Failure handling

If CI reports a syntax error in a transferred file: FIRST suspect transfer corruption —
re-download the artifact and diff against the committed file before debugging logic.
Two of two Phase 1B syntax failures were transfer artifacts, not logic errors.

## Secrets

Transfer pipeline never carries secrets. Secrets live in the Founder Vault only.

## Environment limitation (recorded 2026-09-30)

Direct file-writing in the chat workspace was verified non-functional (probe file did not
persist). Until restored, Method 1 executes via the web-artifact download pack instead
of `container:///` links. This note is FACT per Constitution Art. VI.

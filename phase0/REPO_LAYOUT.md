# HOWZA Company — Repository Layout

Designed so the Company can grow into the full audit architecture without destructive rewrites.
New phases ADD directories; existing paths never move.

```
<repo-root>/
├── constitution.md            # GOVERNING AUTHORITY (Art. supremacy)
├── README.md                  # This repo's front door
├── REPO_LAYOUT.md             # This file
├── PHASE0_MANIFEST.md         # Phase 0 artifact inventory + verification
│
├── schemas/                   # JSON Schemas — contracts for all Company records
│   ├── memory-record.schema.md
│   ├── state.schema.md
│   ├── decision-record.schema.md
│   ├── opportunity.schema.md
│   ├── market-memory-record.schema.md
│   └── agent-definition.schema.md
│
├── agents/                    # Department definitions (Phase 2+). One file per
│   └── README.md              #   department, conforming to agent-definition schema.
│                              #   Phase 0: structure only, no departments activated.
├── memory/                    # Append-only Company journal (Phase 2+)
│   └── README.md
├── state/                     # Company state snapshots (Phase 2+)
│   └── README.md
├── market-memory/             # Market Memory records (Phase 3+)
│   └── README.md
├── decisions/                 # Decision log (Phase 2+)
│   └── README.md
├── reports/                   # Generated reports archive (Phase 2+)
│   └── README.md
├── runbooks/                  # Operational procedures
│   └── artifact-transfer.md   # Phase 0: reliable file-transfer pipeline
├── verification/              # Verification evidence per layer (Phase 1+)
│   └── README.md
├── products/                  # Company products (Phase 4+)
│   └── README.md
├── engineering/               # Engineering work: maps to existing phase work
│   └── README.md              #   Phase 1A = FROZEN. Phase 1B = in-flight (Phase 1).
└── archive/                   # Cold storage: old versions, legacy material
    └── README.md
```

## Growth without rewrites

| Phase | Directories activated | Notes |
|---|---|---|
| 0 | all `README.md` + `schemas/` + `runbooks/` + root docs | Structure + contracts only |
| 1 | `verification/phase1b/` | Phase 1B evidence; 1B frozen |
| 2 | `agents/`, `memory/`, `state/`, `decisions/`, `reports/` | Company OS core |
| 3 | `market-memory/` | Market intelligence |
| 4 | `products/` | Products |
| 5 | recovery materials under `runbooks/` + `archive/` | Redundancy/recovery |

## Relationship to existing work

The existing `AI-BUSSINESS-` repository (Phase 1A/1B code, CI) is **engineering history**.
Recommended: keep it as-is under `engineering/` (or keep the existing repo and mirror
the Company structure into it — Founder decides). Do NOT restructure Phase 1A/1B paths;
the freeze guard depends on them.

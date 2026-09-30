# Schema: Company State Snapshot

Normative JSON Schema (draft-07). Extract the `json` block below as `state.schema.json`
when machine validation is available (Phase 2+).

```json
{
  "$id": "https://howza.company/schemas/state.schema.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Company State Snapshot",
  "description": "Point-in-time Company state. The orchestrator is the only writer.",
  "type": "object",
  "required": ["version", "updated_at"],
  "properties": {
    "version": { "type": "string" },
    "updated_at": { "type": "string", "format": "date-time" },
    "watchlist": { "type": "array", "items": { "type": "object" }, "description": "Monitored instruments and conditions" },
    "positions": { "type": "array", "items": { "type": "object" } },
    "pending_approvals": { "type": "array", "items": { "type": "object" }, "description": "Items awaiting Founder approval" },
    "alerts": { "type": "array", "items": { "type": "object" } },
    "config": { "type": "object", "description": "Targets, thresholds, provider router config (no secrets)" },
    "counters": { "type": "object", "description": "Opportunity pipeline counts, report sequence numbers" }
  }
}
```


# Schema: Market Memory Record

Normative JSON Schema (draft-07). Extract the `json` block below as `market-memory-record.schema.json`
when machine validation is available (Phase 2+).

```json
{
  "$id": "https://howza.company/schemas/market-memory-record.schema.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Market Memory Record",
  "description": "Long-term market knowledge: patterns, scenarios, setups, regimes, outcomes.",
  "type": "object",
  "required": ["id", "timestamp", "instrument", "timeframe", "kind", "description"],
  "properties": {
    "id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "instrument": { "type": "string" },
    "timeframe": { "type": "string" },
    "kind": { "type": "string", "enum": ["pattern", "scenario", "setup", "outcome", "regime"] },
    "technical": { "type": "object" },
    "fundamental": { "type": "object" },
    "sentiment": { "type": "object" },
    "macro": { "type": "object" },
    "description": { "type": "string" },
    "invalidation": { "type": "string" },
    "outcome": { "type": "object" },
    "lesson_refs": { "type": "array", "items": { "type": "string" } }
  }
}
```

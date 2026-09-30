# Schema: Decision Record

Normative JSON Schema (draft-07). Extract the `json` block below as `decision-record.schema.json`
when machine validation is available (Phase 2+).

```json
{
  "$id": "https://howza.company/schemas/decision-record.schema.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Decision Record",
  "description": "A DECISION-mode entry: a commitment to act, with owner, rationale, and approval basis.",
  "type": "object",
  "required": ["id", "timestamp", "owner", "decision", "rationale", "approval"],
  "properties": {
    "id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "owner": { "type": "string", "description": "Founder or HOWZA" },
    "context": { "type": "string" },
    "options_considered": { "type": "array", "items": { "type": "string" } },
    "decision": { "type": "string" },
    "rationale": { "type": "string" },
    "approval": { "type": "string", "enum": ["founder", "founder-delegated", "howza-operational"] },
    "status": { "type": "string", "enum": ["open", "executed", "superseded", "cancelled"] },
    "outcome": { "type": "string" },
    "links": { "type": "array", "items": { "type": "string" } }
  }
}
```

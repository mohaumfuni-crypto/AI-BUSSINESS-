# Schema: Company Memory Record

Normative JSON Schema (draft-07). Extract the `json` block below as `memory-record.schema.json`
when machine validation is available (Phase 2+).

```json
{
  "$id": "https://howza.company/schemas/memory-record.schema.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Company Memory Record",
  "description": "One entry in the append-only Company journal. Never edited after writing; corrections are new records.",
  "type": "object",
  "required": ["id", "timestamp", "type", "title", "body"],
  "properties": {
    "id": { "type": "string", "description": "Unique id, e.g. mem-20260930-001" },
    "timestamp": { "type": "string", "format": "date-time" },
    "type": { "type": "string", "enum": ["observation", "decision", "event", "lesson", "report", "directive"] },
    "department": { "type": "string", "description": "Owning department, if any" },
    "title": { "type": "string" },
    "body": { "type": "string" },
    "facts": { "type": "array", "items": { "type": "string" }, "description": "FACT-mode statements only" },
    "links": { "type": "array", "items": { "type": "string" }, "description": "Ids of related records" },
    "tags": { "type": "array", "items": { "type": "string" } }
  }
}
```

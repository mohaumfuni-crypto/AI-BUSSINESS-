# Schema: A+++ Opportunity Record

Normative JSON Schema (draft-07). Extract the `json` block below as `opportunity.schema.json`
when machine validation is available (Phase 2+).

```json
{
  "$id": "https://howza.company/schemas/opportunity.schema.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "A+++ Opportunity Record",
  "description": "One opportunity moving through the tracked pipeline. Standards are never lowered to meet targets.",
  "type": "object",
  "required": ["id", "detected_at", "instrument", "horizon", "stage"],
  "properties": {
    "id": { "type": "string" },
    "detected_at": { "type": "string", "format": "date-time" },
    "instrument": { "type": "string" },
    "horizon": { "type": "string", "enum": ["scalp", "day", "swing"] },
    "stage": { "type": "string", "enum": ["detected", "qualified", "verified", "presented", "executed", "rejected", "invalidated", "missed"] },
    "evidence": { "type": "object", "description": "Technical/fundamental/sentiment/macro/historical evidence" },
    "qualification": { "type": "object" },
    "verification": { "type": "object" },
    "outcome": { "type": "object", "description": "Result vs prediction; empty until resolved" },
    "target_period": { "type": "string", "description": "Which discovery target period this counts toward, if any" }
  }
}
```

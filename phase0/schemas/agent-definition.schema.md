# Schema: Agent / Department Definition

Normative JSON Schema (draft-07). Extract the `json` block below as `agent-definition.schema.json`
when machine validation is available (Phase 2+).

```json
{
  "$id": "https://howza.company/schemas/agent-definition.schema.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Agent / Department Definition",
  "description": "A department exists only when its definition file is ratified and active.",
  "type": "object",
  "required": ["name", "version", "purpose", "status"],
  "properties": {
    "name": { "type": "string" },
    "version": { "type": "string" },
    "department": { "type": "string" },
    "purpose": { "type": "string" },
    "inputs": { "type": "array", "items": { "type": "string" } },
    "outputs": { "type": "array", "items": { "type": "string" } },
    "tools_allowed": { "type": "array", "items": { "type": "string" } },
    "escalation_triggers": { "type": "array", "items": { "type": "string" } },
    "forbidden_actions": { "type": "array", "items": { "type": "string" } },
    "status": { "type": "string", "enum": ["draft", "active", "retired"] }
  }
}
```

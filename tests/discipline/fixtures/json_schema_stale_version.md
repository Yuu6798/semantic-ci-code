# Stale JSON Schema doc fixture

This fixture mirrors docs/json_schema.md but keeps the verdict envelope pinned
to an old version, simulating a doc that was not updated after a code bump.

| Field | Description |
|---|---|
| `schema_version` | CLI JSON schema version. Currently `"5"`. |
| `schema_version` | Compile-repair envelope version. Currently `"1"`. |
| `schema_version` | Validate-plan envelope version. Currently `"2"`. |
| `schema_version` | Always `"advisory-1"`. |

```json
{
  "schema_version": "catalog-1"
}
```

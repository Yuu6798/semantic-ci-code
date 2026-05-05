# Semantic CI JSON Output Schema

Semantic CI CLI output is JSON by default in non-TTY contexts and when
`--output` is used. The current schema version is `"3"`.

The CLI has two envelopes:

- verdict envelope: `observe`, `compare`, `check`, `pre-commit`
- compile envelope: `compile`

Both are deterministic: field order is fixed by insertion order and JSON is
rendered with two-space indentation.

## Verdict Envelope

```jsonc
{
  "schema_version": "3",
  "subcommand": "check",
  "mode": "full",
  "verdict": "pass",
  "intent": "add user profile endpoint",
  "primary_kind": "feature",
  "allowed_secondary_kinds": [],
  "summary": {
    "fix_required": 0,
    "suggested": 0,
    "info": 0,
    "unresolved": 0,
    "satisfied": 2,
    "skipped": 0
  },
  "results": [],
  "repair_plan": {"result": "pass", "instructions": []},
  "code_state": null,
  "files_touched": 1,
  "loc_delta": {"added": 4, "removed": 0},
  "cache": {
    "hit": 0,
    "miss": 2,
    "invalid": 0,
    "write_failed": 0,
    "disabled": false
  },
  "engine": {
    "extractor_pyver": "3.11",
    "package_version": "0.1.0"
  }
}
```

| Field | Meaning |
|---|---|
| `schema_version` | CLI JSON schema version. Currently `"3"`. |
| `subcommand` | One of `observe`, `compare`, `check`, `pre-commit`. |
| `mode` | `smoke`, `full`, or `null` when the subcommand has no execution mode. |
| `verdict` | `pass`, `repair`, `fail`, or `null` for `observe`. |
| `intent` | Target intent, or `null` for `observe`. |
| `primary_kind` | Target primary change kind, or `null` for `observe`. |
| `allowed_secondary_kinds` | Target secondary change kinds. Empty for `observe`. |
| `summary` | Counts by repair category plus satisfied and skipped constraints. `null` for `observe`. |
| `results` | Serialized evaluator `ConstraintResult` entries in evaluation order. |
| `repair_plan` | Serialized repair plan, or `null` for `observe`. |
| `code_state` | Full `CodeState` dump for `observe`; otherwise `null`. |
| `files_touched` | Git diff file count. Zero for `observe` and `compare`. |
| `loc_delta` | Git diff line count. Zero for `observe` and `compare`. |
| `cache` | Cache stats for this invocation: `hit`, `miss`, `invalid`, `write_failed`, and `disabled`. |
| `engine` | Python minor version and package version. |

## Compile Envelope

`semantic-ci compile` uses a separate minimal envelope because it does not
compute a verdict.

```jsonc
{
  "schema_version": "3",
  "subcommand": "compile",
  "compiled_target": {
    "intent": "verify refactor target",
    "primary_kind": "refactor",
    "allowed_secondary_kinds": [],
    "scope": [],
    "api_surface_policy": {
      "allow_changes": [
        {"fqn": "git_helpers.run_semantic_ci", "fqn_prefix": null},
        {"fqn": null, "fqn_prefix": "helpers."}
      ]
    },
    "effects_policy": {
      "allow_new": [
        {"fqn": "subprocess.run", "effect_class": "process"}
      ]
    },
    "constraints": [
      {
        "id": "template:refactor:api_surface_unchanged",
        "source": "template",
        "kind": "delta",
        "target": "api_surface_public",
        "operator": "equals_baseline",
        "expected": null,
        "severity": "hard",
        "unknown_policy": "fail",
        "tolerance": null,
        "evidence_required": false,
        "scope": null
      }
    ]
  },
  "cache": {
    "hit": 0,
    "miss": 0,
    "invalid": 0,
    "write_failed": 0,
    "disabled": true
  },
  "engine": {
    "extractor_pyver": "3.11",
    "package_version": "0.1.0"
  }
}
```

`compiled_target.constraints` preserves compiler order: template constraints
first, then user constraints in YAML order.

`compiled_target.api_surface_policy.allow_changes` and
`compiled_target.effects_policy.allow_new` are deterministic allow lists used by
built-in template constraints only. User constraints still observe the original
semantic state and delta.

## Compatibility Policy

Within a given envelope, removing fields, renaming fields, or changing field
meaning requires a schema version bump. Adding a new top-level field to an
existing envelope also requires a bump. Separate envelopes, such as `compile`,
may use the same version when they are explicitly keyed by `subcommand`.

## Version History

| Version | Envelope | Change |
|---|---|---|
| `1` | verdict | Initial Brief 4 JSON envelope. |
| `2` | verdict | Added top-level `mode` for execution mode reporting. |
| `2` | verdict | Added `summary.skipped` for constraints skipped by partial extraction modes. |
| `2` | verdict | Clarified that `results[].status == "skipped"` can mean a smoke-mode partial CodeState skipped that constraint's target dimension. |
| `3` | verdict, compile | Added top-level `cache` stats and aligned both envelopes on schema version `"3"`. |

## v2 to v3 Diff

- Added top-level `cache` to verdict and compile envelopes.
- Shape: `{hit: int, miss: int, invalid: int, write_failed: int, disabled: bool}`.
- `check` and `pre-commit` report real cache activity. `observe`, `compare`, and
  `compile` emit `disabled: true` with zero counters because they do not use the
  CodeState cache.
- Migration: consumers reading v2 can treat a missing `cache` field as
  `{hit: 0, miss: 0, invalid: 0, write_failed: 0, disabled: true}`.

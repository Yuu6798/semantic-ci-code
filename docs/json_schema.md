# Semantic CI JSON Output Schema

Semantic CI CLI output is JSON by default in non-TTY contexts and when
`--output` is used. The current schema version is `"4"`.

The CLI has two envelopes:

- verdict envelope: `observe`, `compare`, `check`, `pre-commit`
- compile envelope: `compile`

Both are deterministic: field order is fixed by insertion order and JSON is
rendered with two-space indentation.

`--format sarif` and `--format gh-actions` are separate CI integration outputs,
not variants of the verdict envelope below. SARIF emits a SARIF 2.1.0 document,
while `gh-actions` emits GitHub workflow command lines. They do not change the
verdict or compile JSON envelopes and therefore do not require a schema version
bump beyond the current CLI schema version.

## Verdict Envelope

```jsonc
{
  "schema_version": "4",
  "subcommand": "check",
  "mode": "full",
  "verdict": "pass",
  "intent": "add user profile endpoint",
  "primary_kind": "feature",
  "allowed_secondary_kinds": [],
  "target_authorship": {
    "authors": [{"identity": "alice@example.com", "signature": null}],
    "declared_at": "2026-05-05T12:00:00Z",
    "generation_metadata": {"tool": "codex"}
  },
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
| `schema_version` | CLI JSON schema version. Currently `"4"`. |
| `subcommand` | One of `observe`, `compare`, `check`, `pre-commit`. |
| `mode` | `smoke`, `full`, or `null` when the subcommand has no execution mode. |
| `verdict` | `pass`, `repair`, `fail`, or `null` for `observe`. |
| `intent` | Target intent, or `null` for `observe`. |
| `primary_kind` | Target primary change kind, or `null` for `observe`. |
| `allowed_secondary_kinds` | Target secondary change kinds. Empty for `observe`. |
| `target_authorship` | Target authorship metadata, or `null` when omitted or for `observe`. Semantic CI reports this metadata but does not validate signatures in P1. |
| `summary` | Counts by repair category plus satisfied and skipped constraints. `null` for `observe`. |
| `results` | Serialized evaluator `ConstraintResult` entries in evaluation order. |
| `repair_plan` | Serialized repair plan, or `null` for `observe`. `verdict == "pass"` does not imply `repair_plan.instructions == []`: violations of `severity: info` constraints surface as `category: "info"` instructions while the verdict stays `pass` (Advisor channel; see `code_semantic_ci_design.md §23.3`). |
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
  "schema_version": "4",
  "subcommand": "compile",
  "compiled_target": {
    "intent": "verify refactor target",
    "primary_kind": "refactor",
    "allowed_secondary_kinds": [],
    "scope": [],
    "authorship": {
      "authors": [{"identity": "alice@example.com", "signature": null}],
      "declared_at": "2026-05-05T12:00:00Z",
      "generation_metadata": {"tool": "codex"}
    },
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

`compiled_target.authorship` mirrors optional target authorship metadata. It is
`null` when the target file omits `authorship`.

`compiled_target.api_surface_policy.allow_changes` and
`compiled_target.effects_policy.allow_new` are deterministic allow lists used by
built-in template constraints only. User constraints still observe the original
semantic state and delta.

## Compile-Repair Envelope

`semantic-ci compile-repair --format json` uses an independent Brief 5 envelope.
Its `schema_version` is not tied to the verdict or compile envelope version.

```jsonc
{
  "schema_version": "1",
  "subcommand": "compile-repair",
  "adapter_name": "codex",
  "rendered": "[INTENT]\n...\n",
  "metadata": {
    "schema_version": "1",
    "engine_package_version": "0.1.0",
    "adapter_name": "codex",
    "adapter_version": "1",
    "intent": "",
    "primary_kind": "",
    "constraint_count": 1,
    "render_timestamp": null,
    "input_kind": "verdict_envelope"
  },
  "engine": {
    "extractor_pyver": "3.11",
    "package_version": "0.1.0"
  }
}
```

| Field | Meaning |
|---|---|
| `schema_version` | Compile-repair envelope version. Currently `"1"`. |
| `subcommand` | Always `compile-repair`. |
| `adapter_name` | Adapter used for rendering: `claude-code`, `cursor`, or `codex`. |
| `rendered` | Adapter-rendered text exactly as emitted in `--format text`. |
| `metadata` | Repair compiler metadata. `input_kind` is `verdict_envelope` or `raw_repair_plan`. |
| `engine` | Python minor version and package version. |

## Validate-Plan Envelope

`semantic-ci validate-plan --format json` uses an independent Brief 5 envelope.
Its `schema_version` is not tied to the verdict, compile, or compile-repair
envelope version.

```jsonc
{
  "schema_version": "1",
  "subcommand": "validate-plan",
  "adapter_name": "claude-code",
  "rendered": "# Plan Validation - Pre-Generation Guidance\n...\n",
  "metadata": {
    "schema_version": "1",
    "engine_package_version": "0.1.0",
    "adapter_name": "claude-code",
    "adapter_version": "1",
    "intent": "add profile endpoint",
    "primary_kind": "feature",
    "constraint_count": 2,
    "render_timestamp": null,
    "input_kind": "target_svp"
  },
  "risk_summary": {
    "would_violate": [],
    "forbidden_zones": [],
    "required_additions": [],
    "template_implications": []
  },
  "engine": {
    "extractor_pyver": "3.11",
    "package_version": "0.1.0"
  }
}
```

| Field | Meaning |
|---|---|
| `schema_version` | Validate-plan envelope version. Currently `"1"`. |
| `subcommand` | Always `validate-plan`. |
| `adapter_name` | Adapter used for rendering: `claude-code`, `cursor`, or `codex`. |
| `rendered` | Adapter-rendered text exactly as emitted in `--format text`. |
| `metadata` | Repair compiler pre-generation metadata. |
| `risk_summary` | Deterministic projections: `would_violate`, `forbidden_zones`, `required_additions`, and `template_implications`. |
| `engine` | Python minor version and package version. |

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
| `4` | verdict, compile | Added `target_authorship` to verdict envelopes and `compiled_target.authorship` to compile envelopes. |
| `1` | compile-repair | Initial Brief 5 repair compiler rendering envelope. |
| `1` | validate-plan | Initial Brief 5 pre-generation validation envelope with `risk_summary`. |

## v2 to v3 Diff

- Added top-level `cache` to verdict and compile envelopes.
- Shape: `{hit: int, miss: int, invalid: int, write_failed: int, disabled: bool}`.
- `check` and `pre-commit` report real cache activity. `observe`, `compare`, and
  `compile` emit `disabled: true` with zero counters because they do not use the
  CodeState cache.
- Migration: consumers reading v2 can treat a missing `cache` field as
  `{hit: 0, miss: 0, invalid: 0, write_failed: 0, disabled: true}`.

## v3 to v4 Diff

- Added `target_authorship` to verdict envelopes. Shape:
  `{authors: [{identity: str, signature: str|null}], declared_at: str|null,
  generation_metadata: object|null}` or `null`.
- Added `compiled_target.authorship` to compile envelopes with the same shape.
- Semantic CI only unmarshals and reports authorship metadata in v4. Signature
  verification, author-count policy, and AI generation detection are deferred to
  opt-in constraints in a later brief.
- Migration: consumers reading v3 can treat missing authorship fields as `null`.

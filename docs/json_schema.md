# Semantic CI JSON Output Schema

Semantic CI CLI output is JSON by default in non-TTY contexts and when
`--output` is used. The current schema version is `"5"`.

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
  "schema_version": "5",
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
| `schema_version` | CLI JSON schema version. Currently `"5"`. |
| `subcommand` | One of `observe`, `compare`, `check`, `pre-commit`. |
| `mode` | `smoke`, `full`, or `null` when the subcommand has no execution mode. |
| `verdict` | `pass`, `repair`, `fail`, or `null` for `observe`. |
| `intent` | Target intent, or `null` for `observe`. |
| `primary_kind` | Target primary change kind, or `null` for `observe`. |
| `allowed_secondary_kinds` | Target secondary change kinds. Empty for `observe`. |
| `target_authorship` | Target authorship metadata, or `null` when omitted or for `observe`. Semantic CI reports this metadata but does not validate signatures in P1. |
| `summary` | Counts by repair category plus satisfied and skipped constraints. `null` for `observe`. |
| `results` | Serialized evaluator `ConstraintResult` entries in evaluation order. Each entry includes an optional `unknown_cause` field populated only when `status == "unknown"` (values: `authoring`, `extraction`, `open_runtime`, `evaluator_internal`); `null` otherwise. See `docs/brief_resultstatus_planning.md` §3 D1. |
| `repair_plan` | Serialized repair plan, or `null` for `observe`. `verdict == "pass"` does not imply `repair_plan.instructions == []`: violations of `severity: info` constraints surface as `category: "info"` instructions while the verdict stays `pass` (Advisor channel; see `code_semantic_ci_design.md §23.3`). |
| `code_state` | Full `CodeState` dump for `observe`; otherwise `null`. |
| `files_touched` | Git diff file count. Zero for `observe` and `compare`. |
| `loc_delta` | Git diff line count. Zero for `observe` and `compare`. |
| `cache` | Cache stats for this invocation: `hit`, `miss`, `invalid`, `write_failed`, and `disabled`. |
| `engine` | Python minor version and package version. |

Extractor exclude config changes cache identity but not the JSON envelope shape.
`check` and `pre-commit` include the effective exclude key in their internal
CodeState cache key; schema version `"5"` is unchanged by this operational
cache-key extension. The first run after upgrading from a version without this
cache-key axis will rebuild CodeState cache entries once, even when no exclude
patterns are configured.

## Compile Envelope

`semantic-ci compile` uses a separate minimal envelope because it does not
compute a verdict.

```jsonc
{
  "schema_version": "5",
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
  "schema_version": "2",
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
    "authoring_errors": [],
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
| `schema_version` | Validate-plan envelope version. Currently `"2"`. |
| `subcommand` | Always `validate-plan`. |
| `adapter_name` | Adapter used for rendering: `claude-code`, `cursor`, or `codex`. |
| `rendered` | Adapter-rendered text exactly as emitted in `--format text`. |
| `metadata` | Repair compiler pre-generation metadata. |
| `risk_summary` | Deterministic projections in declared rendering order: `authoring_errors`, `would_violate`, `forbidden_zones`, `required_additions`, and `template_implications`. The author-facing `authoring_errors` slot lists residual spec-level errors (typically empty after Brief D1-2 / D1-3 caught them at compile); generator-facing slots stay scoped to "this implementation will likely violate / cannot touch / must add". Adapters render a two-step instruction so generators fix `target.yaml` first when `authoring_errors` is non-empty. |
| `engine` | Python minor version and package version. |

## Target-Doctor Advisory Envelope (Brief 8 / CSCI-43, planned)

`semantic-ci target-doctor --format json` will use an independent Brief 8
envelope. `schema_version` is not tied to the verdict, compile, compile-repair,
or validate-plan envelopes. The full field shape is fixed in
`docs/brief_8_planning.md §6.3` and pinned by
`src/semantic_ci_code/schemas/doctor_advisory.schema.json` when CSCI-43 lands.

```jsonc
{
  "schema_version": "advisory-1",
  "subcommand": "target-doctor",
  "advisories": [
    {"code": "ADVISORY-D1", "severity": "info", "message": "...", "evidence": {}}
  ]
}
```

Advisory presence does not change the exit code — see `docs/exit_codes.md`.

## Target-Catalog Reference Envelope (Brief 8 / CSCI-44, planned)

`semantic-ci target-catalog --format json` will use an independent Brief 8
envelope listing every registered target / operator / template / match
schema. The full shape is fixed in `docs/brief_8_planning.md §6.4` and pinned
by `src/semantic_ci_code/schemas/target_catalog.schema.json` when CSCI-44
lands.

```jsonc
{
  "schema_version": "catalog-1",
  "subcommand": "target-catalog",
  "primary_kinds": ["feature", "bugfix", "refactor", "test_update"],
  "targets": {},
  "templates": {},
  "operators": {}
}
```

The catalog content is required to stay byte-identical to the runtime
registries (INV-5 catalog ↔ implementation parity, see
`docs/brief_8_planning.md §5.2`).

## Compatibility Policy

Within a given envelope, removing fields, renaming fields, or changing field
meaning requires a schema version bump. Adding a new top-level field to an
existing envelope also requires a bump. Separate envelopes, such as `compile`,
may use the same version when they are explicitly keyed by `subcommand`.

### Nested optional diagnostic fields

Adding a new optional field nested under an existing array element or sub-object
(for example, `results[].unknown_cause`, or future diagnostic fields under
`risk_summary` items) does NOT require a schema version bump as long as the
field is genuinely optional and existing readers can ignore it. The bump
requirement still applies to:

- adding, removing, or changing the meaning of an existing field;
- adding a new top-level field on the envelope;
- adding, removing, or changing the meaning of an enum value already in use.

This exception exists because the verdict / compile envelopes accumulate
diagnostic surfaces as the engine evolves (Brief D1-4 added `results[].unknown_cause`
without bumping `schema_version` from `"5"`). If a downstream tool starts
*depending on* such a field being present, that tool effectively pins a strict
schema parse; the brief that flips the dependency should revisit whether to
bump the envelope version.

## Version History

| Version | Envelope | Change |
|---|---|---|
| `1` | verdict | Initial Brief 4 JSON envelope. |
| `2` | verdict | Added top-level `mode` for execution mode reporting. |
| `2` | verdict | Added `summary.skipped` for constraints skipped by partial extraction modes. |
| `2` | verdict | Clarified that `results[].status == "skipped"` can mean a smoke-mode partial CodeState skipped that constraint's target dimension. |
| `3` | verdict, compile | Added top-level `cache` stats and aligned both envelopes on schema version `"3"`. |
| `4` | verdict, compile | Added `target_authorship` to verdict envelopes and `compiled_target.authorship` to compile envelopes. |
| `5` | verdict, compile | Added Match Schema partial-record semantics for set operators, compile-time validation for partial dict expected records, flat projection aliases, and `evidence.matched` for `excludes_all` violations. |
| `5` | verdict | Brief D1-4: added optional `results[].unknown_cause` and `repair_plan.instructions[].unknown_cause` (values: `authoring` / `extraction` / `open_runtime` / `evaluator_internal`). Nested optional diagnostic field; no bump per the compatibility exception above. Authoring-cause UNKNOWN routes to `verdict: "fail"` regardless of `unknown_policy`. |
| `1` | compile-repair | Initial Brief 5 repair compiler rendering envelope. |
| `1` | validate-plan | Initial Brief 5 pre-generation validation envelope with `risk_summary`. |
| `2` | validate-plan | Brief D3: added `risk_summary.authoring_errors` as a sibling list (positioned first). Adapter rendering surfaces a two-step "fix authoring first, then implement" instruction. |
| `advisory-1` | target-doctor | Brief 8 / CSCI-43 (planned): initial advisory envelope. Independent schema; not tied to verdict / compile / compile-repair / validate-plan versions. |
| `catalog-1` | target-catalog | Brief 8 / CSCI-44 (planned): initial catalog envelope. Independent schema; mirrors runtime registries via INV-5 parity. |

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

## v4 to v5 Diff

- Set operators on registered dict-collection targets now use partial-record
  match semantics. An expected record matches an observed record when every key
  in the expected record is equal in the observed record; observed extra keys are
  ignored.
- `excludes_all`, `includes_all`, `includes_any`, `subset_of`, and `superset_of`
  verdicts can change for partial dict expected records. This is a gate
  strengthening fix for silent bypasses.
- `excludes_all` violations can include `evidence.matched`, a list of
  `{expected_item, observed_record}` pairs showing which observed record matched
  a denied expected partial record.
- The compiler rejects unregistered partial dict expected records and forbidden
  fields such as `signature`, `confidence`, `evidence`, and `symbols`.
- Added flat projection aliases:
  `api_surface_delta.added.fqns`, `effect_changes.added.fqns`, and
  `imports_delta.added.modules`.

## validate-plan v1 to v2 Diff

- Added `risk_summary.authoring_errors` as a sibling list to
  `risk_summary.would_violate`. Positioned first in the rendering order so
  adapters can surface the two-step instruction "fix every item under
  `authoring_errors` in `target.yaml` first; only then implement against
  `would_violate` / `forbidden_zones` / `required_additions`".
- `authoring_errors` carries user constraints whose self-evaluation tagged
  the result `unknown_cause: authoring` (planning §3 D3 / §3 D2). After
  Brief D1-2 and D1-3 the list is typically empty: most authoring errors
  are rejected at compile-time as `CompileError` before `validate-plan`
  reaches the evaluator. The slot stays so the contract is visible to
  adapter implementations and remains populated when residual cases reach
  evaluate-time via direct CompiledConstraint construction.
- Adapter rendering update (claude-code / cursor / codex):
  - claude-code / cursor: a one-line "Implementation order" note appears
    above the risk sections, plus a new `## Authoring Errors` section
    rendered first.
  - codex: a `[IMPLEMENTATION ORDER]` block lists the two-step order;
    `[AUTHORING ERRORS]` is the first risk section.
- Migration: consumers reading v1 should accept the new
  `risk_summary.authoring_errors` key (treat missing as `[]`). No other
  field shape changed.

# Semantic CI JSON Output Schema

Semantic CI CLI output is JSON by default in non-TTY contexts and when
`--output` is used. The current schema version is `"6"`.

The CLI has two envelopes:

- verdict envelope: `observe`, `compare`, `check`
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
  "schema_version": "6",
  "subcommand": "check",
  "mode": "full",
  "verdict": "pass",
  "security": {
    "verdict": "pass",
    "as_of": "2026-09-01",
    "global_count_violated": false,
    "sensors": [
      {
        "sensor_id": "semgrep",
        "status": "pass",
        "added": [],
        "removed": [],
        "suppressed": [],
        "drift_reason": null,
        "provenance_changed": false,
        "unchanged_count": 0
      }
    ]
  },
  "suite_verdict": "pass",
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
    "baseline": {
      "source": "commit",
      "rev": "0123456789abcdef0123456789abcdef01234567"
    },
    "candidate": {
      "source": "working-tree",
      "rev": null
    },
    "extractor_pyver": "3.11",
    "package_version": "0.1.0"
  }
}
```

| Field | Meaning |
|---|---|
| `schema_version` | CLI JSON schema version. Currently `"6"`. |
| `subcommand` | One of `observe`, `compare`, `check`. |
| `mode` | `smoke`, `full`, or `null` when the subcommand has no execution mode. |
| `verdict` | `pass`, `repair`, `fail`, or `null` for `observe`. |
| `security` | Optional `check` security verdict object present only when `--sensor-baseline` / `--sensor-candidate` are supplied. It includes aggregate `verdict`, `as_of`, `global_count_violated`, and `sensors[]` detail. Each sensor entry has `sensor_id`, `status`, `added`, `removed`, `suppressed`, `drift_reason`, `provenance_changed`, and `unchanged_count`; finding arrays contain `SecurityFinding.model_dump(mode="json")` objects with `category` (`sast` or `sca`) and their canonical identity fields. |
| `suite_verdict` | Optional final suite verdict present only when `security` is present. Values: `pass`, `repair`, `fail`, or `unknown`; computed from code and security using `unknown > fail > repair > pass`. |
| `advisory` | Optional `check` LLM scout advisory object present only when `--advisory-sensor` is supplied. It never affects `verdict`, `suite_verdict`, or exit code. Shape: `{adapter_id, sensor, surfaced, pre_existing, muted, counts, mutes_path}`. `sensor` records `{sensor_id, sensor_version, model_id, prompt_hash, non_reproducible, status, error_message}`. `surfaced` and `pre_existing` contain `LLMSecurityFinding.model_dump(mode="json")` objects; `muted` contains `{canonical_id, reason, owner, expires}` audit records; `counts` records `scouted`, `surfaced`, `pre_existing`, and `muted`. |
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
| `engine` | Python minor version, package version, optional source provenance, and optional extraction diagnostics. `check` includes `engine.baseline` and `engine.candidate` sub-objects with `{source, rev}`; `source` is `commit`, `working-tree`, or `staged-index`, and `rev` is a resolved commit SHA for commit-backed sources or `null` for volatile sources. When `check --extractor-timeout` causes one or more dimensions to fall back to schema defaults, `engine.timed_out_dimensions` is a sorted list of dimension names. Other verdict-producing subcommands may omit these sub-objects. |

`CodeState.api_surface[]` records include an additive `decorators: string[]`
field. It is empty by default and contains syntactic decorator names such as
`login_required`, `app.route`, or `auth.requires`; `api_surface[].signature`
does not include decorator lines. `CodeStateDelta` includes an additive
`decorators_delta` `SymbolDelta`; its `added` and `removed` records are
`{"fqn": "...", "decorator": "...", "decorator_leaf": "..."}`. `decorator`
preserves the normalized dotted source name, while `decorator_leaf` supports
qualified-insensitive policy matching. These fields do not require a verdict
envelope schema bump because they are nested CodeState / CodeStateDelta
expansions with empty defaults and are absent from top-level envelope routing.
`CodeStateDelta` also includes additive `renames: [{old_path, new_path}]`
records populated only by the `check` git overlay when `git diff -M` reports a
rename. The pure engine leaves `renames` empty, matching `files_touched` and
`loc_delta` as CLI-derived metadata.

Extractor exclude config changes cache identity but not the JSON envelope shape.
`check` includes the effective exclude key in its internal CodeState cache key;
schema version `"5"` was unchanged by this operational cache-key extension. The
first run after upgrading from a version without this cache-key axis will
rebuild CodeState cache entries once, even when no exclude patterns are
configured.

## Compile Envelope

`semantic-ci compile` uses a separate minimal envelope because it does not
compute a verdict.

```jsonc
{
  "schema_version": "6",
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

The compile envelope shares the CLI `SCHEMA_VERSION` constant with verdict
envelopes for compatibility, but v6 does not add source provenance fields to
`compile`; its envelope shape is unchanged from v5 except for the shared version
number.

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

## Target-Doctor Advisory Envelope

`semantic-ci target-doctor --format json` uses an independent Brief 8
envelope. `schema_version` is not tied to the verdict, compile,
compile-repair, or validate-plan envelopes. The shape is pinned by
`src/semantic_ci_code/schemas/doctor_advisory.schema.json` and
`docs/brief_8_planning.md §6.3`.

```jsonc
{
  "schema_version": "advisory-1",
  "subcommand": "target-doctor",
  "advisories": [
    {
      "code": "ADVISORY-P1",
      "severity": "info",
      "message": "primary_kind=feature has no positive addition constraint ...",
      "evidence": {"primary_kind": "feature"}
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `schema_version` | Always `"advisory-1"`. |
| `subcommand` | Always `"target-doctor"`. |
| `advisories[].code` | One of `ADVISORY-D1`, `ADVISORY-D3`, `ADVISORY-D4`, `ADVISORY-I1`, `ADVISORY-P1`, `ADVISORY-P2`, `ADVISORY-S1`. |
| `advisories[].severity` | Always `"info"` — the Advisor surface never participates in the verdict (`docs/code_semantic_ci_design.md §23.3.1`). |
| `advisories[].message` | Human-readable explanation of the hazard. |
| `advisories[].evidence` | Per-advisory diagnostic fields (e.g. `constraint_id`, `target`, `package_root`, `files_touched_count`). |

Advisories are emitted in canonical order (D1 → D3 → D4 → I1 → P1 → P2 → S1)
with `constraint_id` as the within-code tiebreak so output is byte-identical
across runs. Advisory presence does not change the exit code — see
`docs/exit_codes.md`.

## Target-Catalog Reference Envelope (Brief 8 / CSCI-44)

`semantic-ci target-catalog --format json` uses an independent Brief 8
envelope listing every registered target / operator / template / match
schema. The full shape is pinned by
`src/semantic_ci_code/schemas/target_catalog.schema.json`.

```jsonc
{
  "schema_version": "catalog-1",
  "subcommand": "target-catalog",
  "primary_kinds": ["bugfix", "feature", "generic", "refactor", "test_update"],
  "targets": {},
  "templates": {},
  "operators": {}
}
```

The catalog content is required to stay byte-identical to the runtime
registries (INV-5 catalog ↔ implementation parity, see
`docs/brief_8_planning.md §5.2`). `--kind` narrows only the `templates`
section, and `--target-path` narrows only the `targets` section.
`targets.*.match_schema` mirrors the runtime Match Schema registry. Most
record targets use `required_key` for both bare-string desugaring and record
validation. Some targets, such as effects, also include `required_any_keys`
when a record may specify one of several identity keys (`fqn` or
`effect_class`).

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
| `6` | verdict, compile | Source-selection Phase 2/3a: replaced `check --allow-dirty` with explicit source selection, added `check` source provenance under `engine.baseline` / `engine.candidate`, then extended the source enum with `staged-index`. The compile envelope keeps the shared schema version but its shape is unchanged in v6. |
| `1` | compile-repair | Initial Brief 5 repair compiler rendering envelope. |
| `1` | validate-plan | Initial Brief 5 pre-generation validation envelope with `risk_summary`. |
| `2` | validate-plan | Brief D3: added `risk_summary.authoring_errors` as a sibling list (positioned first). Adapter rendering surfaces a two-step "fix authoring first, then implement" instruction. |
| `advisory-1` | target-doctor | Brief 8 / CSCI-43: initial advisory envelope. Independent schema; not tied to verdict / compile / compile-repair / validate-plan versions. |
| `catalog-1` | target-catalog | Brief 8 / CSCI-44: initial catalog envelope. Independent schema; mirrors runtime registries via INV-5 parity. |

## v2 to v3 Diff

- Added top-level `cache` to verdict and compile envelopes.
- Shape: `{hit: int, miss: int, invalid: int, write_failed: int, disabled: bool}`.
- `check` reports real cache activity. `observe`, `compare`, and `compile` emit
  `disabled: true` with zero counters because they do not use the CodeState
  cache.
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

## v5 to v6 Diff

- `semantic-ci check` now records source provenance in the JSON envelope:
  `engine.baseline` and `engine.candidate` each have `{source, rev}`.
- `source` is `"commit"`, `"working-tree"`, or `"staged-index"`. `rev` is the
  resolved commit SHA when `source == "commit"` and `null` for volatile sources.
- `check --candidate-source {commit,working-tree}` replaced the removed
  `check --allow-dirty` flag in Phase 2. Phase 3a adds
  `--baseline-source {commit,working-tree,staged-index}` and extends
  `--candidate-source` with `staged-index` without bumping the schema version:
  adding an enum value to this optional provenance field is covered by the
  compatibility policy above.
- `check --extractor-timeout <seconds>` can add
  `engine.timed_out_dimensions: [<dimension>, ...]` without bumping the schema
  version because it is an optional diagnostic field. Constraints that target a
  timed-out dimension report `status: "unknown"` and
  `unknown_cause: "extraction"`.
- `check --sensor-baseline <json> --sensor-candidate <json>` can add optional
  top-level `security` and `suite_verdict` fields without bumping the schema
  version. Consumers reading v6 can ignore these additive fields and keep using
  the code-only `verdict`; sensor-enabled callers should route exit behavior
  from `suite_verdict`.
- CSCI-48b extends that optional `security` object with per-sensor `added`,
  `removed`, `suppressed`, `drift_reason`, and `unchanged_count` detail. The
  schema version stays `"6"` because this is an additive expansion of an
  optional diagnostic object introduced in G-4a.
- CSCI-53 adds optional top-level `advisory` output for `check
  --advisory-sensor`. It records LLM scout findings, pre-existing findings,
  muted findings, and provenance for informed consent, but it is advisory-only:
  readers that ignore it keep the same code verdict and exit-code semantics.
  The schema version stays `"6"` following the same additive diagnostic
  compatibility rule used for `security` / `suite_verdict`.
- G-5 adds `CodeState.api_surface[].decorators` and
  `CodeStateDelta.decorators_delta` for syntactic public API decorator tracking.
  The verdict envelope schema version stays `"6"` because these are additive
  nested state/delta fields with empty defaults, not new top-level envelope
  fields.
- The CLI layer still materializes two directories for the engine; the engine
  does not receive source-category enums.

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

# Semantic CI CLI Usage

`semantic-ci` is the operational entrypoint for Semantic CI Code Edition. It is
deterministic, local-first, and currently supports Python code paths only.

```text
semantic-ci [--version] [--language python] [--no-color] [--quiet|--verbose]
            <subcommand> [subcommand-options]
```

Global flags:

| Flag | Meaning |
|---|---|
| `--version` | Print package version and exit 0. |
| `--language python` | Select language. Python is the only accepted value in P1. |
| `--no-color` | Disable ANSI color in human output. |
| `--quiet` | Suppress progress diagnostics. Warnings and errors still go to stderr. |
| `--verbose` | Print progress diagnostics and tracebacks for expected engine errors. |

Stdout is reserved for machine output or human reports. Stderr is reserved for
progress, warnings, and errors.

## Target Discovery

Subcommands that need a target use this order:

1. explicit `--target <path>`
2. `./target.yaml`
3. `./.semantic-ci/target.yaml`

If both implicit locations exist, the command exits with usage error 2 and asks
the user to pass `--target`.

## Excluding Files From Extraction

Extractor commands (`observe`, `compare`, `check`, and the baseline-reading
paths of `validate-plan`) read optional operational extraction config from the
nearest `pyproject.toml` found by walking upward from the package root:

```toml
[tool.semantic_ci_code.extract]
exclude = [
  "tests/fixtures/pipeline/syntax_error",
  "examples/broken/**",
  "**/*_pb2.py",
  "**/*_pb2_grpc.py",
]
```

Patterns are interpreted relative to the `pyproject.toml` parent directory,
not the current working directory and not the package root. `compare` and
`check` discover config independently for baseline and candidate trees, so
historical config changes are respected.

This is not `.gitignore` syntax. Patterns are stdlib-only `fnmatch` with
limited recursive support. For recursive subtree exclusion, prefer literal
directory patterns or trailing `/**`. For generated Python files, prefer
`**/*_pb2.py`-style basename patterns.
Patterns like `src/**/generated.py` are not recursive in this implementation;
use a basename shortcut such as `**/generated.py` or a literal directory rule
instead.

Matcher rules, in order:

| Pattern type | Example | Meaning |
|---|---|---|
| Literal directory or file | `tests/fixtures/syntax_error` | Excludes that exact path and all descendants when it is a directory. |
| Trailing `/**` | `examples/broken/**` | Equivalent to a literal directory subtree. |
| Basename glob shortcut | `**/*_pb2.py` | Matches the basename at any depth. |
| Full-path `fnmatch` fallback | `src/pkg/*.gen.py` | Matches the POSIX path relative to config root, segment by segment, without crossing `/`. |

Invalid patterns are engine errors (exit 3): empty strings, absolute paths,
parent traversal (`..`), Windows backslashes, non-string values, and unknown keys
under `[tool.semantic_ci_code.extract]` such as `exlude` or `excludes`.
Commands that do not extract code (`compile`, `compile-repair`, `init`) do not
load this config.

## Target Policies

`target.yaml` can carry narrow allow-list policies for template constraints.
These policies do not change extractor output and do not hide values from user
constraints; they only change the comparison view used by built-in templates.

```yaml
intent: refactor CLI test helper plumbing
change:
  primary_kind: refactor
api_surface:
  allow_changes:
    - fqn: git_helpers.run_semantic_ci
    - fqn_prefix: helpers.
effects:
  allow_new:
    - fqn: subprocess.run
      effect_class: process
```

`api_surface.allow_changes` accepts exact `fqn` and deterministic
`fqn_prefix` rules. It is intended for scoped exceptions such as test helper
movement where public-looking symbols are not production API. `effects.allow_new`
accepts exact effect FQNs and/or effect classes for feature and bugfix templates.

## Constraint Severity

Each constraint in `target.yaml` carries a `severity` field that decides how
violations route into the verdict. The default is `hard`.

| `severity` | verdict when violated | exit code impact | surface (§23.3) |
|---|---|---|---|
| `hard` (default) | `fail` | exit 1 | Validator |
| `soft` | `repair` | exit 0 (or exit 1 with `--strict-repair`) | Validator |
| `info` | `pass` (verdict unchanged) | no impact | Advisor channel |

`severity: info` violations are reported as `category: info` repair
instructions and surfaced in human / SARIF / GitHub Actions output, but they
do not change the verdict or exit code. Lowering a constraint from `hard` to
`soft` or `info` weakens the gate; the choice is the spec author's
responsibility. See `docs/code_semantic_ci_design.md §23.3` for the underlying
boundary (verdict is not intent correctness).

## Set Operator Match Semantics

For collection targets whose elements are records, Semantic CI supports partial
record matching. An expected record matches an observed record when every key in
the expected record is equal in the observed record; extra observed keys are
ignored. This prevents deny / allow gates from silently bypassing just because
extractors include additional fields such as signatures or evidence.

Formal semantics:

```text
includes_all(expected, observed):
  for every E in expected, some O in observed matches E

includes_any(expected, observed):
  some E in expected matches some O in observed

excludes_all(expected, observed):
  no E in expected matches any O in observed

superset_of(expected, observed):
  same as includes_all

subset_of(expected, observed):
  every O in observed matches at least one E in expected
```

Match Schema registry:

| Target | Required key | Optional keys | Forbidden keys |
|---|---|---|---|
| `api_surface`, `api_surface_public` | `fqn` | `kind`, `visibility` | `signature` |
| `api_surface_delta.added`, `.removed`, `.removed_public` | `fqn` | `kind`, `visibility` | `signature` |
| `api_surface_delta.changed` | `fqn` | `kind` | `signature`, `visibility`, `before`, `after` |
| `effects` | `fqn` or `effect_class` | `effect_class` | `confidence`, `evidence` |
| `effect_changes.added`, `.removed` | `fqn` or `effect_class` | `effect_class` | `confidence`, `evidence` |
| `decorators_delta.added`, `.removed` | `decorator` or `decorator_leaf` | `fqn` | - |
| `imports` | `module` | `from` | `symbols` |
| `imports_delta.added`, `.removed` | `module` | `from` | `symbols` |

Forbidden keys are compile-time errors because they couple policy to unstable
extractor formatting or list-valued exact equality. `module_graph`,
`complexity`, `control_flow`, and `test_surface` are not registered for partial
record matching in this slice.

`api_surface_delta.changed` exposes `visibility` only inside its `before` and
`after` payloads, so D5 does not allow top-level visibility matching there.

For registered targets with one required key, bare strings in `expected` are
desugared at compile time. For example:

```yaml
target: api_surface_delta.added
operator: includes_all
expected:
  - "src.api.users.fetch_user_profile"
```

is compiled as:

```yaml
expected:
  - fqn: src.api.users.fetch_user_profile
```

Effect targets also accept `effect_class`-only records, which is useful for
deny gates that should match any new effect of a class regardless of FQN.
Decorator delta targets accept `decorator` records for exact dotted decorator
matches and `decorator_leaf` records for qualified-insensitive matches. The
auth-guard recipe uses `decorator_leaf` so `@auth.login_required` is matched by
the configured `login_required` guard name.

Flat projections are convenience aliases only: `api_surface_delta.added.fqns`,
`effect_changes.added.fqns`, and `imports_delta.added.modules`. They compare
plain string sets and do not perform record matching. The safety mechanism for
partial dict authoring is the Match Schema validation above.

## Target Authorship

`target.yaml` may include an optional `authorship` section. Semantic CI parses
and reports this metadata but does not validate signatures, author counts, or
AI generation hints in P1.

```yaml
authorship:
  authors:
    - identity: alice@example.com
      signature: optional-signature
  declared_at: "2026-05-05T12:00:00Z"
  generation_metadata:
    tool: codex
```

## Output Format

`--format json|human|sarif|gh-actions` overrides all defaults where supported.
Without an explicit format:

- `observe` defaults to JSON.
- `compare`, `check`, and `compile` use human output on a TTY and JSON when
  piped, redirected, or written with `--output`.
- `--output <file>` defaults to JSON.

`sarif` and `gh-actions` are CI integration formats for verdict-producing
subcommands only: `compare` and `check`. `observe` and `compile` reject them
with usage error 2. `sarif` emits SARIF 2.1.0 JSON and can be used with
`--output`. `gh-actions` emits GitHub workflow commands (`::error`,
`::warning`, `::notice`) to stdout and rejects `--output` because workflow
commands must be written to the job log.

Color is enabled only for human output when stdout is a TTY. `--no-color` and
`NO_COLOR` disable color. `FORCE_COLOR` enables color for non-TTY output unless
`--no-color` or `NO_COLOR` is set.

## Execution Modes

`check` accepts `--mode {smoke,full}`. `full` is the default and preserves the
existing behavior. `smoke` is a faster partial run that extracts only
`api_surface`, `imports`, and `effects`; constraints that target unextracted
dimensions are reported as `skipped` and do not affect the verdict.

If `--mode` is omitted, `SEMANTIC_CI_MODE=smoke|full` can override the default.
An explicit `--mode` flag always wins over the environment. CodeState caching
is available for `check`; worktree reuse and extractor memoization remain
deferred.

## `semantic-ci observe`

```text
semantic-ci observe [--package-root <dir>] [--paths <file...>]
                    [--format {json,human}] [--output <file>]
```

Extracts a Python `CodeState` and writes it in the stable JSON envelope.
`observe` does not load `target.yaml`, compute a verdict, or emit a repair plan.
`--format human` is accepted for forward compatibility and falls back to JSON.

Examples:

```bash
semantic-ci observe --package-root src/semantic_ci_code
semantic-ci observe --package-root . --paths src/semantic_ci_code/cli
```

## `semantic-ci init`

```text
semantic-ci init [--path <file>] [--force] [--intent <text>]
                 [--recipe <id>] [--doctor] [--package-root <dir>]
```

Scaffolds a commented target file. The default output path is
`.semantic-ci/target.yaml`; parent directories are created as needed. Existing
files are not overwritten unless `--force` is provided. `--intent` writes a
single-line human-readable intent into the generated target. Without
`--intent`, the bare scaffold remains byte-for-byte unchanged.

**Surface**: Authoring (§23.3). `init` writes a target.yaml scaffold; it does
not validate, refine, or interpret intent. The scaffold's defaults do not
encode opinions about which constraints are correct for a given change.

Examples:

```bash
semantic-ci init
semantic-ci init --intent "preserve public API while renaming internals"
semantic-ci init --path target.yaml
semantic-ci init --path .semantic-ci/target.yaml --force
semantic-ci init --recipe feature:add-api --add-api pkg.api.create_user --intent "add user API"
semantic-ci init --recipe bugfix:regression-test --test-case tests/test_login.py::test_regression --doctor
semantic-ci init --recipe security:deny-dangerous-imports
semantic-ci init --recipe security:deny-dangerous-effects
semantic-ci init --recipe security:preserve-auth-guards
```

After successful generation, `init` prints next-step commands for compile and
target-doctor. Recipe output also suggests `validate-plan`. Recipe generation
prints a short note about the template constraints it implies; recipes that add
`test_surface_delta.*` constraints also remind the user to ensure
`--package-root` covers the test directory.

Recipe IDs:

| Recipe | Primary kind | User constraint |
|---|---|---|
| `feature:add-api` | `feature` | Requires declared public API additions. |
| `bugfix:regression-test` | `bugfix` | Requires or checks for regression test additions. |
| `refactor:preserve-api-with-allowlist` | `refactor` | Optionally allow-lists selected public API changes. |
| `test-update:add-test-case` | `test_update` | Requires or checks for test case additions. |
| `security:deny-dangerous-imports` | `generic` | Denies newly added imports such as `pickle`, `subprocess`, and `marshal`. |
| `security:deny-dangerous-effects` | `generic` | Denies newly added `process`, `dynamic_code`, and `unsafe_deserialize` effects. |
| `security:preserve-auth-guards` | `generic` | Denies removal of public API decorators whose leaf name is `login_required`, `requires_auth`, or `permission_required`. |

`--doctor` runs target-doctor inline after writing the file and prints the human
advisory output to stderr. `--package-root` is accepted only together with
`--doctor`; it uses the same repo-relative resolution and symlink-escape guards
as `semantic-ci target-doctor`.

## `semantic-ci compare`

```text
semantic-ci compare --baseline-dir <dir> --candidate-dir <dir>
                    [--target <yaml>]
                    [--package-root-baseline <dir>]
                    [--package-root-candidate <dir>]
                    [--format {json,human,sarif,gh-actions}] [--output <file>]
                    [--strict-repair]
```

Compares two local directory trees without git. `files_touched` and `loc_delta`
remain zero because there is no git diff context.

Examples:

```bash
semantic-ci compare --baseline-dir /tmp/base --candidate-dir /tmp/candidate
semantic-ci compare --baseline-dir base --candidate-dir candidate --strict-repair
semantic-ci compare --baseline-dir base --candidate-dir candidate --format sarif --output semantic-ci.sarif
semantic-ci compare --baseline-dir base --candidate-dir candidate --format gh-actions
```

## `semantic-ci check`

```text
semantic-ci check [--baseline-rev <ref>] [--candidate-rev <ref>]
                  [--target <yaml>] [--package-root <repo-relative-dir>]
                  [--format {json,human,sarif,gh-actions}] [--output <file>]
                  [--strict-repair] [--no-fetch]
                  [--baseline-source {commit,working-tree,staged-index}]
                  [--candidate-source {commit,working-tree,staged-index}]
                  [--mode {smoke,full}] [--no-cache] [--cache-dir <dir>]
                  [--cache-max-bytes <int>] [--extractor-timeout <seconds>]
                  [--sensor-baseline <sensor-state.json>]
                  [--sensor-candidate <sensor-state.json>]
                  [--as-of YYYY-MM-DD]
```

Compares git refs using temporary detached worktrees. Defaults are:

- baseline: `origin/main`, then `main`, then `master`
- candidate: `HEAD`

`--package-root` is repo-relative and is resolved inside each materialized tree.
`--baseline-source` and `--candidate-source` select where each snapshot comes
from:

- `commit` (default): evaluate a resolved commit ref. Baseline uses
  `--baseline-rev` or the `origin/main` -> `main` -> `master` fallback;
  candidate uses `--candidate-rev` or `HEAD`. When
  `--candidate-source staged-index` is used and `--baseline-rev` is omitted,
  baseline commit defaults to `HEAD` to match pre-commit-style semantics.
- `working-tree`: evaluate the current working tree. It cannot be combined with
  the same side's `--*-rev` flag. With `--verbose`,
  `--candidate-source working-tree` emits a note when the working tree is clean
  and therefore equivalent to `HEAD`.
- `staged-index`: evaluate the current staged index, exported with
  `git checkout-index`. It cannot be combined with the same side's `--*-rev`
  flag.

If baseline and candidate use the same volatile source (`working-tree` or
`staged-index`), `check` emits a warning and still runs; the verdict reports no
drift by construction because both sides materialize the same snapshot.

Common source combinations:

| Use case | `--baseline-source` | `--candidate-source` | Notes |
|---|---|---|---|
| PR review / CI gate | `commit` | `commit` | Default. Compares baseline ref to candidate ref. |
| Pre-commit-style simulation | `commit` | `staged-index` | Baseline defaults to `HEAD` unless `--baseline-rev` is given. |
| Working-tree trial | `commit` | `working-tree` | Compares a baseline ref to uncommitted local files. |
| Self-check working tree | `working-tree` | `working-tree` | Degenerate no-drift comparison; warning emitted. |
| Self-check staged index | `staged-index` | `staged-index` | Degenerate no-drift comparison; warning emitted. |

JSON output from `check` records source provenance under
`engine.baseline` and `engine.candidate`.

`check` can also combine the code verdict with prebuilt security sensor state:

```bash
semantic-ci check \
  --sensor-baseline baseline.sensor-state.json \
  --sensor-candidate candidate.sensor-state.json \
  --as-of 2026-09-01
```

Both `--sensor-baseline` and `--sensor-candidate` must be provided together.
Each file must be a `SensorState` JSON document produced by the Phase G sensor
state model. `check` does not run Semgrep, pip-audit, or any other live scanner
from these flags; it only ingests prebuilt JSON and evaluates the target's
optional `security:` policy. `--as-of` controls suppression expiry. When it is
omitted, the CLI boundary uses today's date. With sensor state enabled, JSON
output adds:

```json
{
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
  "suite_verdict": "pass"
}
```

The code-only `verdict` field remains the evaluator verdict. `suite_verdict`
combines code and security with `unknown > fail > repair > pass` and controls
the process exit code for sensor-enabled `check` runs. Sensor-enabled `check`
supports JSON, human, and SARIF output. JSON includes per-sensor added,
removed, suppressed, drift, and unchanged-count detail; human output prints the
same summary and added finding lines; SARIF appends security findings into the
same `runs[0]` as code constraint results with `security/<rule>` rule IDs. If a
security policy fails for count or deny-list reasons while the underlying
finding severity maps only to a SARIF note, SARIF also emits a
`security/policy-*` error result so consumers can see the failing gate.
`--format gh-actions` remains deferred to a later G-4 slice. Without sensor
flags, the payload and exit behavior are unchanged.

**Migrated in Phase 3b**: `semantic-ci pre-commit [...]` became
`semantic-ci check --candidate-source=staged-index [...]`. The evaluation
semantics are identical for the hook use case: the baseline is the `HEAD`
commit and the candidate is the staged index.

`check` caches ref-backed `CodeState` extraction under
`<repo>/.semantic-ci/cache/code_state/` by default. The cache key includes the
package subtree object id, package root, execution mode, extracted dimensions,
effective extract exclude key, Python minor version, package version, CodeState
schema version, and cache format version. Adding the effective extract exclude
axis causes a one-time cache miss after upgrading from versions that did not
include that axis, even when no exclude patterns are configured. If package
metadata is unavailable during source-tree execution, the cache key uses a
deterministic fingerprint of the `semantic_ci_code` Python sources instead of
the constant unknown version fallback. `--no-cache` or
`SEMANTIC_CI_NO_CACHE=1` disables both reads and writes. `--cache-dir <dir>`
changes the cache root; relative paths are resolved from the invoking working
directory. `--cache-max-bytes <int>` controls size-based eviction; the default
is 100 MiB, `0` disables eviction, and `SEMANTIC_CI_CACHE_MAX_BYTES` can set the
default when the flag is absent. Add `.semantic-ci/cache/` to your project
`.gitignore` if you use the default cache location.

JSON output includes `cache: {hit, miss, invalid, write_failed, disabled}` for
the current command invocation. `hit` and `miss` count individual baseline /
candidate lookups, `invalid` counts corrupt or version-mismatched entries that
were recomputed, and `write_failed` counts failed cache writes.

`--extractor-timeout <seconds>` applies a per-dimension wall-clock budget to
each Python extractor dimension (`api_surface`, `imports`, `module_graph`,
`effects`, `complexity`, `test_surface`). Omit it for the default fail-fast,
no-timeout behavior. If a dimension exceeds the budget, `check` falls that
dimension back to its schema default, disables CodeState cache reads/writes for
that invocation, records the dimension under `engine.timed_out_dimensions` in
JSON output, and constraints targeting that dimension evaluate as
`unknown_cause: extraction` so their `unknown_policy` still controls verdict
routing.

Examples:

```bash
semantic-ci check
semantic-ci check --baseline-rev origin/main --candidate-rev HEAD --target target.yaml
semantic-ci check --candidate-source working-tree --package-root src/semantic_ci_code
semantic-ci check --candidate-source staged-index --target target.yaml
semantic-ci check --baseline-source working-tree --candidate-source staged-index
semantic-ci check --mode smoke
semantic-ci check --extractor-timeout 2.5 --format json
semantic-ci check --sensor-baseline baseline.security.json --sensor-candidate candidate.security.json
semantic-ci check --cache-dir .semantic-ci/cache
semantic-ci check --cache-max-bytes 104857600
semantic-ci check --format sarif --output semantic-ci.sarif
semantic-ci check --format gh-actions
```

## `semantic-ci compile`

```text
semantic-ci compile [<yaml>] [--target <yaml>] [--format {json,human}] [--output <file>]
```

Compiles `target.yaml` and prints the normalized `CompiledTarget`. It does not
extract code, compute a delta, evaluate constraints, or emit a verdict.

Examples:

```bash
semantic-ci compile .semantic-ci/target.yaml
semantic-ci compile --target target.yaml --format json
semantic-ci compile --target target.yaml --format human --no-color
```

## `semantic-ci compile-repair`

```text
semantic-ci compile-repair --adapter {claude-code,cursor,codex}
                           [--input <json>] [--output <file>]
                           [--format {text,json}] [--no-color]
```

Renders a serialized `RepairPlan` for a coding adapter. Input defaults to stdin
and may be either a full verdict envelope containing `repair_plan` or a raw
`RepairPlan` object with `instructions`. This enables direct pipe usage without
field extraction:

```bash
semantic-ci check --format json | semantic-ci compile-repair --adapter claude-code
semantic-ci check --format json | semantic-ci compile-repair --adapter codex --format json
semantic-ci compile-repair --adapter cursor --input repair-plan.json --output semantic-ci.mdc
```

`--format text` writes only the rendered adapter text. `--format json` wraps the
rendered text in a compile-repair envelope with independent
`schema_version="1"`. A PASS verdict envelope whose `repair_plan` is `null`
exits with usage error 2 because there is nothing to render.

`compile-repair` renders only what the serialized `RepairPlan` carries. It does
not reconstruct `target.yaml`, so rendered intent and primary kind are empty,
and Cursor `globs:` fall back to `**/*.py`. A later CLI integration can pass a
`TargetSVP` alongside the repair plan when intent and scope-aware rendering are
needed.

## `semantic-ci validate-plan`

```text
semantic-ci validate-plan --target <yaml> --adapter {claude-code,cursor,codex}
                          [--baseline-rev <ref> | --baseline-dir <dir>]
                          [--package-root <rel>] [--no-fetch]
                          [--format {text,json}] [--output <file>] [--no-color]
```

Renders pre-generation guidance from a `target.yaml`. Unlike `compile-repair`,
this command has the target available, so adapter output includes intent,
primary kind, target constraints, authorship generation metadata, and Cursor
`globs:` derived from `change.scope.files`.

Baseline state may come from `--baseline-dir`, from `--baseline-rev`, or from
the default git ref resolution order `origin/main -> main -> master`. If no git
baseline can be resolved and no explicit baseline was provided, Semantic CI
falls back to an empty `CodeState` so plan validation can still render.
`--package-root` is relative to the baseline directory or git tree.

`validate-plan` computes a deterministic `risk_summary` with four lists:
`would_violate`, `forbidden_zones`, `required_additions`, and
`template_implications`. For `required_additions`, `includes_all` constraints
emit one required item per expected value, while `includes_any` constraints emit
one `expected_any_of` alternatives group so adapters do not imply that every
alternative must be added. `--format text` writes adapter text directly.
`--format json` wraps it in an independent validate-plan envelope with
`schema_version="1"`.

`would_violate` is computed by re-evaluating user constraints against the
baseline state as both baseline and candidate. State-kind constraints surface
naturally, for example an `includes_all` requirement whose item is absent from
baseline. Delta-kind constraints cannot violate under a self-comparison and are
not reported in `would_violate`; inspect `forbidden_zones` and
`required_additions` for their structural intent.

Examples:

```bash
semantic-ci validate-plan --target target.yaml --adapter claude-code
semantic-ci validate-plan --target target.yaml --adapter codex --format json
semantic-ci validate-plan --target target.yaml --adapter cursor --baseline-rev HEAD~1
```

## `semantic-ci ssp`

```text
semantic-ci ssp scan --sensor {semgrep,pip-audit}
                     --baseline-dir <dir> --candidate-dir <dir>
                     [--config <ruleset>] [--package-root <dir>]
                     [--format {json,human,sarif}] [--output <file>]

semantic-ci ssp from-json --baseline <sensor-output.json>
                          --candidate <sensor-output.json>
                          [--format {json,human,sarif}] [--output <file>]
```

Runs the Semantic Security Protocol (SSP) v0.1 pipeline. SSP is separate from
the core Semantic CI verdict engine: it consumes security sensor output,
computes deterministic security deltas, and emits an SSP envelope with
`schema_version="ssp-1"`.

`ssp scan` executes one live sensor on the baseline and candidate trees:

- `--sensor semgrep` requires `--config <ruleset>`. `--package-root` selects
  the subdirectory inside each tree scanned by Semgrep and defaults to `.`.
- `--sensor pip-audit` audits each project directory. If `requirements.txt`
  exists in a side, it is passed as the requirements input for that side.

`ssp from-json` is fixture / pre-captured mode. It reads two `SensorOutput`
JSON files, computes the same `SSPDelta` and `SSPVerdict`, and does not run
any external sensor process.

Formats:

- `--format json` (default): emits the SSP envelope and validates against
  `src/semantic_ci_code/schemas/ssp_envelope_v1.json`.
- `--format human`: emits a compact per-sensor summary with added / removed /
  unchanged counts and finding details.
- `--format sarif`: emits SARIF 2.1.0. SSP severity maps to SARIF level as:
  `critical` / `high` -> `error`, `medium` -> `warning`, and `low` / `info`
  -> `note`.

Exit codes follow the SSP verdict: `pass` exits 0, `fail` exits 1, usage
errors exit 2, sensor-error / `unknown` envelopes exit 3, and internal bugs
exit 4.

Examples:

```bash
semantic-ci ssp scan --sensor semgrep --config semgrep.yml \
  --baseline-dir baseline --candidate-dir candidate --package-root src
semantic-ci ssp scan --sensor pip-audit --baseline-dir baseline --candidate-dir candidate
semantic-ci ssp from-json --baseline baseline.sensor.json --candidate candidate.sensor.json
semantic-ci ssp from-json --baseline baseline.sensor.json --candidate candidate.sensor.json \
  --format sarif --output ssp.sarif
```

## Authoring subcommands (verdict 不参加)

Subcommands on the **Authoring** or **Advisor** surface
(`docs/code_semantic_ci_design.md §23.3.1`) do not compute a verdict and do
not change the JSON envelope produced by `check` / `compare` /
`compile-repair`. The surface design contract is in
[`docs/target_authoring_surface.md`](./target_authoring_surface.md);
canonical specs are in [`docs/brief_8_planning.md §6`](./brief_8_planning.md).

### `semantic-ci target-doctor`

```text
semantic-ci target-doctor [--target <yaml>] [--package-root <dir>]
                          [--baseline-rev <ref>] [--candidate-rev <ref>]
                          [--format {human,json}] [--output <file>]
```

Audits a `target.yaml` for seven authoring hazards and renders them as
advisories. Advisor surface — advisory presence does not change the
verdict and does not change the exit code (`docs/exit_codes.md`).

| Code | What it detects |
|---|---|
| `ADVISORY-D1` | `test_surface_delta.*` constraint exists, but no test files (`test_*.py` / `*_test.py` / `tests/`) are visible under `--package-root`. |
| `ADVISORY-D3` | A user constraint duplicates a template-expanded constraint (same kind/target/operator/expected). |
| `ADVISORY-D4` | The target is lock-only and the candidate diff (`--baseline-rev` ↔ `--candidate-rev`) touches no Python files; the verdict would be a vacuous PASS. Skipped silently when neither rev is given and git is unavailable. |
| `ADVISORY-I1` | `intent` is the empty string. Repair adapters and `validate-plan` produce better guidance when intent describes the change purpose; use `init --intent` or edit `target.yaml`. |
| `ADVISORY-P1` | `primary_kind: feature` has no positive addition constraint. |
| `ADVISORY-P2` | `primary_kind: bugfix` has no `test_surface_delta.new_cases` expectation. |
| `ADVISORY-S1` | A user constraint has `severity: info` paired with `unknown_policy in {fail, repair}`. After Brief D1-4 the warning scope narrows to extraction-cause / open_runtime UNKNOWN. |

`--format json` emits the `advisory-1` envelope
([`docs/json_schema.md`](./json_schema.md)). There is no `--strict-advice`
flag — CI that wants to gate on advisory presence should consume the JSON
output and apply a workflow-level policy.

Examples:

```bash
semantic-ci target-doctor --target .semantic-ci/target.yaml
semantic-ci target-doctor --target target.yaml --format json
semantic-ci target-doctor --target target.yaml --baseline-rev origin/main \
    --candidate-rev HEAD --format json
```

### `semantic-ci target-catalog`

```text
semantic-ci target-catalog [--format {json,human}]
                           [--kind {feature,bugfix,generic,refactor,test_update}]
                           [--target-path <path>]
                           [--output <file>]
```

Renders the authoring catalog used by assistants, IDE extensions, and
external tools to generate valid `target.yaml` files. This is an Authoring
meta surface: it does not read a target file, does not extract code, and does
not compute or change a verdict.

The JSON envelope is independent of verdict / compile schema versions:

```json
{
  "schema_version": "catalog-1",
  "subcommand": "target-catalog",
  "primary_kinds": ["bugfix", "feature", "generic", "refactor", "test_update"],
  "targets": {},
  "templates": {},
  "operators": {}
}
```

Catalog contents are derived from the runtime registries, not duplicated in the
formatter:

- `primary_kinds`: `ChangeKind` enum values.
- `targets`: `compiler.path_schema` valid paths, `compiler.type_schema`
  categories, and `framework.match_schema` partial-record match rules.
- `templates`: `compiler.templates.TEMPLATE_CONSTRAINTS` expanded constraints.
- `operators`: `framework.constraint_types.Operator` values plus compile-time
  compatibility checks from `compiler.operator_schema` / `compiler.type_schema`.

Filters narrow one section only. `--kind feature` narrows `templates` to the
feature templates while leaving `targets`, `operators`, and `primary_kinds`
unchanged. `--target-path api_surface_delta.added` narrows `targets` to that
single entry while leaving `templates` and `operators` unchanged. The two
filters can be combined. `--target-path` also accepts valid open-dimension
paths such as `python_specific.value`; these render as `kind: open` with
`category: unknown_open`.
`--kind generic` is accepted and renders an empty template entry because
`generic` injects no built-in constraints.

Examples:

```bash
semantic-ci target-catalog --format json
semantic-ci target-catalog --format human
semantic-ci target-catalog --kind feature --format json
semantic-ci target-catalog --target-path api_surface_delta.added --format human
semantic-ci target-catalog --format json --output target-catalog.json
```

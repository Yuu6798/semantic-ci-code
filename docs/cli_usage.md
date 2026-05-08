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

Extractor commands (`observe`, `compare`, `check`, `pre-commit`, and the
baseline-reading paths of `validate-plan`) read optional operational extraction
config from the nearest `pyproject.toml` found by walking upward from the
package root:

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
not the current working directory and not the package root. `compare`, `check`,
and `pre-commit` discover config independently for baseline and candidate
trees, so historical config changes are respected.

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
| `effects` | `fqn` | `effect_class` | `confidence`, `evidence` |
| `effect_changes.added`, `.removed` | `fqn` | `effect_class` | `confidence`, `evidence` |
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
- `compare`, `check`, `pre-commit`, and `compile` use human output on a TTY and
  JSON when piped, redirected, or written with `--output`.
- `--output <file>` defaults to JSON.

`sarif` and `gh-actions` are CI integration formats for verdict-producing
subcommands only: `compare`, `check`, and `pre-commit`. `observe` and `compile`
reject them with usage error 2. `sarif` emits SARIF 2.1.0 JSON and can be used
with `--output`. `gh-actions` emits GitHub workflow commands (`::error`,
`::warning`, `::notice`) to stdout and rejects `--output` because workflow
commands must be written to the job log.

Color is enabled only for human output when stdout is a TTY. `--no-color` and
`NO_COLOR` disable color. `FORCE_COLOR` enables color for non-TTY output unless
`--no-color` or `NO_COLOR` is set.

## Execution Modes

`check` and `pre-commit` accept `--mode {smoke,full}`. `full` is the default
and preserves the existing behavior. `smoke` is a faster partial run that
extracts only `api_surface`, `imports`, and `effects`; constraints that target
unextracted dimensions are reported as `skipped` and do not affect the verdict.

If `--mode` is omitted, `SEMANTIC_CI_MODE=smoke|full` can override the default.
An explicit `--mode` flag always wins over the environment. CodeState caching
is available for `check` and `pre-commit`; worktree reuse and extractor
memoization remain deferred.

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
semantic-ci init [--path <file>] [--force]
```

Scaffolds a commented target file. The default output path is
`.semantic-ci/target.yaml`; parent directories are created as needed. Existing
files are not overwritten unless `--force` is provided.

**Surface**: Authoring (§23.3). `init` writes a target.yaml scaffold; it does
not validate, refine, or interpret intent. The scaffold's defaults do not
encode opinions about which constraints are correct for a given change.

Examples:

```bash
semantic-ci init
semantic-ci init --path target.yaml
semantic-ci init --path .semantic-ci/target.yaml --force
```

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
                  [--strict-repair] [--no-fetch] [--allow-dirty]
                  [--mode {smoke,full}] [--no-cache] [--cache-dir <dir>]
                  [--cache-max-bytes <int>]
```

Compares git refs using temporary detached worktrees. Defaults are:

- baseline: `origin/main`, then `main`, then `master`
- candidate: `HEAD`

`--package-root` is repo-relative and is resolved inside each materialized tree.
Without `--allow-dirty`, a dirty working tree emits a warning and still checks
the `HEAD` commit. With `--allow-dirty`, the working tree is used as candidate.

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

Examples:

```bash
semantic-ci check
semantic-ci check --baseline-rev origin/main --candidate-rev HEAD --target target.yaml
semantic-ci check --allow-dirty --package-root src/semantic_ci_code
semantic-ci check --mode smoke
semantic-ci check --cache-dir .semantic-ci/cache
semantic-ci check --cache-max-bytes 104857600
semantic-ci check --format sarif --output semantic-ci.sarif
semantic-ci check --format gh-actions
```

## `semantic-ci pre-commit`

```text
semantic-ci pre-commit [--target <yaml>] [--package-root <repo-relative-dir>]
                       [--format {json,human,sarif,gh-actions}] [--output <file>]
                       [--strict-repair] [--mode {smoke,full}]
                       [--no-cache] [--cache-dir <dir>]
                       [--cache-max-bytes <int>]
```

Compares `HEAD` against the staged index. The staged index is exported with
`git checkout-index`, so unstaged working-tree changes are ignored. If there are
no staged files, the command returns an empty PASS payload with exit 0.

`pre-commit` uses the same CodeState cache as `check`. Baseline `HEAD` is keyed
by the package subtree object id; the staged candidate is keyed by
`git write-tree`, so identical staged content can hit cache across repeated
runs. `--no-cache`, `SEMANTIC_CI_NO_CACHE=1`, `--cache-dir`, and
`--cache-max-bytes` have the same meaning as they do for `check`.

Examples:

```bash
semantic-ci pre-commit --target target.yaml
semantic-ci pre-commit --strict-repair
semantic-ci pre-commit --mode smoke
semantic-ci pre-commit --cache-dir .semantic-ci/cache
semantic-ci pre-commit --format gh-actions
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
                          [--package-root <rel>] [--no-fetch] [--allow-dirty]
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

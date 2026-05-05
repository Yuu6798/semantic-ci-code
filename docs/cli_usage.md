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

## Output Format

`--format json|human` overrides all defaults. Without an explicit format:

- `observe` defaults to JSON.
- `compare`, `check`, `pre-commit`, and `compile` use human output on a TTY and
  JSON when piped, redirected, or written with `--output`.
- `--output <file>` defaults to JSON.

Color is enabled only for human output when stdout is a TTY. `--no-color` and
`NO_COLOR` disable color. `FORCE_COLOR` enables color for non-TTY output unless
`--no-color` or `NO_COLOR` is set.

## Execution Modes

`check` and `pre-commit` accept `--mode {smoke,full}`. `full` is the default
and preserves the existing behavior. `smoke` is a faster partial run that
extracts only `api_surface`, `imports`, and `effects`; constraints that target
unextracted dimensions are reported as `skipped` and do not affect the verdict.

If `--mode` is omitted, `SEMANTIC_CI_MODE=smoke|full` can override the default.
An explicit `--mode` flag always wins over the environment. Cache support
(worktree reuse and extractor memoization) is intentionally deferred to
CSCI-26 and later.

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

## `semantic-ci compare`

```text
semantic-ci compare --baseline-dir <dir> --candidate-dir <dir>
                    [--target <yaml>]
                    [--package-root-baseline <dir>]
                    [--package-root-candidate <dir>]
                    [--format {json,human}] [--output <file>]
                    [--strict-repair]
```

Compares two local directory trees without git. `files_touched` and `loc_delta`
remain zero because there is no git diff context.

Examples:

```bash
semantic-ci compare --baseline-dir /tmp/base --candidate-dir /tmp/candidate
semantic-ci compare --baseline-dir base --candidate-dir candidate --strict-repair
```

## `semantic-ci check`

```text
semantic-ci check [--baseline-rev <ref>] [--candidate-rev <ref>]
                  [--target <yaml>] [--package-root <repo-relative-dir>]
                  [--format {json,human}] [--output <file>]
                  [--strict-repair] [--no-fetch] [--allow-dirty]
                  [--mode {smoke,full}] [--no-cache] [--cache-dir <dir>]
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
Python minor version, package version, CodeState schema version, and cache format
version. If package metadata is unavailable during source-tree execution, the
cache key uses a deterministic fingerprint of the `semantic_ci_code` Python
sources instead of the constant unknown version fallback. `--no-cache` or
`SEMANTIC_CI_NO_CACHE=1` disables both reads and writes. `--cache-dir <dir>`
changes the cache root; relative paths are resolved from the invoking working
directory. Add `.semantic-ci/cache/` to your project `.gitignore` if you use the
default cache location.

Examples:

```bash
semantic-ci check
semantic-ci check --baseline-rev origin/main --candidate-rev HEAD --target target.yaml
semantic-ci check --allow-dirty --package-root src/semantic_ci_code
semantic-ci check --mode smoke
semantic-ci check --cache-dir .semantic-ci/cache
```

## `semantic-ci pre-commit`

```text
semantic-ci pre-commit [--target <yaml>] [--package-root <repo-relative-dir>]
                       [--format {json,human}] [--output <file>]
                       [--strict-repair] [--mode {smoke,full}]
```

Compares `HEAD` against the staged index. The staged index is exported with
`git checkout-index`, so unstaged working-tree changes are ignored. If there are
no staged files, the command returns an empty PASS payload with exit 0.

Examples:

```bash
semantic-ci pre-commit --target target.yaml
semantic-ci pre-commit --strict-repair
semantic-ci pre-commit --mode smoke
```

## `semantic-ci compile`

```text
semantic-ci compile [--target <yaml>] [--format {json,human}] [--output <file>]
```

Compiles `target.yaml` and prints the normalized `CompiledTarget`. It does not
extract code, compute a delta, evaluate constraints, or emit a verdict.

Examples:

```bash
semantic-ci compile --target target.yaml --format json
semantic-ci compile --target target.yaml --format human --no-color
```

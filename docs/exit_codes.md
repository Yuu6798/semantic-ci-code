# Semantic CI Exit Codes

Semantic CI uses stable exit codes so CI systems can route failures without
parsing output text.

| Code | Meaning | Typical trigger |
|---:|---|---|
| `0` | Pass | `Verdict.result == pass`. |
| `0` | Repair advisory | `Verdict.result == repair` without `--strict-repair`. |
| `0` | Initialized target | `semantic-ci init` created or overwrote the target file. |
| `1` | Semantic failure | `Verdict.result == fail`. |
| `1` | Strict repair | `Verdict.result == repair` with `--strict-repair`. |
| `2` | Usage or configuration error | Bad flags, missing paths, missing or ambiguous `target.yaml`, unsupported language. |
| `3` | Engine error | `CompileError`, `ExtractorError`, expected git command failure, git unavailable. |
| `4` | Internal bug | Unexpected Python exception. |

## Subcommand Notes

`observe` does not compute a verdict, so it returns only 0, 2, 3, or 4.

`init` does not compute a verdict. Successful scaffold creation exits 0.
Existing output files without `--force` and write/path errors exit 2. It has no
normal engine-error path; exit 3 remains reserved by the global policy.

`compare` and `check` map PASS/REPAIR/FAIL through the table above.
`--strict-repair` changes only REPAIR from exit 0 to exit 1. `check --mode
smoke` uses the same exit-code policy; skipped constraints are reported in
output but do not contribute to PASS, REPAIR, or FAIL.

Constraints with `severity: info` violate as advisory only: they appear in
output as `category: info` instructions but never change the verdict or the
exit code, even with `--strict-repair`. This is the Advisor channel defined
in `docs/code_semantic_ci_design.md §23.3`.

Cache hit, miss, invalidation, write failure, and best-effort eviction do not
change exit-code policy. Cache write and eviction failures are reported through
cache stats or verbose diagnostics, then the command continues with the computed
verdict.

Malformed `[tool.semantic_ci_code.extract]` config in `pyproject.toml` is an
engine error (exit 3) for commands that extract code. Non-extraction commands do
not load this config.

`compile` does not compute a verdict. Successful compilation exits 0. Target
discovery errors exit 2. Compile errors exit 3.

`compile-repair` does not compute a verdict. Successful rendering exits 0.
Missing input files, invalid JSON, unrecognized input shape, `repair_plan: null`
verdict envelopes, and unknown adapters exit 2.

`validate-plan` does not compute a verdict. Successful rendering exits 0.
Missing or invalid targets, invalid explicit baselines, missing adapters, and
write/path errors exit 2. If no implicit git baseline can be resolved, it
renders against an empty `CodeState` instead of failing.

`target-doctor` (Brief 8 / CSCI-43) is an Advisor surface command and does
not compute a verdict. It follows the repo-wide policy: advisory detection
— zero or more — never changes the exit code (always 0 on successful run
+ output). Usage / configuration errors (target file missing, missing
`--package-root` directory, unparseable flags) exit 2. Expected engine /
git errors (`CompileError` on `target.yaml`, git revision resolution
failure when `--baseline-rev` / `--candidate-rev` is given, git
unavailable when explicitly required) exit 3. Internal bugs exit 4. When
neither `--baseline-rev` nor `--candidate-rev` is given and git is
unavailable or no baseline can be resolved, ADVISORY-D4 is silently
skipped rather than failing. There is no `--strict-advice` flag; CI that
wants to gate on advisory presence should consume `--format json` and
apply a workflow-level policy. Silent success on bad input is forbidden —
the advisor surface only suppresses the verdict step, not the input
validation step.

`target-catalog` (Brief 8 / CSCI-44) is an Authoring meta surface command and
does not compute a verdict. Successful catalog rendering exits 0. Invalid
filters or flags (for example an unknown `--target-path`) exit 2 with a
did-you-mean hint when available. Expected output / filesystem failures exit 3.
Internal bugs exit 4.

`ssp` (Brief 7 / CSCI-40) computes a Semantic Security Protocol envelope, not
the core Semantic CI verdict envelope. `ssp scan` executes one security sensor
on baseline and candidate directories; `ssp from-json` consumes pre-captured
`SensorOutput` JSON files without sensor execution. SSP `aggregate_verdict:
pass` exits 0, `fail` exits 1, and `unknown` exits 3 because it represents a
sensor error / incomplete security signal. Bad flags, missing files, invalid
fixture JSON, or missing Semgrep `--config` exit 2. Internal bugs exit 4.

## Error Streams

Stdout is reserved for JSON or human report output. Expected diagnostic messages
go to stderr.

| Situation | Exit | Stderr |
|---|---:|---|
| Missing target | 2 | `target.yaml not found; tried ./target.yaml and ./.semantic-ci/target.yaml. Use --target.` |
| Ambiguous target | 2 | `ambiguous target.yaml location: both ./target.yaml and ./.semantic-ci/target.yaml exist; use --target.` |
| Compile error | 3 | One-line `CompileError` with filename and path/line where available. |
| Extract config error | 3 | `extract config error: <pyproject.toml>: <reason>` |
| Extractor error | 3 | `extractor failed: <name> at <path>: <reason>` |
| Git unavailable | 3 | `git is required for 'check'; install git or use 'compare'` or the subcommand-specific equivalent. |
| Dirty working tree in `check` with default `--candidate-source commit` | 0/1 | No warning; the resolved candidate commit is evaluated. |
| `check --candidate-source working-tree --candidate-rev <ref>` | 2 | `error: --candidate-source=working-tree is incompatible with --candidate-rev` |
| `check --candidate-source staged-index --candidate-rev <ref>` | 2 | `error: --candidate-source=staged-index is incompatible with --candidate-rev` |
| `check --baseline-source working-tree --baseline-rev <ref>` | 2 | `error: --baseline-source=working-tree is incompatible with --baseline-rev` |
| `check --baseline-source staged-index --baseline-rev <ref>` | 2 | `error: --baseline-source=staged-index is incompatible with --baseline-rev` |
| `check --baseline-source <volatile> --candidate-source <same volatile>` | 0/1 | Warning: verdict will report no drift by construction. |
| `ssp scan --sensor semgrep` without `--config` | 2 | `--config is required when --sensor=semgrep` |
| `ssp from-json` with a sensor error fixture | 3 | SSP envelope is still written with `aggregate_verdict: unknown`. |
| Internal bug | 4 | `internal error: <one-line>; rerun with --verbose for traceback` |

With `--verbose`, expected engine errors also print a traceback after the
one-line diagnostic.

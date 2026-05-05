# Semantic CI Exit Codes

Semantic CI uses stable exit codes so CI systems can route failures without
parsing output text.

| Code | Meaning | Typical trigger |
|---:|---|---|
| `0` | Pass | `Verdict.result == pass`. |
| `0` | Repair advisory | `Verdict.result == repair` without `--strict-repair`. |
| `0` | No staged work | `semantic-ci pre-commit` with an empty staged index. |
| `1` | Semantic failure | `Verdict.result == fail`. |
| `1` | Strict repair | `Verdict.result == repair` with `--strict-repair`. |
| `2` | Usage or configuration error | Bad flags, missing paths, missing or ambiguous `target.yaml`, unsupported language. |
| `3` | Engine error | `CompileError`, `ExtractorError`, expected git command failure, git unavailable. |
| `4` | Internal bug | Unexpected Python exception. |

## Subcommand Notes

`observe` does not compute a verdict, so it returns only 0, 2, 3, or 4.

`compare`, `check`, and `pre-commit` map PASS/REPAIR/FAIL through the table
above. `--strict-repair` changes only REPAIR from exit 0 to exit 1.
`check --mode smoke` and `pre-commit --mode smoke` use the same exit-code
policy; skipped constraints are reported in output but do not contribute to
PASS, REPAIR, or FAIL.

Cache hit, miss, invalidation, write failure, and best-effort eviction do not
change exit-code policy. Cache write and eviction failures are reported through
cache stats or verbose diagnostics, then the command continues with the computed
verdict.

`compile` does not compute a verdict. Successful compilation exits 0. Target
discovery errors exit 2. Compile errors exit 3.

## Error Streams

Stdout is reserved for JSON or human report output. Expected diagnostic messages
go to stderr.

| Situation | Exit | Stderr |
|---|---:|---|
| Missing target | 2 | `target.yaml not found; tried ./target.yaml and ./.semantic-ci/target.yaml. Use --target.` |
| Ambiguous target | 2 | `ambiguous target.yaml location: both ./target.yaml and ./.semantic-ci/target.yaml exist; use --target.` |
| Compile error | 3 | One-line `CompileError` with filename and path/line where available. |
| Extractor error | 3 | `extractor failed: <name> at <path>: <reason>` |
| Git unavailable | 3 | `git is required for 'check'; install git or use 'compare'` or the subcommand-specific equivalent. |
| Dirty working tree in `check` | 0/1 | Warning, unless `--allow-dirty` is used. |
| Internal bug | 4 | `internal error: <one-line>; rerun with --verbose for traceback` |

With `--verbose`, expected engine errors also print a traceback after the
one-line diagnostic.

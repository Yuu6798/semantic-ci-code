# 02 - Imports Unchanged, Effects Changed

Declared intent: keep status rendering free of process execution.

What changed: both sides import `subprocess`, so a simple import diff is not
enough. The candidate starts calling `subprocess.run`, adding a `process`
effect.

Scope guard line: not a linter.

Expected verdict: `fail`

Expected exit code: `1`

Run:

```bash
semantic-ci compare --baseline-dir examples/02-imports-same-effects-change/baseline --candidate-dir examples/02-imports-same-effects-change/candidate --target examples/02-imports-same-effects-change/target.yaml
```


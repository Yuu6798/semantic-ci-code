# Runnable Examples Gallery

These examples are hand-built baseline/candidate directory pairs. They use
`semantic-ci compare`, not git refs, live scanners, network access, or test
execution. Each case demonstrates one scope-guard differentiator.

Run any case with:

```bash
semantic-ci compare --baseline-dir examples/<case>/baseline --candidate-dir examples/<case>/candidate --target examples/<case>/target.yaml
```

| Case | Scope-guard line | Expected verdict | Expected exit code |
|---|---|---:|---:|
| [`01-tests-pass-intent-fails`](01-tests-pass-intent-fails/) | not a test runner | `fail` | `1` |
| [`02-imports-same-effects-change`](02-imports-same-effects-change/) | not a linter | `fail` | `1` |
| [`03-api-same-complexity-grows`](03-api-same-complexity-grows/) | not a type checker | `fail` | `1` |
| [`04-llm-style-intent-drift`](04-llm-style-intent-drift/) | not LLM-as-judge | `fail` | `1` |

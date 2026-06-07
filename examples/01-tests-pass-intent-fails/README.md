# 01 - Tests Would Pass, Intent Is Violated

Declared intent: add a public coupon API named `billing.apply_coupon`.

What changed: the candidate only adds a passing smoke test around the existing
`billing.total` function. It does not add the declared coupon API.

The smoke test is green, but the verdict still fails because the declared API
addition is missing.

Scope guard line: not a test runner.

Expected verdict: `fail`

Expected exit code: `1`

Run:

```bash
semantic-ci compare --baseline-dir examples/01-tests-pass-intent-fails/baseline --candidate-dir examples/01-tests-pass-intent-fails/candidate --target examples/01-tests-pass-intent-fails/target.yaml
```

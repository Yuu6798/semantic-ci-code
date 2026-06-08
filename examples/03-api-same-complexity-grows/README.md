# 03 - API Surface Unchanged, Complexity Grows

Declared intent: keep the public pricing API shape while avoiding more complex
pricing logic.

What changed: the candidate preserves the `pricing.shipping_cost` signature but
adds branches that increase cyclomatic complexity. The engine is not comparing
runtime behavior here; it is enforcing the declared "keep it simple" intent via
the `complexity_delta.cyclomatic` proxy.

Scope guard line: not a type checker.

Expected verdict: `fail`

Expected exit code: `1`

Run:

```bash
semantic-ci compare --baseline-dir examples/03-api-same-complexity-grows/baseline --candidate-dir examples/03-api-same-complexity-grows/candidate --target examples/03-api-same-complexity-grows/target.yaml
```

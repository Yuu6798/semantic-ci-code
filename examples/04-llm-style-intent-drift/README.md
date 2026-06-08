# 04 - LLM-Style Candidate Drifts From Declared Intent

Declared intent: add a pure markdown summary formatter without deserialization
or dangerous imports.

What changed: the candidate keeps a plausible formatter shape but adds
`pickle.loads`, drifting from the declared safety boundary.

Scope guard line: not LLM-as-judge.

Expected verdict: `fail`

Expected exit code: `1`

Run:

```bash
semantic-ci compare --baseline-dir examples/04-llm-style-intent-drift/baseline --candidate-dir examples/04-llm-style-intent-drift/candidate --target examples/04-llm-style-intent-drift/target.yaml
```


# LLM Scout Usage

This guide covers the advisory-only LLM scout path. LLM findings are never a
verdict by themselves. They are candidates for review, mute, or promotion into
deterministic `target.yaml` constraints.

## Quick Start

Run `check` with one recorded Codex Security payload:

```bash
semantic-ci check \
  --advisory-sensor codex-security=codex-security-output.json \
  --format json
```

Run with multiple recorded scout payloads. Semantic CI aggregates them into a
single `llm-ensemble` advisory state before re-projection:

```bash
semantic-ci check \
  --advisory-sensor codex-security=codex-security-a.json \
  --advisory-sensor codex-security=codex-security-b.json \
  --format json
```

Add an advisory mute ledger when a surfaced candidate is known and accepted:

```bash
semantic-ci check \
  --advisory-sensor codex-security=codex-security-output.json \
  --advisory-mutes .semantic-ci/advisory_mutes.yaml \
  --as-of 2026-09-01
```

The recommended mute ledger location is `.semantic-ci/advisory_mutes.yaml`.
Semantic CI does not auto-discover this file; pass it explicitly.

## Promotion Path

The LLM scout path is intentionally advisory:

1. A scout reports a candidate finding.
2. A human reviews it.
3. If it should become a gate, freeze the intent as a deterministic
   `target.yaml` constraint or recipe.
4. Future verdicts are owned by that deterministic constraint, not by the LLM.

There is no automatic promotion. Silence means consent: if a surfaced advisory
candidate is neither muted nor promoted into a declared constraint, it remains
non-blocking and the normal verdict continues unchanged.

Examples of promotion targets:

| Scout finding class | Deterministic promotion surface |
|---|---|
| `missing-authz` | `semantic-ci init --recipe security:preserve-auth-guards` and review the generated `decorators_delta.removed` constraint. |
| Dangerous import | `security:deny-dangerous-imports`, or a hand-written `imports_delta.added excludes_all` constraint. |
| Dangerous effect | `security:deny-dangerous-effects`, or a hand-written `effect_changes.added excludes_all` constraint. |
| Deterministic SAST/SCA finding | `target.yaml security:` policy plus gate suppressions when needed. |

## Mutes vs Suppressions

Advisory mutes and security suppressions are different mechanisms:

| Mechanism | File / namespace | Affects verdict | Intended use |
|---|---|---:|---|
| Advisory mute ledger | `.semantic-ci/advisory_mutes.yaml` passed with `--advisory-mutes` | No | "We saw this scout candidate; stop surfacing it until expiry." |
| Security suppression | `target.yaml security.suppressions` | Yes | "This deterministic sensor finding is accepted for gate evaluation until expiry." |

This separation is intentional: merging the two mechanisms would let an
advisory-only control cross into the verdict-bearing policy layer.

Advisory mute entries use the LLM finding canonical identity. In ensemble mode,
the canonical id changes because the finding is re-projected under
`sensor_id="llm-ensemble"`. A mute written for a single `codex-security`
finding will not match the ensemble finding. Write the mute from the mode you
intend to keep using.

## Output

JSON output adds top-level `advisory`:

```json
{
  "advisory": {
    "adapter_id": "llm-ensemble",
    "sensor": {
      "sensor_id": "llm-ensemble",
      "model_id": "ensemble:codex-a,codex-b",
      "prompt_hash": "sha256:..."
    },
    "members": [
      {"sensor_id": "codex-security", "model_id": "codex-a"},
      {"sensor_id": "codex-security", "model_id": "codex-b"}
    ],
    "surfaced": [],
    "pre_existing": [],
    "muted": [],
    "counts": {
      "scouted": 0,
      "surfaced": 0,
      "pre_existing": 0,
      "muted": 0
    }
  }
}
```

`advisory` is additive and verdict-non-participating. `verdict`,
`suite_verdict`, `repair_plan`, `summary`, and exit code are unchanged by scout
findings, including `critical` findings and non-complete advisory sensor runs.

For ensemble runs, `counts.scouted` is the number of findings after anchor
deduplication, not the sum of findings reported by all members. When members
report the same anchor with different severities, the ensemble uses both the
severity and message from the deterministic maximum-severity member.

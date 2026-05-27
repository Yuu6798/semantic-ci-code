# SSP Usage Guide

This guide is for humans (and AI assistants) using the `semantic-ci ssp`
subcommand group. It is a practical companion to the canonical references —
it does **not** replace them:

- `docs/ssp_protocol.md` — normative SSP v0.1 spec (domain types,
  fingerprint algorithm, delta computation, verdict precedence)
- `docs/cli_usage.md` § `semantic-ci ssp` — full flag reference
- `docs/exit_codes.md` — SSP exit code policy

> **What SSP is:** A sibling protocol that computes deterministic security
> sensor deltas alongside the core Semantic CI verdict. SSP does not modify
> core verdict semantics — the two envelopes are independent.

> **What SSP is not:** SSP is not a scanner. It orchestrates external
> scanners (Semgrep, pip-audit) and computes the *delta* between two scans.
> A single scan is not useful on its own — SSP needs a baseline and a
> candidate to produce a verdict.

## Quick Start

### 1. SAST delta with Semgrep

Compare two directory snapshots for new static analysis findings:

```bash
semantic-ci ssp scan \
  --sensor semgrep \
  --config semgrep.yml \
  --baseline-dir /tmp/baseline \
  --candidate-dir /tmp/candidate \
  --package-root src
```

- `--config` is the Semgrep ruleset file (required for `--sensor semgrep`).
- `--package-root` selects the subdirectory scanned inside each tree
  (defaults to `.`).
- Exit 0 = pass (no new findings, or only `info`-severity additions).
  Exit 1 = fail (new findings with severity `low` or above).

### 2. SCA delta with pip-audit

Compare two project snapshots for new dependency vulnerabilities:

```bash
semantic-ci ssp scan \
  --sensor pip-audit \
  --baseline-dir /tmp/baseline \
  --candidate-dir /tmp/candidate
```

If `requirements.txt` exists in a directory, it is passed to pip-audit
via `--requirement`. Otherwise pip-audit audits the project directory
directly (using `--locked` when supported, or the directory path as
fallback).

### 3. Fixture mode (no scanner required)

When sensors are not installed (e.g. in CI without Semgrep), use
pre-captured `SensorOutput` JSON files:

```bash
semantic-ci ssp from-json \
  --baseline baseline_sensor.json \
  --candidate candidate_sensor.json
```

This computes the same delta and verdict without executing any external
process. Useful for:

- CI environments without Semgrep/pip-audit installed
- Reproducible testing with frozen fixtures
- What-if analysis with hand-built sensor output

## Output Formats

### JSON (default)

```bash
semantic-ci ssp from-json \
  --baseline baseline.json \
  --candidate candidate.json \
  --format json
```

Emits the full `SSPEnvelope` with `schema_version: "ssp-1"`. The output
validates against `src/semantic_ci_code/schemas/ssp_envelope_v1.json`.

Key fields in the JSON output:

```json
{
  "schema_version": "ssp-1",
  "aggregate_verdict": "fail",
  "deltas_by_sensor": {
    "semgrep": {
      "status": "fail",
      "added": [{"rule_id": "python.security.eval", "severity": "high", ...}],
      "removed": [],
      "unchanged_count": 1
    }
  }
}
```

### Human-readable

```bash
semantic-ci ssp from-json \
  --baseline baseline.json \
  --candidate candidate.json \
  --format human
```

Outputs a compact summary:

```
SSP summary
aggregate verdict: fail

sensor: semgrep
  verdict: fail
  added: 1
  removed: 0
  unchanged: 1
  added findings:
    - [high] python.security.eval at src/app.py:5 - New eval use
```

### SARIF 2.1.0

```bash
semantic-ci ssp from-json \
  --baseline baseline.json \
  --candidate candidate.json \
  --format sarif \
  --output ssp.sarif
```

Emits SARIF 2.1.0 JSON suitable for GitHub Code Scanning upload.
Severity mapping:

| SSP severity | SARIF level |
|---|---|
| `critical` / `high` | `error` |
| `medium` | `warning` |
| `low` / `info` | `note` |

SAST findings include `physicalLocation` with file path and line/column.
SCA findings use `advisory_id` as the SARIF `ruleId`.

## CI Integration

### GitHub Actions workflow

```yaml
- name: SSP security delta
  run: |
    semantic-ci ssp scan \
      --sensor semgrep \
      --config .semgrep.yml \
      --baseline-dir baseline \
      --candidate-dir candidate \
      --format sarif \
      --output ssp.sarif

- name: Upload SARIF
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: ssp.sarif
```

### Exit code routing

| Exit | Meaning | CI action |
|---|---|---|
| 0 | Pass — no new findings, or only `info`-severity additions | Continue |
| 1 | Fail — new findings with severity >= low | Block merge or warn |
| 2 | Usage error — bad flags, missing files | Fix invocation |
| 3 | Sensor error — scanner failed, verdict unknown | Investigate |
| 4 | Internal bug | Report |

### Fixture-based CI (no scanner installation)

If your CI does not have Semgrep or pip-audit, capture per-side
`SensorOutput` JSON locally (where sensors are installed) and commit
the files:

```bash
# Capture baseline SensorOutput via the adapter Python API:
python -c "
import json
from semantic_ci_code.ssp.adapters.semgrep import SemgrepAdapter
from pathlib import Path
result = SemgrepAdapter().scan(Path('src'), ruleset=Path('.semgrep.yml'), repo_root=Path('.'))
print(json.dumps(result.output.model_dump(mode='json'), indent=2))
" > baseline_sensor.json

# After changes, capture candidate SensorOutput the same way:
python -c "
import json
from semantic_ci_code.ssp.adapters.semgrep import SemgrepAdapter
from pathlib import Path
result = SemgrepAdapter().scan(Path('src'), ruleset=Path('.semgrep.yml'), repo_root=Path('.'))
print(json.dumps(result.output.model_dump(mode='json'), indent=2))
" > candidate_sensor.json
```

The `from-json` subcommand expects **`SensorOutput` JSON** (with
`sensor_id`, `status`, `findings`), not raw Semgrep/pip-audit output
or SSP envelope JSON.

```bash
# In CI (no scanner needed):
semantic-ci ssp from-json \
  --baseline baseline_sensor.json \
  --candidate candidate_sensor.json
```

## Writing SensorOutput JSON by Hand

SSP accepts hand-built `SensorOutput` JSON — no real scanner needed.
This is guaranteed by the Sensor Provenance Invariant
(`docs/ssp_protocol.md` §4).

Minimal SAST example:

```json
{
  "sensor_id": "semgrep",
  "status": "complete",
  "findings": [
    {
      "category": "sast",
      "rule_id": "python.security.eval",
      "module_path": "src/app.py",
      "qualified_name": "src.app.handler",
      "normalized_text": "eval(user_input)",
      "severity": "high",
      "message": "Avoid eval with user input",
      "source_span": {
        "start_line": 5,
        "start_col": 5,
        "end_line": 5,
        "end_col": 21
      }
    }
  ]
}
```

Minimal SCA example:

```json
{
  "sensor_id": "pip-audit",
  "status": "complete",
  "findings": [
    {
      "category": "sca",
      "package_name": "django",
      "installed_version": "3.2.0",
      "advisory_id": "PYSEC-2021-9",
      "severity": "critical",
      "message": "SQL injection in Django QuerySet"
    }
  ]
}
```

`fingerprint` is optional for both SAST and SCA — the delta engine
computes fingerprints automatically. For SAST findings, `ordinal`,
`normalization`, and `source_span` are also optional (SAST-only fields;
do not add these to SCA findings as the model rejects unknown fields).
Set `severity` to one of: `critical`, `high`, `medium`, `low`, `info`.

## How SSP Computes the Delta

1. Both baseline and candidate `SensorOutput` values are fingerprinted:
   - SAST: 5-element canonical JSON → SHA-256[:16]
     (`rule_id`, `module_path`, `qualified_name`, `normalized_text`, `ordinal`)
   - SCA: 3-element canonical JSON → SHA-256[:16]
     (`package_name`, `installed_version`, `advisory_id`)

2. Fingerprint sets are compared:
   - `added` = in candidate but not baseline (new findings)
   - `removed` = in baseline but not candidate (fixed findings)
   - `unchanged_count` = in both

3. Verdict:
   - Any added finding with severity >= `low` → `fail`
   - Only `info` additions or no additions → `pass`
   - Sensor error → `unknown`
   - Aggregate: `unknown > fail > pass`

## Relationship to Core Semantic CI

SSP and the core verdict engine are independent:

```
semantic-ci check   → core verdict (target.yaml adherence)
semantic-ci ssp     → SSP envelope (security sensor delta)
```

They share no schema definitions. A CI pipeline can run both and gate
on either or both. Future suite-layer tooling may aggregate them, but
SSP v0.1 does not bundle with the core verdict.

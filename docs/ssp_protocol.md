# Semantic Security Protocol (SSP) v0.1

> **Status**: ACTIVE — normative v0.1 spec for the SSP data layer.
>
> SSP is a sibling protocol for deterministic security sensor deltas.
> It does not change semantic-ci core verdict semantics.
> The core verdict envelope and SSP envelope are separate;
> aggregation is suite-layer responsibility.

## §1. Scope and Non-goals

### §1.1 Scope

SSP v0.1 covers two sensor categories for Python projects:

- **SAST** (Static Application Security Testing): source-code pattern-match
  findings (Semgrep as reference adapter).
- **SCA** (Software Composition Analysis): known-CVE findings in dependency
  packages (pip-audit as reference adapter).

Language: Python only (Brief 6 / TypeScript is frozen).

### §1.2 Non-goals

- Secrets scanning, IaC scanning, CodeQL, Bandit adapters.
- TypeScript / npm / multi-language support.
- Auto-template: SSP delta does not influence core verdict without explicit
  `target.yaml` declaration.
- Deep core integration: SSP never writes to `CodeState` or participates
  in the core evaluator.
- SARIF-first design: SARIF is an output target, not the internal format.
- GitHub Marketplace publication.

### §1.3 Naming

Full name: **Semantic Security Protocol (SSP)**. CLI subcommand:
`semantic-ci ssp <subcmd>`. NIST System Security Plan collision is
accepted; the full name at first mention provides disambiguation.

## §2. Definitions

### §2.1 Finding Types

A **Finding** is a discriminated union (`category` field) of two variants:

#### SAST Finding

| Field | Type | Required | Description |
|---|---|---|---|
| `category` | `"sast"` | yes | Discriminator |
| `rule_id` | `string` (non-empty) | yes | Sensor rule identifier |
| `module_path` | `string` (non-empty) | yes | Repo-relative POSIX path (backslash normalized to `/`) |
| `qualified_name` | `string` (non-empty) | yes | `<module>.<class>...<func>` walk-up scope |
| `normalized_text` | `string` | yes | Python-profile-normalized source text (§5.3) |
| `ordinal` | `int ≥ 0 \| null` | no | Assigned by ordinal algorithm (§5.1.2), null before assignment |
| `fingerprint` | `string[16] \| null` | no | SHA-256[:16] hex, computed from 5-element tuple (§5.1) |
| `severity` | Severity | yes | `critical \| high \| medium \| low \| info` |
| `message` | `string` | no | Human-readable description, default `""` |
| `source_span` | SourceSpan \| null | no | Location in source, null for virtual findings |
| `normalization` | `"ast" \| "raw"` | no | Which normalization path was used, default `"ast"` |

#### SCA Finding

| Field | Type | Required | Description |
|---|---|---|---|
| `category` | `"sca"` | yes | Discriminator |
| `package_name` | `string` (non-empty) | yes | PyPI package name |
| `installed_version` | `string` (non-empty) | yes | Installed version string |
| `advisory_id` | `string` (non-empty) | yes | Advisory identifier (e.g. `PYSEC-2021-9`) |
| `fingerprint` | `string[16] \| null` | no | SHA-256[:16] hex, computed from 3-element tuple (§5.2) |
| `severity` | Severity | yes | `critical \| high \| medium \| low \| info` |
| `message` | `string` | no | Human-readable description, default `""` |

### §2.2 SourceSpan

| Field | Type | Constraint |
|---|---|---|
| `start_line` | `int` | ≥ 1 |
| `start_col` | `int` | ≥ 0 |
| `end_line` | `int` | ≥ 1 |
| `end_col` | `int` | ≥ 0 |

### §2.3 SensorOutput

| Field | Type | Required | Description |
|---|---|---|---|
| `sensor_id` | `string` (non-empty) | yes | Unique sensor identifier (e.g. `"semgrep"`, `"pip-audit"`) |
| `sensor_version` | `string` | no | Sensor tool version, default `""` |
| `status` | `"complete" \| "error"` | no | Default `"complete"` |
| `findings` | `tuple[Finding, ...]` | no | Default `()`. Must be empty when `status == "error"` |
| `error_message` | `string \| null` | no | Error description when `status == "error"` |

**Invariant**: A `SensorOutput` with `status == "error"` MUST NOT include
findings. This is enforced at model validation time.

### §2.4 SSPDelta

| Field | Type | Required | Description |
|---|---|---|---|
| `sensor_id` | `string` (non-empty) | yes | Matches `SensorOutput.sensor_id` |
| `status` | SSPResult | yes | `pass \| fail \| unknown` |
| `added` | `tuple[Finding, ...]` | no | Findings present in candidate but not baseline |
| `removed` | `tuple[Finding, ...]` | no | Findings present in baseline but not candidate |
| `unchanged_count` | `int ≥ 0` | yes | Count of fingerprint-identical findings |
| `error_message` | `string \| null` | no | Propagated from error SensorOutput |

### §2.5 SSPVerdict

| Field | Type | Description |
|---|---|---|
| `sensor_verdicts` | `dict[str, SSPResult]` | Per-sensor verdict, keyed by sensor_id (sorted) |
| `aggregate_verdict` | SSPResult | Aggregate across all sensors (§7.2) |

### §2.6 SSPMetadata

| Field | Type | Default | Description |
|---|---|---|---|
| `timestamp` | `string` | `""` | ISO 8601 timestamp of the scan |
| `findings_order_invariant` | `"source-span" \| "schema-order"` | `"source-span"` | Which ordering invariant findings follow |

Metadata is optional in the JSON Schema and may be omitted by older producers.

## §3. Sensor Contract

### §3.1 Adapter Responsibility

A sensor adapter converts raw tool output into a `SensorOutput`. The
adapter is responsible for:

- Invoking the sensor tool with deterministic flags.
- Parsing tool output into `Finding` instances.
- Normalizing `module_path` to repo-relative POSIX form.
- Computing `qualified_name` by walking up AST scopes.
- Applying `normalize_text` (§5.3) to produce `normalized_text`.
- Setting `normalization` to `"ast"` or `"raw"` per the result.

### §3.2 Deterministic Invocation

Reference adapters MUST hard-code flags that eliminate non-determinism:

- Semgrep: `--metrics=off --disable-version-check --no-rewrite-rule-ids`
- pip-audit: use a pinned advisory database snapshot when possible.

### §3.3 Path Normalization

`module_path` is a repo-relative POSIX path (`os.sep` normalized to `/`,
`.py` extension retained). This ensures findings from the same file on
different OS platforms produce identical fingerprints.

### §3.4 Error Handling

When a sensor fails (non-zero exit, JSON parse failure, timeout, SIGTERM,
ruleset unavailable, advisory DB unavailable):

- `SensorOutput.status` = `"error"`
- `SensorOutput.findings` = `()` (empty)
- `SensorOutput.error_message` = description of the failure
- The resulting delta status is `"unknown"` (§6.2)
- The per-sensor verdict is `"unknown"` (§7.1)

## §4. Sensor Provenance Invariant

### §4.1 Statement

> The SSP delta engine consumes `SensorOutput` values. It does not
> inspect or discriminate based on the provenance of those values.

This is the mirror of `docs/code_semantic_ci_design.md` §23.1 (CodeState
provenance neutrality) applied to the SSP domain.

### §4.2 Supported Modes

| Mode | Baseline | Candidate | Use case |
|---|---|---|---|
| post-commit CI | main HEAD scan | PR head scan | Standard CI |
| pre-commit | HEAD scan | staged content scan | Local gate |
| pre-generation | current code scan | predicted/virtual | Pre-gen validation |
| contract test | hand-built | hand-built | Unit test |

All four modes produce valid `SensorOutput` values and flow through the
same `compute_delta` engine path. Tests MUST include at least one case
with fully hand-built (virtual) `SensorOutput` to prevent regression
into requiring real sensor execution.

## §5. Fingerprint Specification

### §5.1 SAST Fingerprint

The canonical SAST fingerprint is computed from a 5-element tuple:

```
(rule_id, module_path, qualified_name, normalized_text, ordinal)
```

Encoding: **canonical JSON array** (not delimiter join):

```python
import hashlib, json

def sast_fingerprint(rule_id: str, module_path: str,
                     qualified_name: str, normalized_text: str,
                     ordinal: int) -> str:
    payload = json.dumps(
        [rule_id, module_path, qualified_name, normalized_text, ordinal],
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

JSON array encoding is required because delimiter join (`:`) is not
injective — `normalized_text` and other fields may contain `:` legally.

#### §5.1.2 Ordinal Assignment Algorithm

The ordinal disambiguates multiple findings that share the same
`(rule_id, module_path, qualified_name, normalized_text)` 4-tuple.

Algorithm (5 steps):

1. **Collect** all raw SAST findings from the sensor output.
2. **Dedup** by the 5-tuple `(rule_id, module_path, qualified_name,
   normalized_text, source_span)` — identical source spans within the
   same 4-tuple group are duplicates. Dedup BEFORE grouping.
3. **Group** by the 4-tuple `(rule_id, module_path, qualified_name,
   normalized_text)`.
4. **Sort** each group by source span tuple
   `(start_line, start_col, end_line, end_col)` in ascending order
   (integer comparison, tie-break left to right). Findings without a
   source span sort before those with spans, using original iteration
   order as a stable tiebreaker.
5. **Assign** 0-indexed position within the sorted group as the ordinal.

Known trade-off: inserting a new finding within a group shifts subsequent
ordinals by +1, changing their fingerprints. This is accepted because
same-group collisions (identical rule × file × function × normalized text)
are rare in practice.

### §5.2 SCA Fingerprint

The canonical SCA fingerprint is computed from a 3-element tuple:

```
(package_name, installed_version, advisory_id)
```

Same encoding as SAST (canonical JSON array → SHA-256[:16]):

```python
def sca_fingerprint(package_name: str, installed_version: str,
                    advisory_id: str) -> str:
    payload = json.dumps(
        [package_name, installed_version, advisory_id],
        ensure_ascii=False, sort_keys=False, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

### §5.3 Python Profile (AST Normalization)

The `normalize_text` function produces the canonical text representation
for SAST fingerprints:

1. Attempt `ast.parse(source)` on the input.
2. If parsing succeeds: `ast.unparse(tree)` → strip leading/trailing
   whitespace → collapse internal whitespace runs to single space.
   Record `normalization: "ast"`.
3. If parsing fails (`SyntaxError`): use the raw source text → strip →
   collapse whitespace. Record `normalization: "raw"`.

Properties:

- **Whitespace-insensitive**: `"x=1\n\nprint( x )"` and
  `"x = 1\nprint(x)"` produce the same normalized text.
- **Comment-insensitive**: comments are stripped by `ast.unparse`.
- **Deterministic**: same source always produces the same output.

## §6. Envelope Schema

### §6.1 Top-level Structure

```json
{
  "schema_version": "ssp-1",
  "engine": {
    "ssp_version": "0.1",
    "scan_mode": "real",
    "baseline": {"kind": "git-rev", "ref": "origin/main"},
    "candidate": {"kind": "git-rev", "ref": "HEAD"},
    "sensors": [
      {"id": "semgrep", "version": "1.161.0", "ruleset_hash": "sha256:..."}
    ]
  },
  "deltas_by_sensor": {
    "semgrep": {
      "sensor_id": "semgrep",
      "status": "pass",
      "added": [],
      "removed": [],
      "unchanged_count": 1
    }
  },
  "aggregate_verdict": "pass",
  "metadata": {
    "timestamp": "2026-01-01T00:00:00Z",
    "findings_order_invariant": "source-span"
  }
}
```

The SSP envelope is independent of the core verdict envelope
(`schema_version: "6"`). They share no schema definitions.

Every `deltas_by_sensor` key must match the embedded `SSPDelta.sensor_id`.
The Pydantic model enforces this invariant so consumers cannot accidentally
misattribute a delta to the wrong sensor key.

### §6.2 Delta Computation

`compute_delta(baseline: SensorOutput, candidate: SensorOutput) -> SSPDelta`:

1. Validate that `baseline.sensor_id == candidate.sensor_id`.
2. If either sensor has `status == "error"`: return `SSPDelta` with
   `status = "unknown"`, empty `added`/`removed`, `unchanged_count = 0`,
   and propagated `error_message`.
3. Compute fingerprints for all findings in both sides (§5.1, §5.2,
   including ordinal assignment for SAST).
4. Partition by fingerprint set operations:
   - `added = candidate_fps - baseline_fps`
   - `removed = baseline_fps - candidate_fps`
   - `unchanged_count = len(baseline_fps & candidate_fps)`
5. Compute verdict for the delta (§7.1).

### §6.3 Finding Discrimination

SAST and SCA findings have different field sets. They are distinguished
by the `category` discriminator field:

- `category: "sast"` → SASTFinding (5-element fingerprint, source_span,
  normalization)
- `category: "sca"` → SCAFinding (3-element fingerprint, no source location)

Both variants appear in the same `added`/`removed` arrays within an
`SSPDelta`, serialized as a discriminated union.

### §6.4 JSON Schema Artifact

The normative JSON Schema is at
`src/semantic_ci_code/schemas/ssp_envelope_v1.json`
(JSON Schema draft 2020-12). A conforming `SSPEnvelope.model_dump(mode="json")`
output MUST validate against this schema.

## §7. Aggregation and Verdict

### §7.1 Per-sensor Verdict

`verdict_for_delta(delta: SSPDelta) -> SSPResult`:

1. If `delta.status == "unknown"`: return `"unknown"`.
2. If any finding in `delta.added` has `severity ∈ {critical, high,
   medium, low}`: return `"fail"`.
3. Otherwise (no added findings, or all added findings are `info`-only):
   return `"pass"`.

Rationale: `info`-severity findings are advisory and do not gate CI.
Removed findings never cause failure (removing a vulnerability is good).

### §7.2 Aggregate Verdict

`aggregate_verdict(verdicts: Iterable[SSPResult]) -> SSPResult`:

Precedence: `unknown > fail > pass`.

- If any sensor verdict is `"unknown"`: aggregate is `"unknown"`.
- Else if any sensor verdict is `"fail"`: aggregate is `"fail"`.
- Otherwise: `"pass"`.

### §7.3 Severity

| SSP severity | Semantics |
|---|---|
| `critical` | Critical — MUST be addressed |
| `high` | High — MUST be addressed |
| `medium` | Medium — SHOULD be addressed |
| `low` | Low — SHOULD be addressed |
| `info` | Informational — does not cause verdict `fail` |

## §8. Reference Adapters

> Adapter implementations are out of scope for CSCI-37.
> See CSCI-38 (SemgrepAdapter) and CSCI-39 (pip-audit Adapter).

### §8.1 SemgrepAdapter (CSCI-38)

Converts Semgrep JSON output to `SensorOutput` with SAST findings.
Must hard-code `--metrics=off --disable-version-check --no-rewrite-rule-ids`.

### §8.2 pip-audit Adapter (CSCI-39)

Converts pip-audit JSON output to `SensorOutput` with SCA findings.
Must use a pinned advisory database snapshot for baseline/candidate parity.

## §9. Determinism Requirements

### §9.1 Invariants

Two invariants MUST hold and MUST be tested:

| ID | Invariant | Test method |
|---|---|---|
| **D-1** | Frozen fixtures produce byte-identical serialized output across runs | Serialize the same delta twice in the same process, compare bytes |
| **D-2** | Output is identical across `PYTHONHASHSEED` values | Run the same computation in subprocesses with seeds `0`, `1`, `random`; compare JSON output |

### §9.2 Audit Trail

The following audit results from Issue #48 (2026-05-06) informed the
SSP design:

| ID | Result | SSP implication |
|---|---|---|
| A1 | PASS (byte-identical, N=20) | Same-input regression test |
| A3 | CONDITIONAL PASS | Path repo-relative normalization required |
| C1 | FAIL (line-based fp unstable) | Self-computed 5-element fingerprint, not Semgrep `extra.fingerprint` |
| E1 | NOTE | Adapter must handle SIGTERM / parse failure → `unknown` |

## §10. CLI Surface

> CLI implementation is out of scope for CSCI-37.
> See CSCI-40 (`semantic-ci ssp` subcommand group).

The planned CLI entry point is `semantic-ci ssp scan` with subcommands
for running sensors, computing deltas, and emitting envelopes.

## §11. Relationship to SARIF

SSP's internal format is the `SSPEnvelope` (§6). SARIF 2.1.0 is an
output target via a one-way `ssp-to-sarif` converter (CSCI-40), enabling
upload to GitHub Code Scanning. SARIF is not the internal representation.

## §12. Compatibility and Versioning

- `schema_version: "ssp-1"` is the v0.1 schema identifier.
- Breaking schema changes increment the version (e.g. `"ssp-2"`).
- The SSP version (`engine.ssp_version: "0.1"`) tracks the protocol
  version independently of the schema version.
- SSP envelope versioning is independent of the core verdict envelope
  versioning (`schema_version: "6"`).

## §13. Core Isolation

The SSP package (`semantic_ci_code.ssp`) MUST NOT import from:

- `semantic_ci_code.cli`
- `semantic_ci_code.evaluator`
- `semantic_ci_code.compiler`
- `semantic_ci_code.repair_compiler`

This isolation is enforced by `tests/architecture/test_ssp_isolation.py`
via transitive import closure analysis.

Allowed dependencies: stdlib (`hashlib`, `json`, `ast`) and `pydantic`.

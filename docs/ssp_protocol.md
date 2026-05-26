# Semantic Security Protocol (SSP) v0.1

Status: normative v0.1 protocol for Brief 7 / SSP.

SSP is a sibling protocol for deterministic security sensor deltas. It does
not change the core semantic-ci verdict envelope or evaluator semantics.
Adapters produce `SensorOutput` values, the SSP data layer computes pure
deltas, and suite-level tooling may later render or bundle the result.

## 1. Invariants

- SSP consumes sensor output only. The delta engine must not inspect whether a
  sensor output came from a real scan, staged scan, virtual fixture, or
  hand-built test object.
- SSP is deterministic: identical `SensorOutput` values produce byte-identical
  deltas and verdicts.
- SSP does not import or depend on semantic-ci CLI, compiler, evaluator, or
  repair-compiler modules.

## 2. Domain Types

### 2.1 `SensorOutput`

`SensorOutput` is the adapter boundary object.

| Field | Type | Semantics |
|---|---|---|
| `sensor_id` | string | Stable sensor identifier, for example `semgrep` or `pip-audit`. |
| `sensor_version` | string | Sensor implementation version, empty when unknown. |
| `status` | `"complete"` or `"error"` | `"complete"` means findings are usable; `"error"` means the sensor failed and findings must be empty. |
| `findings` | array of `Finding` | SAST or SCA findings. Empty for `status="error"`. |
| `error_message` | string or null | Error detail for failed sensors. |

### 2.2 `Finding`

SSP v0.1 defines two finding variants.

SAST finding:

| Field | Type | Semantics |
|---|---|---|
| `category` | const `"sast"` | Discriminator. |
| `rule_id` | string | Sensor rule identifier. |
| `module_path` | string | POSIX-style module path. |
| `qualified_name` | string | Best available symbol or module qualified name. |
| `normalized_text` | string | Python profile normalized source text. |
| `ordinal` | integer or null | Assigned by the ordinal algorithm in section 5.1.2. |
| `fingerprint` | string or null | 16-hex-character fingerprint. |
| `severity` | SSP severity | See section 7.3. |
| `message` | string | Human-readable finding text. |
| `source_span` | object or null | `start_line`, `start_col`, `end_line`, `end_col`. |
| `normalization` | `"ast"` or `"raw"` | Python normalization path used. |

SCA finding:

| Field | Type | Semantics |
|---|---|---|
| `category` | const `"sca"` | Discriminator. |
| `package_name` | string | Installed package name. |
| `installed_version` | string | Installed vulnerable version. |
| `advisory_id` | string | Advisory identifier. |
| `fingerprint` | string or null | 16-hex-character fingerprint. |
| `severity` | SSP severity | See section 7.3. |
| `message` | string | Human-readable advisory text. |

## 3. Sensor Metadata

Sensor run details that describe scan completeness belong to `SensorOutput`,
not to `engine.sensors[]`. In v0.1, the envelope sensor list is intentionally
flat and only records adapter identity/configuration fields. Future coverage
metadata may extend `SensorOutput` without changing core semantic-ci verdicts.

## 4. Sensor Provenance Invariant

The SSP delta engine accepts real, staged, virtual, and hand-built
`SensorOutput` values through the same API. Tests for the data layer should use
at least one hand-built virtual `SensorOutput` and must not require real sensor
execution.

## 5. Fingerprints

### 5.1 SAST Fingerprint

The SAST fingerprint input is the canonical JSON array:

```json
[rule_id, module_path, qualified_name, normalized_text, ordinal]
```

The fingerprint is:

```text
sha256(canonical_json_array_utf8).hexdigest()[:16]
```

The JSON encoding is compact UTF-8 JSON with no delimiter-join substitute.

### 5.1.2 SAST Ordinal Assignment

For all SAST findings emitted by one sensor output:

1. Deduplicate exact finding locations before ordinal assignment.
2. Group findings by `(rule_id, module_path, qualified_name, normalized_text)`.
3. Sort each group by `(start_line, start_col, end_line, end_col)`.
4. Assign 0-indexed ordinals inside each group.
5. Compute the SAST fingerprint from the 5-element array above.

### 5.2 SCA Fingerprint

The SCA fingerprint input is the canonical JSON array:

```json
[package_name, installed_version, advisory_id]
```

The fingerprint is:

```text
sha256(canonical_json_array_utf8).hexdigest()[:16]
```

### 5.3 Python Profile Normalization

Python SAST text normalization is:

1. Try `ast.parse(source)` and `ast.unparse(tree)`.
2. If parsing succeeds, normalize the unparsed text.
3. If parsing fails, normalize the raw input text.
4. Normalization strips leading/trailing whitespace and collapses all
   whitespace runs to a single ASCII space.

The finding records `normalization="ast"` for the AST path and
`normalization="raw"` for the fallback path.

## 6. Envelope

### 6.1 `SSPEnvelope`

Example:

```json
{
  "schema_version": "ssp-1",
  "engine": {
    "ssp_version": "0.1",
    "scan_mode": "real",
    "baseline": {"kind": "git-rev", "ref": "origin/main"},
    "candidate": {"kind": "git-rev", "ref": "HEAD"},
    "sensors": [
      {
        "id": "semgrep",
        "version": "1.161.0",
        "ruleset_hash": "sha256:...",
        "advisory_db_hash": null
      }
    ]
  },
  "deltas_by_sensor": {},
  "aggregate_verdict": "pass",
  "metadata": {
    "timestamp": "2026-01-01T00:00:00Z",
    "findings_order_invariant": "source-span"
  }
}
```

`engine.sensors[]` is a flat structure:

| Field | Type | Semantics |
|---|---|---|
| `id` | string | Stable sensor identifier. |
| `version` | string | Adapter or tool version, empty when unknown. |
| `ruleset_hash` | string or null | SAST ruleset hash when available. |
| `advisory_db_hash` | string or null | SCA advisory database hash when available. |

`metadata` is optional in the JSON Schema and may be omitted by older
producers. When present, `findings_order_invariant` is `"source-span"` or
`"schema-order"`.

### 6.2 `SSPDelta`

`deltas_by_sensor.<sensor_id>` maps to:

| Field | Type | Semantics |
|---|---|---|
| `sensor_id` | string | Sensor identifier. |
| `status` | `"pass"`, `"fail"`, or `"unknown"` | `"pass"` / `"fail"` mean delta computation succeeded and store the per-sensor verdict directly. `"unknown"` means a sensor error made delta computation unavailable. |
| `added` | array of `Finding` | Candidate findings not present in baseline. |
| `removed` | array of `Finding` | Baseline findings not present in candidate. |
| `unchanged_count` | integer | Count of fingerprints present in both baseline and candidate. |
| `error_message` | string or null | Error detail for unknown deltas. |

Delta partitioning is by fingerprint:

```text
added = candidate_fps - baseline_fps
removed = baseline_fps - candidate_fps
unchanged_count = len(candidate_fps & baseline_fps)
```

### 6.3 Finding JSON Shape

Findings are serialized as a discriminated union on `category`. SAST findings
and SCA findings keep their sensor-specific fields; adapters should not coerce
SCA advisories into source spans or SAST findings into package advisories.

### 6.4 JSON Schema

The JSON Schema artifact is `src/semantic_ci_code/schemas/ssp_envelope_v1.json`.
It validates conforming `SSPEnvelope` payloads and is versioned by
`schema_version="ssp-1"`.

## 7. Verdicts

### 7.1 Per-Sensor Verdict

Per-sensor verdict precedence is:

1. If the sensor output or delta is unavailable because the sensor errored,
   verdict is `"unknown"`.
2. If any added finding has severity `critical`, `high`, `medium`, or `low`,
   verdict is `"fail"`.
3. If all added findings are `info` or there are no added findings, verdict is
   `"pass"`.

### 7.2 Aggregate Verdict

Aggregate verdict precedence is:

```text
unknown > fail > pass
```

If any sensor is unknown, aggregate is `"unknown"`. Otherwise, if any sensor
failed, aggregate is `"fail"`. Otherwise aggregate is `"pass"`.

### 7.3 Severity

| SSP severity | Semantics |
|---|---|
| `critical` | Critical severity - MUST be addressed. |
| `high` | High severity - MUST be addressed. |
| `medium` | Medium severity - SHOULD be addressed. |
| `low` | Low severity - SHOULD be addressed. |
| `info` | Informational - does not cause verdict `fail`. |

## 8. Reference Adapter Profiles

### 8.1 SemgrepAdapter Severity Mapping

| Semgrep severity | SSP severity |
|---|---|
| `ERROR` | `critical` |
| `WARNING` | `medium` |
| `INFO` | `info` |

### 8.2 pip-audit Severity Mapping

| CVSS range | SSP severity |
|---|---|
| 9.0-10.0 (Critical) | `critical` |
| 7.0-8.9 (High) | `high` |
| 4.0-6.9 (Medium) | `medium` |
| 0.1-3.9 (Low) | `low` |
| No CVSS | `medium` (conservative) |

## 9. Determinism Requirements

- D-1: Frozen virtual fixtures must produce byte-identical SSP deltas across
  repeated runs.
- D-2: SSP output must be byte-identical under `PYTHONHASHSEED=0`,
  `PYTHONHASHSEED=1`, and `PYTHONHASHSEED=random`.

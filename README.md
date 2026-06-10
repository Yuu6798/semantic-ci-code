# semantic-ci-code

Semantic CI Code Edition is a deterministic semantic CI layer for code changes.
It compares observed code semantics against a declared `target.yaml` intent and
returns stable JSON or human-readable repair guidance.

It is not a linter, type checker, test runner, or LLM-as-judge service.

## Project Status

**Experimental — pre-release.** This project is actively developed and
dogfooded, but it is **not** production-ready:

- **API, policy, and JSON output are unstable** and may change without notice.
  No stability guarantee is offered, and there is no tagged or published
  release (the `0.1.0` in `pyproject.toml` is a development placeholder, not a
  release).
- It is designed for **early review and dogfooding**, not for pinning in a
  production CI gate.
- What it is: a **deterministic** semantic CI layer that flags intent drift a
  linter, type checker, test suite, or LLM judge would miss — see the scope
  guard above.

See [`ROADMAP.md`](ROADMAP.md) for what must hold before a stable release, and
the [Dogfooding Findings Tracker](docs/dogfooding_findings_tracker.md) for the
honest record of what it has and has not caught (real-PR pass: 6 of 8 cases
matched reviewer-relevant signal, with 1 vacuous PASS and 1 authoring mismatch;
5 of 7 D-class findings resolved).

## Install

```bash
pip install -e ".[dev]"
semantic-ci --version
```

The legacy `semantic-ci-code` entrypoint is still available and unchanged.

## Quick Start

Create a minimal `target.yaml`:

```yaml
intent: add user profile endpoint
change:
  primary_kind: feature
```

For scoped exceptions, such as test helper movement that should not count as
production API breakage, add explicit allow-list policy:

```yaml
api_surface:
  allow_changes:
    - fqn_prefix: tests.helpers.
```

Scaffold a commented `target.yaml`:

```bash
semantic-ci init
```

Inspect a package without judging it:

```bash
semantic-ci observe --package-root src/semantic_ci_code --format json
```

Compare two local directories:

```bash
semantic-ci compare --baseline-dir /tmp/base --candidate-dir /tmp/candidate --target target.yaml
```

Check a git change against `origin/main`:

```bash
semantic-ci check --target target.yaml
```

Check staged changes before committing:

```bash
semantic-ci check --candidate-source=staged-index --target target.yaml
```

Dry-compile a target file:

```bash
semantic-ci compile --target target.yaml --format human
```

Render pre-generation guidance for a coding adapter:

```bash
semantic-ci validate-plan --target target.yaml --adapter claude-code
```

Render the repair plan from a verdict envelope:

```bash
semantic-ci check --format json | semantic-ci compile-repair --adapter claude-code
```

## Documentation

Start here:

- [ROADMAP.md](ROADMAP.md) — maturity status, exit criteria for a stable release, and the surfaces that may still break
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, the design / implementation split, and good first issues

Active references (current behavior):

- [LLM Scout Usage](docs/llm_scout_usage.md) — advisory-only recorded LLM scout usage, cross-model ensemble aggregation, mute ledger authoring, and promotion into deterministic `target.yaml` constraints

- [CLI Usage](docs/cli_usage.md) — all 10 subcommands (incl. the `ssp` sensor group), flags, target discovery, output formats, severity routing
- [Exit Codes](docs/exit_codes.md) — CI-facing exit code contract
- [JSON Output Schema](docs/json_schema.md) — verdict / compile envelopes (`schema_version="6"`) + compile-repair (`"1"`) / validate-plan (`"2"`) envelopes (independent versions)
- [Code Semantic CI Design](docs/code_semantic_ci_design.md) — Code Edition v0.1 design spec (3-state RPE, constraint type system, phase plan)
- [Runnable Examples Gallery](examples/README.md) — four deterministic `compare` cases for the scope-guard failure modes
- [CLI Test Inventory](docs/cli_test_inventory.md) — CLI test coverage map and reduction candidates
- [target.yaml Authoring Guide](docs/target_yaml_guide.md) — practical authoring guide; centralises hazards D1/D3/D4 (`--package-root` scope, template/user constraint duplication, config-only vacuous PASS)
- [Target Authoring Surface](docs/target_authoring_surface.md) — Authoring surface design contract (target.yaml generation paths, surface isolation, `candidate_code_used: false`)
- [AGENTS.md](AGENTS.md) — Claude × Codex task handoff protocol + Experience Externalization Discipline (§5)
- [SSP v0.1 Protocol Spec](docs/ssp_protocol.md) — normative v0.1 spec: definitions, fingerprint, Python profile, delta computation, verdict, JSON Schema, Sensor Provenance Invariant
- [SSP Usage Guide](docs/ssp_usage_guide.md) — practical guide: quick start, output formats, CI integration, hand-built fixtures, delta mechanics
- [SSP v0.1 Forward Design Note](docs/ssp_protocol_design_note.md) — Brief 7 implementer 用 一次資料 (Phase 4 で AGENTS.md inline から分離)
- [Repository Layout](docs/repository_layout.md) — full `src/` / `tests/` tree with per-module CSCI annotations (offloaded from CLAUDE.md to keep policy lean)
- [CLAUDE.md](CLAUDE.md) — repository-level agent operating policy

Planning (open):

- [PR Validation — Phase X-2 (code domain) external validation](docs/pr_validation_planning.md) — falsification experiment for the core thesis: collect N≥48 public PRs and correlate semantic-ci verdicts with human reviewer decisions. Y = review state (changes-requested=fail / approve=pass), diff fixed at the first substantive review's SHA, target A(generic) + B(intent-only from PR title/body/labels; bans both Y-leakage and candidate-tautology), primary metrics AUROC/MCC/F1/confusion matrix + bootstrap CI (ρ auxiliary), pre-registered. Measures "does it work?" beyond the existing "does it run?" dogfooding
- [Phase G — SSP core integration](docs/phase_g_planning.md) — vertical-connect SSP v0.1 into core: SensorState parallel to CodeState, suite evaluator unifying code + security delta, FQN-translated findings, CSCI-45〜49 (active queue main axis)
- [LLM Security Sensor — Non-Deterministic Scout Layer (Phase H candidate)](docs/llm_sensor_adapter_planning.md) — connect a non-deterministic LLM security oracle (Codex Security et al.) as one sensor adapter atop Phase G. Core thesis: **LLM is a scout, not a judge** (on-demand, advisory surface, never seats the verdict). Determinism preserved via frozen SensorState + one-run-plus-reprojection; §23.1 not weakened; LLM-general adapter protocol; promotion only via target.yaml authoring freeze (silence = consent). Gated on Phase G-5, CSCI-50〜54
- [Brief 8 — Target Authoring Surface](docs/brief_8_planning.md) — target.yaml generation paths (recipe / catalog / hand-written), surface isolation from evaluator, `candidate_code_used: false`; encoded into `tests/authoring/` + `tests/architecture/`
- [Brief 7 — Semantic Security Protocol v0.1](docs/brief_7_planning.md) — SAST + SCA, Python only, independent envelope, Sensor Provenance Invariant
- [ResultStatus authoring/extraction split](docs/brief_resultstatus_planning.md) — C+B (compile-time pushback + `unknown_cause` sibling field), 5 PR split, validate-plan v2 — boundary with Brief 8 (Authoring Surface) pinned in §1b
- [Candidate / baseline source selection](docs/source_selection_planning.md) — `--candidate-source` / `--baseline-source` redesign, `--allow-dirty` removal, `pre-commit` subcommand migration; CLI-layer sourcing, engine §23.1 neutrality unchanged
- [Doc Refactoring Plan (urgent, 2026-05-21)](docs/doc_refactor_planning.md) — startup attention budget 2,500 → 800 lines compaction, Tier A/B/C/D 階層化, archive infrastructure, test-enforced rule conversion, 8 phase / 4-6 day scope

Reference / archived (completed briefs, retained for context — see [`docs/archive/README.md`](docs/archive/README.md)):

- [Brief 5 — Repair Compiler + Vibe Coding Adapters (P2.5 entry)](docs/archive/brief_5_planning.md) — CSCI-31〜35 merged 2026-05-07
- [Brief 4b — CI integration outputs (SARIF + GH Actions + pre-commit manifest)](docs/archive/brief_4b_planning.md) — CSCI-28 merged 2026-05-05
- [Brief 4 — CLI / operational entrypoint](docs/archive/brief_4_planning.md) — CSCI-15〜19 merged 2026-05-04
- [Brief 3 — Pipeline integration (judgment layer)](docs/archive/brief_3_planning.md) — CSCI-10〜14 merged

Out-of-core observation (case studies and dogfooding):

- [Dogfooding TC10 Report](docs/dogfooding_TC10_report.md) — 10 virtual-package cases through the CLI; FINDING-1 / D5 (set operator partial-dict semantics) resolved in PR #65
- [Dogfooding Real-PR Complexity Report](docs/dogfooding_real_pr_complexity.md) — 8 real-PR cases under complexity constraints; surfaces D6 (nested-function vacuous PASS) and D7 (extract-method × cyclomatic authoring mismatch), both open
- [Dogfooding Scale & Security Report](docs/dogfooding_scale_and_security.md) — 15 cases across litellm / langgraph / pdm: scale + large-function robustness (89-file / 514-symbol-delta / +5951 LOC inputs, 0 crashes, cache cold 103s → warm 11s) and SSP security observation (pip-audit SCA valid + positive-controlled; 2 real merged-then-fixed vulns established from git history; Semgrep SAST sub-pass network-blocked, HTTP 403 / 0 rules — not a valid SAST measurement); surfaces D8 (SCA pyproject/pdm.lock discovery gap) and F6 (pattern-SAST logic-vuln blindspot — untested-here hypothesis / Phase H motivation, not demonstrated this pass)
- [Dogfooding Findings Tracker](docs/dogfooding_findings_tracker.md) — consolidated D-class status (D1〜D8) across all dogfooding passes
- [Pre-Generation Validation Case](docs/pre_generation_validation_case.md) — observation that stub-only candidates are accepted by the engine input contract; reproduction in `experiments/pre_generation_validation/`
- [Multi-Agent Audit Case](docs/multi_agent_audit_case.md) — orchestrator-blindspot observation when running parallel agents

## Development

```bash
ruff check .
ruff format --check .
pytest -q
```

## License

MIT. Revisit before a commercial or source-available release if the product policy changes.

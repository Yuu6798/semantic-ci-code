# semantic-ci-code

Semantic CI Code Edition is a deterministic semantic CI layer for code changes.
It compares observed code semantics against a declared `target.yaml` intent and
returns stable JSON or human-readable repair guidance.

It is not a linter, type checker, test runner, or LLM-as-judge service.

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
semantic-ci pre-commit --target target.yaml
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

Active references (current behavior):

- [CLI Usage](docs/cli_usage.md) — all 8 subcommands, flags, target discovery, output formats, severity routing
- [Exit Codes](docs/exit_codes.md) — CI-facing exit code contract
- [JSON Output Schema](docs/json_schema.md) — verdict / compile envelopes (`schema_version="4"`) + compile-repair / validate-plan envelopes (independent `schema_version="1"`)
- [Code Semantic CI Design](docs/code_semantic_ci_design.md) — Code Edition v0.1 design spec (3-state RPE, constraint type system, phase plan)
- [CLI Test Inventory](docs/cli_test_inventory.md) — CLI test coverage map and reduction candidates
- [target.yaml Authoring Guide](docs/target_yaml_guide.md) — practical authoring guide; centralises hazards D1/D3/D4 (`--package-root` scope, template/user constraint duplication, config-only vacuous PASS)
- [Target Authoring Surface](docs/target_authoring_surface.md) — Authoring surface design contract (target.yaml generation paths, surface isolation, `candidate_code_used: false`)
- [AGENTS.md](AGENTS.md) — Claude × Codex task handoff protocol + Experience Externalization Discipline (§5)
- [SSP v0.1 Forward Design Note](docs/ssp_protocol_design_note.md) — Brief 7 implementer 用 一次資料 (Phase 4 で AGENTS.md inline から分離)
- [CLAUDE.md](CLAUDE.md) — repository-level agent operating policy

Planning (open):

- [Brief 7 — Semantic Security Protocol v0.1](docs/brief_7_planning.md) — SAST + SCA, Python only, independent envelope, Sensor Provenance Invariant
- [ResultStatus authoring/extraction split](docs/brief_resultstatus_planning.md) — C+B (compile-time pushback + `unknown_cause` sibling field), 5 PR split, validate-plan v2 — boundary with Brief 8 (Authoring Surface) pinned in §1b
- [Doc Refactoring Plan (urgent, 2026-05-21)](docs/doc_refactor_planning.md) — startup attention budget 2,500 → 800 lines compaction, Tier A/B/C/D 階層化, archive infrastructure, test-enforced rule conversion, 8 phase / 4-6 day scope

Reference / archived (completed briefs, retained for context — see [`docs/archive/README.md`](docs/archive/README.md)):

- [Brief 5 — Repair Compiler + Vibe Coding Adapters (P2.5 entry)](docs/archive/brief_5_planning.md) — CSCI-31〜35 merged 2026-05-07
- [Brief 4b — CI integration outputs (SARIF + GH Actions + pre-commit manifest)](docs/archive/brief_4b_planning.md) — CSCI-28 merged 2026-05-05
- [Brief 4 — CLI / operational entrypoint](docs/archive/brief_4_planning.md) — CSCI-15〜19 merged 2026-05-04
- [Brief 3 — Pipeline integration (judgment layer)](docs/archive/brief_3_planning.md) — CSCI-10〜14 merged

Out-of-core observation (case studies and dogfooding):

- [Dogfooding TC10 Report](docs/dogfooding_TC10_report.md) — 10 virtual-package cases through the CLI; tracks D5 / FINDING-1 (set operator partial-dict semantics, **unresolved**)
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

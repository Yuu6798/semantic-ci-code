# Dogfooding Findings Tracker

This document is the **single source of truth** for D-class findings (D#)
surfaced across dogfooding passes against `semantic-ci`. Each dogfooding
report (`docs/dogfooding_*.md`) records its own raw findings; this tracker
classifies them, deduplicates siblings, and pins resolution status.

Status taxonomy:

- **解決 (resolved)** — code fix landed (PR linked), or guide pin +
  `target-doctor` advisory detector both in place
- **未解決 (open)** — no mitigation; brief candidate
- **重複 / 関連 (sibling-class)** — distinct mechanism but same root pattern
  as another D#; cross-linked for context

## D# Registry

| D# | Source pass | Hazard class | Mechanism | Status | Resolution / Mitigation |
|---:|---|---|---|---|---|
| D1 | 2026-05-07 Session 4 dogfood | extractor scope coverage vs declared intent | `--package-root` excludes `tests/`, but test_surface constraint declared → vacuous empty observed | **解決** | `docs/target_yaml_guide.md` Hazard 1 + `ADVISORY-D1` detector (`authoring/hazards.py::detect_d1`) |
| D2 | 2026-05-07 Session 4 dogfood | extractor crash on malformed inputs | AST parse failure on `syntax_error/bad.py` aborted dimension extraction | **解決** | PR #67 (CSCI-35e) — `[tool.semantic_ci_code.extract] exclude` loaded from nearest `pyproject.toml` and applied before AST parse |
| D3 | 2026-05-07 Session 4 dogfood | template / user constraint duplication | user constraint shadows template default with identical semantics, doubles evidence | **解決** | `docs/target_yaml_guide.md` Hazard 2 + `ADVISORY-D3` detector |
| D4 | 2026-05-07 Session 4 dogfood | vacuous PASS (out-of-scope diff) | config-only PR produces empty Python `CodeStateDelta`; lock-only template constraints pass without exercising the actual change | **解決** | `docs/target_yaml_guide.md` Hazard 3 + `ADVISORY-D4` detector |
| D5 | 2026-05-07 Session 5 dogfood (FINDING-1) | set operator partial-match semantics | partial-dict `expected` items canonicalised as different elements from full extractor records — false positive on `includes_*` / `subset_of` / `superset_of`, **false negative (CI bypass) on `excludes_all`** | **解決** | PR #65 (CSCI-35c) — Match Schema partial-record matching + flat-projection aliases + `evidence.matched`; schema_version v4→v5 |
| D6 | 2026-05-28 real-PR complexity dogfood (FINDING-F1) | vacuous PASS (extractor coverage gap) — **重複・関連 = sibling of D4** | nested function bodies are excluded from `ComplexityEntry` by `python_complexity_extractor` spec (`api_surface` parity); refactor that nests outer-function body into nested helpers reports large CC drop while real complexity is unchanged | **未解決** | Candidate paths: (a) `docs/target_yaml_guide.md` new Hazard 4 + `ADVISORY-D6` detector mirroring D4; (b) extractor spec change to emit nested-function entries (long-term, schema-impacting). Reproduction: langgraph PR #3700 (8/1 vacuous PASS in real-PR pass) |
| D7 | 2026-05-28 real-PR complexity dogfood (FINDING-F2) | authoring mismatch (operator / constraint pairing) | `extract-method` refactor is mathematically guaranteed to **micro-increase cyclomatic** (each extracted function adds base 1), even with `_` prefix discipline and api_surface preserved. Cognitive is the metric that drops. Authors declaring `complexity_delta.cyclomatic ≤ 0` for extract-method refactors hit a structural false-FAIL | **未解決** | Candidate paths: (a) authoring guide section "Choosing complexity metric per refactor pattern" recommending `cognitive_delta` for extract-method; (b) future `ADVISORY-D7` detector emitted when a `change.primary_kind=refactor` target uses `cyclomatic_delta ≤ 0` and the diff matches extract-method shape. Low priority: this is authoring advice, not a CI integrity hazard |

## Reading order

| Question | Doc |
|---|---|
| What does D-N really do under the hood? | the originating dogfooding report (see `Source pass` column) |
| How do I avoid D-N in my `target.yaml`? | `docs/target_yaml_guide.md` (for resolved D# with guide pin) |
| Where is the open work for D-N tracked? | this file + `.claude/memory/STATUS.md` `次の発行順序` when an open D# is promoted to a brief |

## Classification at a glance

- **重複・関連 pairs**: D4 ↔ D6 (both are "vacuous PASS" via extractor coverage gap, distinct mechanism — D4 is "diff outside Python scope", D6 is "diff inside scope but inside nested function")
- **解決 (5 of 7)**: D1, D2, D3, D4, D5
- **未解決 (2 of 7)**: D6 (mitigation path open), D7 (authoring advice, low priority)

## Source pass index

| Pass | Date | Methodology | Cases | Doc | Findings → D# |
|---|---|---|---:|---|---|
| Session 4 self-dogfood | 2026-05-07 | self-dogfood on own PRs (#59, #60) + `init → compile_repair` 実走 | 3 | `.claude/memory/2026-05-07.md` §"dogfood 発見 D1〜D4" | D1, D2, D3, D4 |
| TC10 virtual report | 2026-05-07 Session 5 | hand-built virtual `baseline/` and `candidate/` package trees | 10 | `docs/dogfooding_TC10_report.md` | FINDING-1 → D5, FINDING-2 (resolved in PR #61), FINDING-3 (resolved in PR #61) |
| Real-PR complexity | 2026-05-28 | external public PRs + per-PR `target.yaml` under complexity constraints | 8 | `docs/dogfooding_real_pr_complexity.md` | F1 → D6, F2 → D7, F3 / F4 / F5 → observations only |
| **累計** | | | **21** | | D1〜D7 |

CASE STUDY 系の empirical 観察 (`docs/pre_generation_validation_case.md` 3
ケース、 `docs/multi_agent_audit_case.md` 3 並列 agent 比較) は dogfooding
pass とは別の core-scope-外応用観測として `CLAUDE.md` の Design Documents
table で CASE STUDY 区分に分類されており、 本累計には含めない。
新規 pass を追加する際は、 dogfooding (= semantic-ci 自身の self-test
or その verdict quality 測定) と case study (= 応用観測) の区別を維持し、
本表には dogfooding pass のみ追記すること。

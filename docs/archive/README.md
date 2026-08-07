# Archived Brief Planning Docs

This directory holds **completed brief planning documents**. They are kept
for downstream context (decision history, Open Questions resolution paths,
how Brief N's design constraints were derived) but are **no longer
authoritative** for current behavior.

For anything authoritative:

- Current spec / contract: see active docs in [`../`](..)
  (e.g. `code_semantic_ci_design.md`, `cli_usage.md`, `exit_codes.md`,
  `json_schema.md`).
- Live status / next-issue queue: see
  [`../../.claude/memory/STATUS.md`](../../.claude/memory/STATUS.md).
- Open / in-progress work: see the live queue in `STATUS.md`; completed
  planning records may remain in `docs/` when later phases still cite them.

## Contents

| Document | Status | Brief outcome |
|---|---|---|
| `brief_3_planning.md` | ARCHIVED | Brief 3 (pipeline 統合) — CSCI-10〜14 全 PR merged。当時の判断履歴として保存 (operator 5 個案などの一部記述は CSCI-12 brief で上書き済み) |
| `brief_4_planning.md` | REFERENCE (Brief 4 完走 2026-05-04) | Brief 4 (CLI / operational entrypoint) — CSCI-15〜19 全 PR merged で `semantic-ci` CLI 5 subcommand release 可能になった |
| `brief_4b_planning.md` | REFERENCE (Brief 4b 完走 2026-05-05) | Brief 4b (CI integration outputs) — CSCI-28 で SARIF 2.1.0 / GitHub Actions annotation / `.pre-commit-hooks.yaml` manifest を 1 PR で完結 |
| `brief_5_planning.md` | REFERENCE (Brief 5 完走 2026-05-07) | Brief 5 (Repair Compiler + Vibe Coding Adapters、P2.5 entry) — CSCI-31〜35 全 PR merged で `compile-repair` / `validate-plan` 2 subcommand + Claude Code / Cursor / Codex 3 adapter が release 可能 |
| `doc_refactor_planning.md` | ARCHIVED (completed 2026-05-21) | 起動時 context compaction、archive infrastructure、discipline test 変換を完了し、self-archive 条件を充足 |

## When to read these

- **Decision archaeology**: tracing why a particular operator / envelope /
  flag exists, especially when an Open Question in a later brief points
  back to a resolution recorded here.
- **Brief 7 (SSP v0.1) bootstrapping**: `brief_5_planning.md` is the
  closest structural precedent for Brief 7's CSCI-36〜40 split, and
  `brief_4b_planning.md` shows the CI-integration output pattern Brief 7
  will reuse.
- **Audit / handoff**: a new contributor or auditor reconstructing how the
  P1 → P2.5 sequence was carried out.

## When NOT to read these

- Looking up current CLI behavior (use `../cli_usage.md`).
- Looking up current envelope shape (use `../json_schema.md`).
- Looking up current next-action queue (use
  `../../.claude/memory/STATUS.md` 次の発行順序).

# AGENTS.md - Claude x Codex Handoff Protocol

This repository uses a design/implementation split. Claude Code owns design briefs
and review judgment. Codex owns implementation, tests, and PR preparation. The user
triggers handoff between them.

Both agents should read this file before starting repository work.

## Message Flow

```text
Claude -> Task Brief -> User -> Codex
Claude <- Completion Summary <- User <- PR URL <- Codex
```

Agents do not need to communicate directly. The user moves the structured messages
between them.

## 1. Task Brief: Claude to Codex

Claude should issue tasks in this format so the user can paste them directly into
Codex. Target task size is roughly 0.5 to 2 days.

````markdown
# Task Brief: <ID> - <short title>

## Phase
<design phase or document reference>

## Goal
<1-2 sentences defining completion>

## Acceptance Criteria
- [ ] Verifiable condition 1
- [ ] Verifiable condition 2

## Scope
- IN: <files or modules Codex may change>
- OUT: <files, behavior, or decisions Codex must not change>

## Allowed Dependencies (optional)
<Dependencies Codex may add to pyproject.toml. If absent, new dependencies require escalation.>

## Implementation Hints (optional)
<Suggested approach, design references, existing patterns>

## Required Outputs
- Branch name: `codex/<topic>`
- PR title: <Conventional Commits style>
- Expected files changed: <list>
- Required tests: <test expectations>

## Done When
- All acceptance criteria are checked
- `ruff check .` passes
- `pytest -q` passes
- PR body starts with a Completion Summary
````

## 2. Completion Summary: Codex to Claude

Codex should place this at the top of the PR body.

````markdown
# Completion Summary: <Task ID>

## Phase
<copied from Task Brief>

## What Changed
- <high-level change 1>
- <high-level change 2>
- <high-level change 3>

## Acceptance Criteria Status
- [x] Condition 1 - <evidence>
- [x] Condition 2 - <evidence>
- [ ] Condition 3 - <reason if incomplete>

## Tests
- Added: <test names or count>
- Result: <pass / fail / skipped>

## Dogfooding
- Status: performed | skipped
- Commands: <commands run, or short evidence>
- Result: <observed result>
- Reason: <required when skipped; omit when performed>

## Files Changed
<git diff --stat equivalent>

## Deviations from Brief
<None, or list deviations>

## Open Questions / Deferred
<Questions for Claude or next phase>

## Next Handoff
<What Claude should review next>
````

## 3. Escalation Rules

Codex should stop and report a blocked Completion Summary when:

1. Acceptance criteria are technically impossible.
2. The brief requires an unstated design decision.
3. Existing tests fail in a way that suggests a behavior regression.
4. A new dependency is needed but not listed in Allowed Dependencies.
5. The implementation would violate determinism, auditability, no-LLM operation, or
   no-API-key operation.

## 4. Branch Rules

- Claude design branches: `claude/<topic>`
- Codex implementation branches: `codex/<topic>`
- Direct changes on `main` are reserved for explicit user-approved exceptions.

## 5. Experience Externalization Discipline (経験値の外部化規律)

Required reading **before drafting any new Task Brief** or **introducing
a new architectural pattern**. Codifies the operating principle from
2026-04 〜 2026-05 累計 28 sessions / 39 merged PRs. Compacted by
`docs/doc_refactor_planning.md` Phase 3 (was 209 lines, now ~88; ≤ 80 target
の残 cosmetic と §5.3 merge は Phase 3 の唯一の未了項目)。

### 5.1 Principle

AI 開発は session 跨ぎの暗黙知を継承しない (Claude = no long-term memory、
Codex = PR 単位 review trail のみ、 user 壁打ち経験 = session 跨ぎで消失)。
再現性維持の唯一の方法は経験値を **明示 artifact** (docs / tests /
checklists / pattern catalog) に強制外部化すること。 「ベテランの感」 個人
閉じ込めは AI 開発では機能しない。 Claude が forget する制約が逆説的に
**強制的 externalization discipline** として働く。

### 5.2 Empirical Envelope

| PR | 体制 | Rounds | 規模 | Notes |
|---|---|---|---|---|
| #82 (CSCI-43) | split | **16** | 1 日 | advisory boundary chase |
| #84 (CSCI-42) | Claude exception | **13** | 1 日 | producer shape 暗黙追従 |
| #85 (canonical refactor) | Claude alone | 0 | 半日 | scope 制限下で self-review 機能 |
| #86 (CSCI-44) | split | 0 | 1 日 | INV-5 cross-test + brief 規律 |
| #87 (R17) | split | 0 | 半日 | brief hint 逐語 + bonus test |

体制別 envelope: **split** = 1 日 brief で 0 round 可、 **Claude alone** =
半日以下なら 0 round 可、 **Claude exception** = 半日以下に narrow 必須
(1 日規模を押し込むと PR #84 の 13 round chase)。 Codex 不在時は brief
paste 待ちで Codex 復帰を待つ方が trade-off 上有利。

#82 + #84 累計 29 round の P2 を `tests/authoring/test_canonical.py` 48
cases + `tests/architecture/` 16 tests + `docs/brief_8_planning.md §15`
checklist に encode した結果、 後続 PR #86 / #87 が 0 round で landing
した因果が **本 framework の empirical base case**。

### 5.3 Three-Tier Externalization (artifact type)

| Tier | Type | 主要 artifact |
|---|---|---|
| 1 (codified) | 別 repo 持ち運び可 | `CLAUDE.md` / `AGENTS.md` / `tests/architecture/` invariants / brief §15 checklist / AskUserQuestion N 択 pattern |
| 2 (repo-specific) | 同 domain で再利用可 | `docs/brief_*_planning.md` / authoring guides / `tests/authoring/test_canonical.py` / case studies |
| 3 (session-tacit) | memory 読み返しで部分継承 | `.claude/memory/STATUS.md` / `_index.md` / dated `YYYY-MM-DD.md` |

CLAUDE.md `Required Reading` の Tier A/B/C/D は **読み込み load 優先度**
(直交軸)。 artifact type と読み込み tier は parallel concept として併用。

### 5.4 Review Round Count as Leading Quality Indicator

| Round | 解釈 | Action |
|---|---|---|
| **0** | brief 規律機能、 inviolate predicate 明示、 producer shape grep 済 | なし (base case) |
| **1〜3** | 軽い follow-up、 specific point の補強 | round 内完了で acceptable |
| **5〜10** | brief 内で曖昧だった spec section 表面化 | 該当 spec を docs/test に encode 必須 |
| **10+** | brief 起草段階で §15 skip / inviolate predicate 不在 / producer shape 未確認 | 「同じ trap 二度発生させない」 encoding work を follow-up commit / next brief で必ず実施 |

Round 0 連続は **規律が壊れない限り** 維持される envelope。 §5.5 の
maintenance practice を遵守しないと PR #84 の状態に戻る。

### 5.5 Practice + Anti-Pattern + Enforcement (combined)

各 rule は **肯定形 (Practice)** / **反例 (Anti-Pattern)** / **enforce 経路**
の 3 軸で読む。 enforce 経路の `tests/discipline/` test は
`docs/doc_refactor_planning.md` Phase 6 (完走) で出揃った。

| Practice | Anti-Pattern | Enforcement |
|---|---|---|
| brief 起草前に memory log + 直近 3 dated entries 読む | memory log skip → 過去 session trap 再発生 | `CLAUDE.md` § Required Reading (Tier A) |
| §15.1 Schema grounding (producer 出力 shape grep 後 validator) | 思い込みで validator 書く → `Class::method` 受理忘れ系 trap | `docs/brief_8_planning.md §15.1` + `tests/discipline/test_json_schema_version_sync.py` |
| §15 checklist 全項目 (規模に関係なく) | 「短い brief だから」 で §15 skip | `docs/brief_8_planning.md §15` (8 sub-checklist) |
| 新 module 追加時に architecture test の prefix match cover を確認 | prefix match → 個別 enumeration に regress / prefix を緩める | `tests/architecture/test_surface_isolation.py` |
| dogfood で fail case + pass case 両方を実演 | pass case 1 件のみで「動いた」 → no-op gate 検出不能 | `tests/discipline/test_dogfood_dual_case.py` |
| AskUserQuestion で trade-off 軸 3-4 択提示 | 単純な yes/no 問い → user 判断遅延 | (pattern catalog、 PR #84 R10 / #85 / 5/21 で再現性確認) |
| Codex 不在時の Claude exception scope ≤ 半日 | 1 日規模を Claude 単独押し込み → 13+ round chase | (体制 envelope §5.2、 PR #84 vs #85 の境界) |
| review 5+ round → PR merge 後に「曖昧だった spec」 を docs/test に encode | round 内修正のみで完了 → trail が memory log だけに残り再参照されない | `CLAUDE.md` 終了時ルール step 7 wrap-up checklist (round-count は test 化せず retire: prose proxy が脆く「encode 忘れ」 case を検出不能) |
| PR merge 直後に STATUS.md `次の発行順序` を sweep (完走 entry 削除) | 「後で」 と先送り → stale entry 蓄積 (5/21 で ADVISORY-S1 + R17 で 2 連続発生) | `tests/discipline/test_status_md_next_queue_no_completed.py` |
| STATUS.md `## Phase` は 1 paragraph 厳守 | 新 paragraph 追加 + 旧 paragraph 残置 (5/21 で Codex も再発) | `tests/discipline/test_status_md_phase_single_paragraph.py` |
| `_index.md` 各 entry の cell ≤ 500 chars | essay cell に膨張 (Phase 2 で 53KB → 5KB 復元の前例) | `tests/discipline/test_index_md_entry_compactness.py` |

### 5.6 Cross-Reference

- `CLAUDE.md` § Experience Externalization (本 section への light pointer)
  + § Required Reading (Tier A/B/C/D)
- `docs/brief_8_planning.md §15` (brief drafting checklist、 20 round 蒸留)
- `docs/multi_agent_audit_case.md` (parallel agent 規律不在時の failure mode)
- `docs/doc_refactor_planning.md` (本 framework 自己 refactor の dogfood
  example、 Phase 6 完走で本 §5.5 Anti-Pattern を `tests/discipline/` に変換済)

## Forward Design Note: Brief 7 / SSP v0.1 (CSCI-36 着手時必読)

Brief 7 (Semantic Security Protocol v0.1) の設計申し送り (11 項目 + Brief
5 からの学び 3 項目 + 設計 AI への推奨判断) は本 doc 内 inline から分離
され、 専用 doc に移送された:

→ **[`docs/ssp_protocol_design_note.md`](docs/ssp_protocol_design_note.md)** —
canonical 一次資料、 CSCI-36 Task Brief 起草・実装時の逐語参照対象。

分離経緯: `docs/doc_refactor_planning.md` Phase 4 (2026-05-21 Session 2)、
AGENTS.md の handoff protocol body から ~220 lines の brief-specific
context を別 doc に move out して Tier B 読み込み load を narrow した。
旧 inline 版と等価な content を保持、 内部 section 番号も保持済。

## Related Documents

- `CLAUDE.md` - repository policy and workflow summary
- `docs/code_semantic_ci_design.md` - product design specification

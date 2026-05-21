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
`docs/doc_refactor_planning.md` Phase 3 (was 209 lines, now ≤ 80).

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
の 3 軸で読む。 enforce 経路が 「(Phase 6)」 のものは
`docs/doc_refactor_planning.md` Phase 6 で `tests/discipline/` に test 化
予定。

| Practice | Anti-Pattern | Enforcement |
|---|---|---|
| brief 起草前に memory log + 直近 3 dated entries 読む | memory log skip → 過去 session trap 再発生 | `CLAUDE.md` § Required Reading (Tier A) |
| §15.1 Schema grounding (producer 出力 shape grep 後 validator) | 思い込みで validator 書く → `Class::method` 受理忘れ系 trap | `docs/brief_8_planning.md §15.1` + (Phase 6: schema-grep check) |
| §15 checklist 全項目 (規模に関係なく) | 「短い brief だから」 で §15 skip | `docs/brief_8_planning.md §15` (8 sub-checklist) |
| 新 module 追加時に architecture test の prefix match cover を確認 | prefix match → 個別 enumeration に regress / prefix を緩める | `tests/architecture/test_surface_isolation.py` |
| dogfood で fail case + pass case 両方を実演 | pass case 1 件のみで「動いた」 → no-op gate 検出不能 | (Phase 6: dual-case dogfood check) |
| AskUserQuestion で trade-off 軸 3-4 択提示 | 単純な yes/no 問い → user 判断遅延 | (pattern catalog、 PR #84 R10 / #85 / 5/21 で再現性確認) |
| Codex 不在時の Claude exception scope ≤ 半日 | 1 日規模を Claude 単独押し込み → 13+ round chase | (体制 envelope §5.2、 PR #84 vs #85 の境界) |
| review 5+ round → PR merge 後に「曖昧だった spec」 を docs/test に encode | round 内修正のみで完了 → trail が memory log だけに残り再参照されない | (Phase 6: round-count-to-encoding check) |
| PR merge 直後に STATUS.md `次の発行順序` を sweep (完走 entry 削除) | 「後で」 と先送り → stale entry 蓄積 (5/21 で ADVISORY-S1 + R17 で 2 連続発生) | `CLAUDE.md` rule (Required Reading) + (Phase 6: status-drift check) |

### 5.6 Cross-Reference

- `CLAUDE.md` § Experience Externalization (本 section への light pointer)
  + § Required Reading (Tier A/B/C/D)
- `docs/brief_8_planning.md §15` (brief drafting checklist、 20 round 蒸留)
- `docs/multi_agent_audit_case.md` (parallel agent 規律不在時の failure mode)
- `docs/doc_refactor_planning.md` (本 framework 自己 refactor の dogfood
  example、 Phase 6 で本 §5.5 Anti-Pattern を `tests/discipline/` に変換)

## Forward Design Note: Brief 7 / SSP v0.1 (CSCI-36 着手時必読)

以下は session 2026-05-07 で user から提供された Brief 7 (Semantic Security Protocol v0.1) の
設計申し送り。CSCI-36 Task Brief を起草・実装する際に **逐語で参照すること**。
`docs/brief_7_planning.md` は planning であり spec ではない(申し送り #1, #2 を参照)。
このセクションは Claude × user の合意により main 直 commit で永続化(通常の `.claude/memory/`
例外運用と同等の扱い)。

### 現状認識

Brief 5 までで semantic-ci core / Repair Compiler / Adapter CLI は一通り完走した。
semantic-ci は「意図 target.yaml と実コード delta の整合性を見る core」と、「判定結果を AI 開発ツールに渡す adapter layer」まで到達している。

Brief 7 はここからの **隣接 protocol 拡張**であり、semantic-ci core に SAST/SCA を混ぜる話ではない。
SSP は security sensor の finding delta を扱う別 protocol として設計する。

### 最重要方針

SSP は semantic-ci core を太らせない。

```text
semantic-ci core  = intent / delta adherence
Repair Compiler   = AI 開発ツールへの guidance rendering
SSP               = security sensor delta protocol
suite/action      = core + SSP を束ねる運用層
```

core verdict envelope と SSP envelope は分離すること。
統合表示や総合 gate は suite/action layer の責務に送る。

### 未解決・注意点

#### 1. docs/brief_7_planning.md の文字化け

ローカル表示で `docs/brief_7_planning.md` がかなり文字化けしている。
CSCI-36 ではまず、人間がレビュー可能な UTF-8 の `docs/ssp_protocol.md` として清書すること。
planning doc をそのまま spec として扱わない。

(注: 2026-05-07 verify では file content 自体は valid UTF-8。表示破損は local terminal /
editor encoding 起因。それでも spec / planning の分離方針は採用する。)

#### 2. CSCI-36 は docs/spec only 推奨

いきなり SemgrepAdapter / pip-audit 実装に入らない。
まず SSP v0.1 spec を固定する。

CSCI-36 の主成果物:
- `docs/ssp_protocol.md`
- SSP scope / non-goals
- SensorOutput / Finding / SSPDelta / SSPVerdict 定義
- Sensor Provenance Invariant
- fingerprint spec
- envelope schema
- determinism requirements
- SARIF との関係
- versioning policy

#### 3. Sensor Provenance Invariant を最優先で固定

SSP engine は `SensorOutput` の出自を問わない。

```text
real scan
staged content
virtual fixture
hand-built contract test
```

これらを同じ `SensorOutput` として扱うこと。
これは semantic-ci core の「CodeState 出自不問」と同じ思想。
ここを壊すと SSP がただの CLI wrapper になる。

#### 4. fingerprint 設計が最大リスク

Semgrep の line-based fingerprint や OSS `extra.fingerprint` に依存しないこと。

SAST fingerprint は少なくとも以下を含める方針:
- `rule_id`
- `module_path`
- `qualified_name`
- `normalized_text`
- `ordinal_index_within_scope`

delimiter join ではなく canonical JSON array を SHA-256 する。
`:` join は collision risk があるため避ける。

未解決:
- `ordinal_index_within_scope` の安定性
- `normalized_text` の AST unparse 方針
- module-level / lambda / nested function の qualified_name 規則
- finding が同一 normalized_text で複数出る場合の扱い

#### 5. SSP scope は SAST + SCA に限定

Brief 7 v0.1 では以下に絞る。

```text
SAST: SemgrepAdapter
SCA: pip-audit Adapter
```

入れないもの:
- secrets scanning
- IaC scanning
- CodeQL
- Bandit
- GitHub Marketplace publication
- TypeScript / npm
- SARIF first の設計
- core CodeState への Semgrep finding 統合

scope creep を避けること。

#### 6. SSP envelope は独立 schema

verdict envelope / compile envelope / validate-plan envelope とは別。
例:

```json
{
  "schema_version": "ssp-1",
  "engine": {
    "ssp_version": "0.1",
    "scan_mode": "real|staged|virtual|hybrid",
    "baseline": {},
    "candidate": {},
    "sensors": []
  },
  "deltas_by_sensor": {},
  "aggregate_verdict": "pass|fail|unknown"
}
```

`semantic-ci check` の JSON schema を bump して SSP を混ぜない。

#### 7. SARIF は出力先であって内部形式ではない

SSP 内部形式を SARIF に寄せすぎない。
SARIF は GitHub Code Scanning / external tooling 向けの変換先。
`ssp-to-sarif` は CSCI-40 以降でよい。

#### 8. adapter 実装前に unknown/error semantics を決める

Semgrep / pip-audit 実行では失敗パターンが多い。

決めるべきこと:
- Semgrep exit code `0/1` は正常 scan
- JSON parse failure
- timeout
- SIGTERM
- ruleset unavailable
- scanned path mismatch
- advisory DB unavailable
- pip-audit network dependency

これらを engine error にするのか、SSP `unknown` にするのかを spec で固定すること。
semantic-ci 的には、sensor failure は多くの場合 `unknown` として envelope に出す方がよい。

#### 9. deterministic audit を spec に入れる

少なくとも以下を回帰テスト化する設計にする。

- 同一 input で byte-identical
- `PYTHONHASHSEED` 差で byte-identical
- path separator 差の正規化
- Semgrep `--jobs` 差で同一
- ruleset id rewrite 無効化
- metrics / version check disabled
- line number 変動で fingerprint が過剰に揺れない
- sensor failure が deterministic に unknown へ落ちる

#### 10. CLI surface は後段

`semantic-ci ssp ...` は CSCI-40 あたりでよい。
CSCI-36/37 では model / spec / pure delta engine を先に作る。
CLI 先行にすると protocol が固まる前に UX に引っ張られる。

推奨順:

```text
CSCI-36: docs/ssp_protocol.md v0.1
CSCI-37: Pydantic models + delta engine
CSCI-38: SemgrepAdapter
CSCI-39: pip-audit Adapter
CSCI-40: semantic-ci ssp CLI + SARIF bridge
```

### Brief 5 からの学びとして反映すべきこと

#### target/scope 設計の教訓

semantic-ci core では `tests/cli` を package root にすると helper 移動が API change になった。
SSP でも scan scope を曖昧にすると、想定外の finding delta が出る。
SSP spec でも scan root / include / exclude / repo-relative path normalization を明確化すること。

#### adapter layer の教訓

Repair Compiler で adapter ごとの表現差が semantic drift を露出した。
SSP でも JSON / SARIF / GH annotation / human output の間で意味がズレないよう、内部 envelope を先に固定すること。

#### includes_any 問題の教訓

`includes_any` を required item として flatten すると、AI が「全部必要」と誤解した。
SSP でも「alternative」「required」「advisory」「unknown」を混同しないこと。
security finding の severity / confidence / reachability / fixability を単純 flatten しない。

### 設計AIへの推奨判断

Brief 7 は進めてよい。
ただし「semantic-ci にセキュリティ機能を足す」と表現しない方がよい。

正しい framing:

```text
Semantic Security Protocol (SSP) is a sibling protocol for deterministic
security sensor deltas. It does not change semantic-ci core verdict semantics.
```

CSCI-36 は implementation ではなく spec 固定に徹すること。
ここで scope / fingerprint / provenance / unknown semantics を固めるのが最重要。

## Related Documents

- `CLAUDE.md` - repository policy and workflow summary
- `docs/code_semantic_ci_design.md` - product design specification

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

This section codifies the operating principle that emerged from
2026-04 〜 2026-05 累計 28 sessions / 39 merged PRs. It is required
reading **before drafting any new Task Brief** or **introducing a new
architectural pattern**. The principle is referenced (lightly) from
`CLAUDE.md` § Experience Externalization; this section is the canonical
detailed form.

### 5.1 Principle

AI 開発 (Claude design + Codex implementation + 並列 agent 運用) は
session 跨ぎの暗黙知を継承しない:

- **Claude** は long-term memory を持たない。 各 session は clean state
  から始まり、 過去の判断履歴は memory log を読み返さない限り消失する
- **Codex** は PR 単位の review trail 以外を学習しない。 別 PR で同じ
  trap を再発生させる可能性が常にある
- **user** の壁打ち経験は session 跨ぎで永続化されない限り消失する。
  「以前こうだったよね」 が agent 側に通じない

この制約下で再現性を維持する唯一の方法は、 経験値を **明示 artifact** に
強制的に外部化することである: docs / tests / checklists / pattern catalog
のいずれかに encode することで、 次の session / 次の PR / 次の brief で
**構造的に reusable** な状態にする。 単に「ベテランの感」 として個人 /
agent に閉じる形は **AI 開発では機能しない**。

逆説的に、 Claude が forget する制約が **強制的な externalization
discipline** として働く。 これは普通の dev における「暗黙知の個人内累積」
を、 構造的に外部化された discipline 規律へ転換する mechanism。

### 5.2 Empirical Envelope

Review round 数の急減は経験値が外部化された結果として実測される。 本
リポジトリの直近の data point:

| PR | 体制 | Codex bot review rounds | Notes |
|---|---|---|---|
| #82 (CSCI-43 / target-doctor) | Claude=design / Codex=impl | **16** | advisory boundary 16 round chase |
| #84 (CSCI-42 / init --recipe) | Claude exception (両方担当) | **13** | producer 出力 shape 暗黙追従 |
| #85 (canonical refactor) | Claude alone (small scope) | 0 | scope 半日、 self-review 機能 |
| #86 (CSCI-44 / target-catalog) | Claude=design / Codex=impl | 0 | INV-5 cross-test + brief 規律 |
| #87 (R17 / package-root parity) | Claude=design / Codex=impl | 0 | brief hint 逐語適用 + bonus test |

#82 + #84 の累計 29 round で表面化した P2 を **producer-spec contract
test (`tests/authoring/test_canonical.py` 48 cases) + architecture
invariant test (`tests/architecture/` 16 tests) + brief drafting
checklist (`docs/brief_8_planning.md §15` 8 sub-section)** に encode した
結果、 後続 PR #86 / #87 が 0 round で landing した。 同じ trap は二度
発生しない構造を作るのが目的。

### 5.3 Three-Tier Externalization

蓄積される経験値は 3 階層に分類して扱う。 階層が下がるほど repo / project
の固有性が強くなり、 transferability が下がる。

**Tier 1 — Codified / fully transferable**

別 repo / 別 project に物理的に持ち運べる artifact:

- `CLAUDE.md` policy doc (session 跨ぎの operating contract)
- `AGENTS.md` handoff protocol (本 doc) + Forward Design Note 群
- `tests/architecture/` invariant test pattern (INV-1〜INV-5、 prefix
  match で新 module を自動 cover する設計)
- Brief drafting checklist (`docs/brief_8_planning.md §15` の 8
  sub-section、 20 round 蒸留)
- AskUserQuestion N 択 trade-off 軸提示 pattern
- dogfood で fail + pass 両方実演する pattern
- §15.1 Schema grounding (実 schema を grep してから brief を書く規律)

**Tier 2 — Repo-specific / partially transferable**

同じ engine 仕様 / domain に依存する artifact:

- `docs/brief_*_planning.md` (planning archeology、 6 brief 分の判断履歴)
- `docs/target_yaml_guide.md` / `docs/target_authoring_surface.md`
  (authoring hazards / surface contract)
- `tests/authoring/test_canonical.py` (producer-spec contract、 12 種類の
  near-miss shape を 48 parametrize cases に encode)
- `src/semantic_ci_code/authoring/canonical.py` module docstring
  (producer references を集約する単一 source of truth)
- `src/semantic_ci_code/authoring/catalog.py` (4 registry mirror による
  INV-5 自動 drift detection、 hard-code ゼロ)
- `docs/multi_agent_audit_case.md` / `pre_generation_validation_case.md` /
  `dogfooding_TC10_report.md` (observation case study)

**Tier 3 — Session-tacit / 継承経路あり**

個別の対話履歴 / 判断 touch / trade-off sense。 物理的には永続化される
が、 利用には memory 読み返しが必要:

- `.claude/memory/STATUS.md` live tracker (current phase + 直近 merged +
  次の発行順序、 28 session 跨ぎで更新)
- `.claude/memory/_index.md` 1-line index (各 session の要約)
- `.claude/memory/YYYY-MM-DD.md` dated entries (full session log、 28
  entries)
- 各 PR の commit message + review trail (GitHub 側に残置)

Claude が次 session で memory を読み返すことで部分継承される。 「forget
するから外部化が強制される」 という制約が逆に discipline 強制に働く。

### 5.4 Review Round Count as Leading Quality Indicator

Codex bot review の round 数は **brief 起草段階の品質を後追いで測る
indicator** として運用する:

| Round 数 | 解釈 | 必要 action |
|---|---|---|
| **0** | brief 規律が機能、 inviolate predicate が明示化、 producer 出力 shape が grep 済 | なし。 base case |
| **1〜3** | 軽い follow-up、 brief 内の specific point が補強される程度 | acceptable、 round 内で完了 |
| **5〜10** | brief 内で曖昧だった spec section が表面化 | round 終了後に対応する spec を docs / test に encode 必須 |
| **10+** | brief 起草段階で §15 checklist スキップ / inviolate predicate 不在 / producer 出力 shape 未確認 | PR merge は可だが、 **「同じ trap を二度発生させない」 ための encoding work** を follow-up commit / next brief で必ず実施 |

PR #82 / #84 の 16 + 13 round = 29 round 累計を `tests/authoring/
test_canonical.py` 48 cases + `tests/architecture/` 16 tests に encode
した結果、 PR #86 / #87 が 0 round に到達した因果関係を base case とする。

逆方向の解釈: **round 0 の連続は brief 規律が機能している証拠**。 ただし
これは **規律が壊れない限り** 維持される envelope であり、 何もしないで
維持されるわけではない (§5.6 maintenance practice 参照)。

### 5.5 体制別 envelope (split / Claude alone / Claude exception)

同じ「経験値の外部化」 規律下でも、 体制によって round 数の expected
envelope が変わる:

- **split 運用 (Claude=design / Codex=impl)**: 1 日規模 brief を 0 round
  で landing 可能 (PR #86 / #87)。 self-review blind spot が agent 跨ぎで
  分散、 brief 起草と実装の専門性が分業
- **Claude alone (small scope)**: 半日以下の scope なら 0 round 可能
  (PR #85)。 self-review が scope 制限下で機能、 規律 infrastructure を
  **先に書く** ことで自分自身を audit する loop が成立
- **Claude exception (両方担当、 1 日規模)**: 規律負債を累積させる例外
  運用 (PR #84 で 13 round 実証)。 Codex 不在時の continuity 維持として
  一時的に有効、 ただし scope を半日以下に narrow すべき

実用 rule: Codex 不在時に 1 日規模 brief を Claude exception で押し込む
よりも、 **brief paste 待ち状態を維持して Codex 復帰を待つ** 方が trade-off
として優位 (PR #84 vs PR #86 で実証された round 数の差が根拠)。

### 5.6 Maintenance Practice (規律を壊さない)

経験値外部化の運用 rule:

1. **Codex review で 5+ round が発生したら、 PR merge 後に必ず**
   「何が brief 内で曖昧だったか」 を抽出して docs / test に encode する
   follow-up commit を起こす。 round trail を memory log だけに残すのは
   不十分 (memory log は session 跨ぎ context 用で、 brief 起草時に
   逐語参照されにくい)
2. **新 module を追加するときは、 architecture test の prefix match に
   含まれるかを最初に確認する**。 `AUTHORING_FORBIDDEN_FOR_VERDICT_PATH`
   等の prefix match は新 module を **自動 cover** する設計で、
   enumeration 追加なしで INV-2 / INV-4 が効く。 これを壊す変更
   (個別 module 列挙に変える / prefix match を緩める) は accumulated
   discipline を破壊する
3. **producer 出力 shape を grep してから validator / consumer を書く**
   (§15.1 Schema grounding を再 grep する)。 思い込みで書くと
   `Class::method` 受理忘れ系の trap が再発生する (PR #84 R5 で実証)
4. **dogfood は fail + pass 両方を実演する**。 single-case dogfood は
   no-op gate (D5 FINDING-1 と同 trap) を検出できない。 PR #85 / #86 で
   pattern 確立済
5. **AskUserQuestion で trade-off 軸を 3-4 択提示する**。 単純な
   「続けるか?」 より「規模 × 例外運用 × 依存関係」 のような軸を明示
   する方が user 判断が早い。 PR #84 round 10 で初実証、 PR #85 / 5/21
   で再現性確認
6. **Codex 不在時の Claude exception 運用は scope を半日以下に限る**
   (PR #85 の成立条件)。 1 日規模を Claude 単独で押し込むと 13+ round
   chase になる (PR #84 で実証)。 1 日規模なら paste 待ち状態を維持
7. **brief 起草前に `.claude/memory/STATUS.md` + 直近 3 件の dated
   entries を必ず読む**。 memory rule (CLAUDE.md § Required Reading
   Before Editing) は厳守。 memory skip は recurring failure mode

### 5.7 Anti-Patterns (accumulated discipline を壊す行為)

以下は実証済の failure mode。 brief 起草 / review / implementation の
いずれの phase でも回避する:

- **memory log を skip して新 brief を起こす** — 過去 session の trap を
  見落として再発生させる。 28 session 累計の判断履歴が消失する
- **brief の §15 checklist を「短い brief だから不要」 と skip する** —
  brief の規模に関係なく、 schema grounding / producer 出力 shape の
  確認は必須。 1 行 brief でも実 schema は grep する
- **architecture invariant test の prefix match を個別 enumeration に
  「明示的にしたい」 という理由で変える** — automatic cover を壊し、
  新 module 追加時に手動更新を要求する状態に regress させる
- **review round が長引いたときに、 round 内の修正のみで完了とする** —
  round trail を docs / test に encode しないと再発生。 PR merge 直後の
  follow-up が必須
- **dogfood を pass case 1 件だけで「動いた」 とする** — no-op gate を
  検出できない。 fail case (期待通り fail する) + pass case (期待通り
  pass する) の **両方** が必要
- **CSCI 単位の brief で「`tests/architecture/` test 不要」 と判断する** —
  新 module 追加が伴うなら必ず INV-2 / INV-4 prefix match の coverage を
  確認、 必要なら enumeration を update する
- **STATUS.md の `次の発行順序` 更新を「後で」 と先送りする** — CLAUDE.md
  rule で「If a CSCI is closed, **remove the corresponding entry from
  次の発行順序**」 が明示。 PR merge 時の memory hygiene 必須事項

### 5.8 Cross-Reference

- `CLAUDE.md` § Experience Externalization (light pointer to this section)
- `CLAUDE.md` § Required Reading Before Editing (memory log の優先度)
- `CLAUDE.md` § Session Memory (永続記憶ワークフロー)
- `docs/brief_8_planning.md §15` (brief drafting checklist 8
  sub-section、 20 round 蒸留)
- `docs/multi_agent_audit_case.md` (parallel agent blind spot 観測事例、
  本 discipline の **裏面** = 規律不在時の failure mode)
- `.claude/memory/STATUS.md` (live tracker、 累計 28 session 跨ぎ context)
- 各 dated session log (`.claude/memory/YYYY-MM-DD.md`) — Tier 3
  session-tacit knowledge の継承経路

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

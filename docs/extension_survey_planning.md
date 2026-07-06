# Extension Survey & Task Planning — post-D-class-closure roadmap

Status: **PLANNING (open)**。起草 2026-07-06。

本 doc は D-class closure 完了 (8/8、2026-06-12) 後の repo-internal 拡張
roadmap である。作成体制は `docs/model_delegation_policy.md` 本ルートの
初適用: **調査 (capability inventory + extension-seam survey) は Sonnet
実行担当 2 並列に委譲**し、Fable は distilled summary のみを受けて設計
判定・優先度付け・task planning を行った。

個々のタスクの brief 発行時は `/new-brief` skill (§15 checklist gate) を
必ず通すこと。本 doc の各タスク定義は brief の**種**であって brief 本体
ではない (§15.1 schema grounding は brief 起草時に実施する)。

## 0. 判定軸

各拡張候補を 4 軸で判定する:

1. **Product value** — verdict の信頼性 / CI 統合価値 / authoring 安全性
   への寄与
2. **Effort** — `AGENTS.md §5.2` 体制 envelope 基準 (split = 1 日 brief で
   0 round が上限目安、超えるなら分割)
3. **Scope-guard / §23.1 risk** — 決定論・input neutrality・「not an
   LLM-as-judge / not an intent validator」への抵触有無
4. **依存 / 順序** — 既存 queue (STATUS.md 次の発行順序、特に E-3 =
   Phase X-2 pilot) との関係

## 1. 洗い出し結果 (survey summary)

### 1.1 実装済み表面 (2026-07-06 時点)

- CLI 10 subcommand (`ssp` は 2 sub の group)、exit code 0-4、envelope:
  verdict/compile=`"6"` / compile-repair=`"1"` / validate-plan=`"2"` /
  doctor=`advisory-2` / catalog=`catalog-1` / ssp=`ssp-1`
- Operator 17 種 (pure 12 + baseline 系 7 の分類、`changed_only_in` は
  parse のみ P1 未対応)、compile-time operator/path schema 検証 +
  did-you-mean
- Extractor 6 種: api_surface / complexity / effects / imports /
  module_graph / test_surface
- Repair: `R_*` 15 code + 3 adapter (claude-code / cursor / codex)
- SSP + sensor 層: semgrep / pip-audit adapter、LLM scout (fixture ingest
  + `llm-ensemble` 集約 + advisory mute)、suite evaluator + Suppression
- Authoring: init recipe 7 種、target-catalog、target-doctor advisory 9 種
  (D1/D3/D4/D6/D7/I1/P1/P2/S1)、canonical shape 共有
- Test 118 file (architecture 10 / discipline 8 で invariant enforce)、
  inline TODO/FIXME ゼロ

### 1.2 Survey findings (S1〜S8: 非対称・stale)

| ID | Finding | 出所 |
|---|---|---|
| **S1** | `CodeState.type_relations` / `control_flow` / `data_flow` / `coverage` は schema・evaluator・delta に存在するが **extractor 未実装** — 実抽出経路では常に空。constraint は書けてしまう | `domain/state_schema.py` vs `pipeline/python_code_state.py` |
| **S2** | format 非対称: `compile-repair` / `validate-plan` は text/json のみ (sarif / gh-actions なし)、`ssp` は gh-actions なし | `cli/main.py` |
| **S3** | `compare` に sensor / suite security 経路なし (`check` のみ配線) | `cli/main.py` |
| **S4** | suppression 二重機構: advisory mute (`sensor/mutes.py`) と verdict 側 `Suppression` (`framework/security_policy.py`) が別層・非統一 | 同左 |
| **S5** | `init --recipe` 7 種 < catalog の全 template/operator 表面 | `authoring/` |
| **S6** | `ROADMAP.md` の D-class 行が **stale** (「5 of 7 resolved; D6/D7 open」のまま。実際は 8/8 解決 2026-06-12) | ROADMAP.md |
| **S7** | `docs/doc_refactor_planning.md` の self-archive 最終 step 未了 (Phase 0-6 完了済みなのに doc が `docs/` に残存、表 status も PLANNING のまま) | 同 doc §7 |
| **S8** | planning doc の open questions に解決の追記がない (phase_g Q1-Q5 / brief_7 R1・R4・R5 / source_selection §10 再評価 / resultstatus §1b.3) — 実装は着地済みでも doc 上 open に見える | 各 planning doc |

### 1.3 設計 doc 由来の deferred / frozen (再確認)

P2 repair core 完備 (effect_db L2/3、partial CFG/data-flow、repair_order、
reduce/defer/lock) / §19 spec quality metrics / §20 suite packaging +
GH Action / §10.3 round-trip log / override 機構 (Brief 3 #3) / §21.3
HTTP adapter 群 / §21.5 LSP / §22 多言語 / §23.2 retrospective audit・
nightly scan / Brief 6 TypeScript (凍結) / D2-3 pytest-xdist /
orchestrator 観測応用 / F6 (SAST 盲点、untested hypothesis)。

## 2. 設計判定 (Fable verdict)

### 2.1 採用 — 即実行可 (Wave 1: hygiene)

判定: 全て docs / 小粒 code。リスクゼロ、放置コストが survey で顕在化
(S6 は外部から見える stale)。E-3 と完全並走可能。

### 2.2 採用 — 設計ピン付きで委譲可 (Wave 2: 非対称解消)

- **S1 → ghost-facet authoring hazard** が本 survey の最重要 finding。
  extractor 未実装 facet への constraint は実抽出経路で恒久 vacuous
  PASS / 恒久 FAIL / UNKNOWN のいずれかに退化する — **D4 の一般化**。
  設計ピン: hand-built CodeState 経路 (§23.1) では正当な使い方なので
  **compile error にしてはならない**。target-doctor の **advisory**
  (ADVISORY-D9 仮称、「実抽出ではこの facet は常に空」) が正解。
- **S2 → format parity** は CI 統合価値が明確で機械的。
- **S3 / S4 / S5 は「解消しない」判定** (§2.4 参照)。

### 2.3 採用 — 本命拡張、ただし X-2 の後 (Wave 3)

- **§19 spec quality metrics (meta-verdict)**: D4/D6 で個別対処してきた
  「vacuous PASS」問題の一般解。spec_coverage (観測 delta 次元のうち
  constraint が触れる割合) + meta-verdict (good/weak/insufficient)。
  設計ピン: **Advisor surface 固定・verdict 非参与** (§23.3。これを
  verdict に混ぜると「not an intent validator」を侵す)。
- **§10.3 round-trip log**: per-stage hash chain (intent/state/delta/
  verdict)。determinism・auditability の flagship で ecosystem 不変条件
  (audit layer 再現性) の実装的裏付け。
- **順序判断**: どちらも「効くか」(X-2 外部検証) の結果と相互情報を持つ
  — 特に §19 は X-2 の C-lite 誤判定タグ分析が実データを供給する。
  **X-2 pilot (E-3) より先に着手しない**。

### 2.4 見送り / 凍結維持 (declared asymmetry として doc pin)

| 対象 | 判定 | 理由 |
|---|---|---|
| S3 `compare` sensor parity | **見送り** | `check` = CI 統合の full-surface command、`compare` = local-dir 軽量経路という意図的非対称を宣言する方が薄い。`source_selection_planning.md §10` の再評価 (据置) と同判定。W1-a で doc pin |
| S4 suppression 統一 | **見送り** | mute = advisory 層 / Suppression = verdict 層は **層分離そのものが設計** (LLM scout を verdict から隔離する Phase H の柱)。統一はむしろ隔離を弱める。W1-a で境界を doc pin |
| S5 init recipe 拡張 | **見送り** | recipe は opinionated subset が仕様。catalog + hand-written 経路が既に全表面を提供 |
| Brief 6 TS / §21.5 LSP / §22 多言語 / §20 packaging / PyPI・Action 配布 | **凍結維持** | ROADMAP どおり post-X-2 (empirical evidence 後)。順序不変 |
| P2 repair core 完備 / retrospective audit / nightly scan | **後倒し** | §19 着地後に再評価 (repair_order は §19 の meta 情報と相互作用) |
| D2-3 xdist / F6 Semgrep 再実行 | **据置** | 前者 = user 判断待ちのまま。後者 = `semgrep.dev` 許可 network policy の別 session 案件 |

## 3. Task plan (CSCI-56〜61)

実行体制は全タスク共通: **Fable = brief 発行 + verdict のみ**。実装・
テスト・dogfood は指定 executor へ。1 タスク = 1 PR = 1 brief。

### Wave 1 — hygiene (即発行可、E-3 と並走)

| ID | タスク | Executor | 規模 |
|---|---|---|---|
| **W1-a** | docs 整合 sweep: S6 (ROADMAP 8/8 化) + S7 (doc_refactor self-archive + 表 status 更新) + S8 (open questions へ解決/据置を追記) + `brief_8_planning.md §15.1` grounding bullet 追加 + §2.4 の 3 件の declared-asymmetry pin (S3/S4/S5) | **Sonnet** | 半日 / docs のみ |
| **W1-b (CSCI-56)** | H-5 申し送り P3 ×3: ① `aggregate_advisory_states` の非 LLM 入力を silent skip → `ValueError` (fail-closed) ② ensemble の message を max-severity member から採る (severity と出所を統一) ③ `counts.scouted` = dedup 後件数を doc 化 | **Sonnet** | 半日 / code + test |

依存なし。W1-a は判定変更ゼロ (doc pin のみ)、W1-b は挙動変更 2 件を
必ず test encode。

### Wave 2 — 非対称解消 (設計ピン済)

| ID | タスク | Executor | 規模 |
|---|---|---|---|
| **W2-a (CSCI-57)** | **Ghost-facet advisory (S1)**: extractor 未実装 facet (`type_relations` / `control_flow` / `data_flow` / `coverage`) を target する constraint への ADVISORY-D9 (仮)。error ではなく advisory (§23.1 pin、§2.2)。未実装 facet 集合は extractor registry から導出し hardcode しない (extractor 追加で自動解消)。advisory enum 拡張 → `advisory-2` compatibility policy に従い bump 判定を brief で確定 | **Opus** | 1 日 / authoring + doctor + test |
| **W2-b (CSCI-58)** | **Format parity (S2)**: `ssp scan` / `ssp from-json` に gh-actions、`compile-repair` / `validate-plan` に sarif + gh-actions。§15.1 で既存 SARIF/gh-actions renderer の実 shape を grep してから spec 化 (validate-plan の would_violate → SARIF result への写像が自然に立たない場合、その format は「対象外を宣言」に切替可 — 無理な写像を発明しない) | **Sonnet** | 1 日 / cli + test |

W2-a が本 survey の主産物。W2-b は独立で並走可。

### Wave 3 — 本命拡張 (X-2 pilot の後、着手前に planning 増補)

| ID | タスク | Executor | 前提 |
|---|---|---|---|
| **W3-a (CSCI-59〜60)** | **§19 spec quality metrics**: spec_coverage 算出 + meta-verdict (Advisor surface 固定、verdict 非参与)。2 PR 想定 (metrics 算出 / doctor・envelope 露出)。着手前に本 doc へ設計 section 増補 (X-2 の誤判定タグ実データを入力に) | **Opus** | **E-3 (X-2 pilot) 完了後** |
| **W3-b (CSCI-61)** | **§10.3 round-trip log**: intent/state/delta/verdict の per-stage hash chain を envelope optional field で露出。schema_version bump 判定含む | **Opus** | W3-a と独立、X-2 後 |
| W3-c | override 機構 (Brief 3 #3) | — | §19 着地後に再評価 (据置) |

## 4. Sequencing — 既存 queue との整合

STATUS.md 次の発行順序の主軸は **E-3 (Phase X-2 pilot、別 session 委譲)**
のままで不変。本 plan はそれを置き換えない:

    E-3 (別 session、本命) ── 並走 ──> Wave 1 → Wave 2 (repo-internal)
                                              ↓ X-2 の結果を入力に
                                           Wave 3 (§19 / §10.3)

Wave 1-2 は X-2 待ちの間に executor が消化できる独立小粒。Wave 3 は
「効くか」の empirical evidence を見てから投資する (Fable 評価レビュー
「上物より中核仮説の falsification を先に」と同判定)。

## 5. 発行手順 (運用)

1. user が着手 wave を指定 → Fable が `/new-brief` で該当タスクの brief
   起草 (§15 gate、S# finding の file 引用を grounding に使う)
2. 実装は brief 記載の executor (Opus/Sonnet subagent or Codex handoff —
   どちらでも brief format は `AGENTS.md §1` 共通)
3. Fable は Completion Summary / distilled review evidence で verdict
4. merge 後: STATUS.md sweep + 本 doc の該当行に PR 番号を追記、wave
   完走時は §3 の表を completed 化

本 doc 自体の完了条件: Wave 1-2 全 PR merged + Wave 3 の go/no-go 判定
記録。その後 REFERENCE 化 (または §19 planning へ発展的解消)。

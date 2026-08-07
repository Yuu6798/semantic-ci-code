# Doc Refactoring Planning (2026-05-21 起草)

Status: **ARCHIVED (completed 2026-05-21)** — 全 Phase の完走後、履歴資料として
`docs/archive/doc_refactor_planning.md` に移送済み。以下は当時の計画と実行記録であり、
現在の作業状態は `.claude/memory/STATUS.md` を正本とする。

## 0. 背景と Goal

### 背景

5/21 Session 2 終了時点で **起動時 attention budget が ~2,500 lines** に
膨張、 doc 規律 infrastructure 自体が noise 源化する閾値に到達した。
2026-05-21 Session 2 でユーザが本懸念を指摘 — 「経験値の外部化 discipline」
自身が **適切な圧縮なしで膨張する逆説** にハマっていることが confirmed
(本日 `AGENTS.md +200 lines` がその症状)。

### Primary Goal

**起動時 attention budget を ~2,500 lines → ~800 lines に圧縮**、 ただし
**累積された経験値の情報量は失わない** (archive 移送 + test 化に分散)。

### Success Metrics (定量)

- `CLAUDE.md` ≤ 200 lines (現 320 → 軽量 entry point)
- `AGENTS.md` ≤ 300 lines (現 520 → §5 圧縮 + Forward Design Note 分離)
- `.claude/memory/STATUS.md` ≤ 400 lines (現 800+ → archive 移送 +
  1-paragraph Phase 強制)
- `.claude/memory/_index.md` 各 entry ≤ 2 lines (現 30-80 lines essay →
  本来仕様の 1 行 index 復元)
- **起動時 minimum 読み込み合計 ≤ 800 lines** (Tier A 制約)

### Non-Goals

- 既存 `docs/*.md` (`code_semantic_ci_design.md` / `brief_*_planning.md` /
  case studies) の本文圧縮は scope 外 (これらは brief 起草時 on-demand
  読み込みで attention budget に常時入らない)
- 既存 test suite の compaction (test の冗長性 ≠ doc 冗長性、 test は
  drift 防止が主機能)
- 累積知識の削除 — 全て archive へ移送

---

## 1. 定量的現状

| Artifact | 現サイズ | tier 候補 | 圧縮余地 |
|---|---|---|---|
| `CLAUDE.md` | 320 lines | Tier A (常時) | 120 lines 圧縮可 (Workflow / Repository Layout / Design Documents は Tier B/C へ pointer 化) |
| `AGENTS.md` | 520 lines | §1-§4 = Tier B / §5 = Tier B / Forward Design Note = Tier C | §5 を 180 → 80 lines に統合可、 Forward Design Note を別 file に分離 |
| `STATUS.md` | 800+ lines | Tier A | `## 直近 merged` 古い entry を archive 移送で 400-500 lines 削減 |
| `_index.md` | ~1,000 lines (28 entries × 30-80 lines) | Tier A | 30 日経過 entry を 1 行化で 800 lines 圧縮可 |
| 18 dated session logs | ~3,600 lines | Tier C/D (on-demand) | archive 移送のみ、 本文圧縮不要 |
| `docs/*.md` (18 files) | 7,532 lines | Tier C/D | scope 外 (brief 起草時のみ) |

**累積 attention overhead**: 起動時必読 ≈ 2,720 lines、 brief 起草時追加
≈ 1,000 lines。

---

## 2. Bloat sources の inventory

| # | Source | 症状 | 修正方針 |
|---|---|---|---|
| **B1** | `_index.md` の essay 化 | 本来「1 行 index」 が 30-80 line summary に膨張 | 30 日経過 entry を 2 行以内に強制 collapse、 元 text は dated file に既に保存済なので情報損失なし |
| **B2** | `STATUS.md ## Phase` 累積 | 新 Phase paragraph 追加・旧削除しない pattern が固定化 (5/21 で Codex も再発) | Phase は **1 paragraph 厳守、 更新時は完全上書き** を rule 化、 自動 check 可 |
| **B3** | `STATUS.md ## 直近 merged` 累積 | 5/2 〜 5/21 の全 PR entry が inline 残置 | 最新 5 entry のみ inline、 古いものは `archive/STATUS_MERGED_LOG.md` 移送 |
| **B4** | `STATUS.md 次の発行順序` の stale | 完走済 item の削除を「後で」 にしがち (5/21 で ADVISORY-S1 + R17 で 2 連続発生) | merge 直後の自動 check 化 (`tests/discipline/test_status_md_drift.py`) |
| **B5** | `AGENTS.md §5` の Maintenance / Anti-Pattern 重複 | §5.6 (rule) と §5.7 (anti-pattern) が同じ規則を肯定形 + 否定形で 2 度書き | 1 つの list に統合、 80 lines に圧縮 |
| **B6** | Cross-reference 鎖の深さ | 1 rule に到達するまで 3-4 hop 必要 | Tier A doc 内に 1 行 summary 残置、 詳細は Tier B/C に pointer |
| **B7** | Forward Design Note (Brief 7) が `AGENTS.md` inline | 本来 brief 起草時のみ必要な情報が handoff doc に inline | `docs/brief_7_planning.md §11` か別 doc に分離、 `AGENTS.md` は pointer のみ |
| **B8** | dated session logs の無圧縮累積 | 18 files × avg 200 lines、 増加止まらず | 30 日経過したら `archive/YYYY-MM/` 移送 + summary 5 行残置 |
| **B9** | rule の doc 化過剰 | §5.7 anti-pattern 7 件の半数は test で enforce 可能なのに doc rule に留まっている | `tests/discipline/` 新設、 enforce 可能なものを doc から test に移送 |

---

## 3. Refactoring Phases (sequenced)

### Phase 0: **Tier 階層の明示** (CLAUDE.md edit、 1 PR、 半日)

最初に「読み込み layer の階層」 を doc 化、 後続 phase の基準にする。

`CLAUDE.md` `Required Reading Before Editing` を以下に置換:

```
## Required Reading Before Editing

### Tier A (常時必読、 起動時 ≤ 800 lines target)
1. CLAUDE.md (本 doc、 core operating contract のみ)
2. STATUS.md `## Phase` (1 paragraph) + `次の発行順序` (current entries)
3. _index.md 直近 5 entries (本来仕様: 1-2 line summary)
4. AGENTS.md §1-§4 (Message Flow + Brief / Summary format)

### Tier B (brief 起草時必読、 ≤ 300 lines target)
1. AGENTS.md §5 Experience Externalization Discipline (compaction 後 ≤ 80 lines)
2. `docs/brief_8_planning.md §15` brief drafting checklist
3. 関連 planning doc 当該 §

### Tier C (関連 brief 着手時 on-demand)
- `docs/brief_*_planning.md` 該当
- 直近 3 dated session logs (full)
- 関連 case study (`docs/multi_agent_audit_case.md` 等)

### Tier D (debug / archeology only)
- `.claude/memory/archive/`
- 30 日以上前の dated session logs
- 旧 STATUS.md merged log
```

**Acceptance**: Tier A 列挙が ≤ 800 lines 内で完結することを確認。

### Phase 1: **STATUS.md compaction** (memory exception、 直 push、 半日)

最大 ROI。 800 lines → 400 lines 目標。

1. **`## Phase` policy 強制**: 1 paragraph 厳守、 更新時完全上書き
2. **`## 直近 merged`**: 最新 5 entry のみ inline、 残りは
   `archive/STATUS_MERGED_LOG.md` (新規) に移送
3. **`次の発行順序`**: stale entry を全 sweep
4. **`Frozen / Deferred`**: 当該 brief landing 時点で完走化、 古い deferred
   を archive 移送

**Acceptance**: STATUS.md ≤ 400 lines、 全 entry が active state を反映。

### Phase 2: **_index.md 本来仕様復元** (memory exception、 直 push、 半日)

`_index.md` を **1-2 line index** の本来仕様に復元。

1. 30 日以上前 entry を **1 行 summary** に collapse (full text は dated
   file に保存済、 情報損失ゼロ)
2. 直近 1 ヶ月 entry を **2 行 summary** に圧縮 (key decision + 該当 PR # +
   詳細 ref のみ)
3. column format: `| Date | PR # | One-line outcome | dated file ref |`

**Acceptance**: `_index.md` ≤ 60 lines (28 entries × avg 2 lines)。
~1,000 lines → ~60 lines = **940 lines 削減**。

### Phase 3: **AGENTS.md §5 collapse** (PR、 1 日)

180 lines → 80 lines target。

1. **§5.6 Maintenance Practice + §5.7 Anti-Patterns を 1 list に統合**:
   rule + 反例 + 該当 enforcement (test 名 / script 名) の 3 列 table
2. **§5.2 Empirical Envelope の data 表は維持** (これは経験値外部化の
   base case 証拠、 削れない)
3. **§5.3 Three-Tier Externalization** を CLAUDE.md `Required Reading` に
   統合 (Tier 概念は読み込み tier と並行する概念、 統合の方が cognitive
   load 低)
4. **§5.5 体制別 envelope** を §5.2 table に column 追加で吸収
5. **§5.8 Cross-Reference** を末尾 pointer に圧縮

**Acceptance**: `AGENTS.md §5` ≤ 80 lines、 8 sub-section → 5 sub-section
(Principle / Envelope (data table) / Practice (combined) /
Anti-Pattern-to-Test-Map / Cross-Ref)。

### Phase 4: **Forward Design Note を分離** (PR、 半日)

`AGENTS.md` Forward Design Note: Brief 7 / SSP v0.1 (現 ~220 lines) は
**CSCI-36 着手時にしか参照されない**。 Handoff doc から分離:

- 移送先: `docs/brief_7_planning.md §11.5` (新 section) または
  `docs/ssp_protocol_design_note.md` (新規)
- `AGENTS.md` には **pointer 1 行** のみ残置

**Acceptance**: AGENTS.md ≤ 300 lines。 Forward Design Note 内容は移送先で
完全保存。

### Phase 5: **Archive infrastructure** (PR、 半日) — **infrastructure landed (2026-05-21)**

`.claude/memory/archive/` directory 構造を確立:

```
.claude/memory/archive/
├── YYYY-MM/                  # 30 日経過 dated session logs (TTL-driven、 incremental)
│   ├── 2026-05-02.md
│   └── ...
├── STATUS_MERGED_LOG.md      # STATUS.md `## 直近 merged` から移送した古い entries
├── INDEX.md                  # archive 全体の索引 (Tier D 専用)
```

Compaction policy (memory wrap-up 時に自動実行):

- 30 日経過 dated entry → `archive/YYYY-MM/` 移送
- `_index.md` の該当行を 1 行に collapse + archive path 追記
- session log dated file 自体は原文保存 (情報損失ゼロ)

**Acceptance (originally)**: 30 日以上前の dated entries (5/2-5/7 等、 6 files) が
archive 移送、 `_index.md` で 1 行参照可能。

**Phase 5 actual landing (2026-05-21 Session 2、 commit `<this PR>`)**:
本 phase 起動時 (2026-05-21) の dated session log 最古は 2026-05-02
(19 日経過)、 **30 日 TTL に到達した entry は存在しない**。 したがって
本 PR は **archive infrastructure 設置 (INDEX.md + TTL contract pin) のみ
を land**、 実 file 移送は次回 wrap-up trigger 以降の TTL-driven ritual
として発火する。 次回 entry 移送発生予定: 2026-06-01 以降 (5/2 entry が
30 日に到達)。 STATUS_MERGED_LOG.md は Phase 1 で既に landed 済 (`0db925f`)。

- 新設: `.claude/memory/archive/INDEX.md` (本 archive directory の Tier D
  専用 索引、 layout / 移送 protocol / TTL contract / Phase 6 cross-ref +
  archive 由来 4 phase log を pin)

### Phase 6: **Test-enforced rule への変換** (完走: 5 implemented + 1 retired)

`tests/discipline/` で doc rule の自動 check を実装。 初回 slice (2026-05)
で STATUS.md / `_index.md` hygiene の 3 test、 続く Phase 6 v2 (2026-05-29)
で schema-grep + dual-case dogfood の 2 test を landed。 round-count
candidate は test 形式と相性が悪いため retire (理由は下表)。

| Rule | Status / test | 検出方法 |
|---|---|---|
| `STATUS.md 次の発行順序` 更新先送り | implemented: `tests/discipline/test_status_md_next_queue_no_completed.py` | queue heading / primary bullet に `完走` / `landed` marker が残っていれば fail |
| `STATUS.md ## Phase` duplicate paragraph | implemented: `tests/discipline/test_status_md_phase_single_paragraph.py` | `## Phase` section の paragraph count が 1 でなければ fail |
| `_index.md` essay cell 化 | implemented: `tests/discipline/test_index_md_entry_compactness.py` | table cell が 500 chars を超えれば fail |
| schema-grep check | implemented: `tests/discipline/test_json_schema_version_sync.py` | 各 CLI envelope の `schema_version` 定数 (producer) と `docs/json_schema.md` の Currently/Always anchor が不一致なら fail |
| dual-case dogfood | implemented: `tests/discipline/test_dogfood_dual_case.py` | registered case/verdict-matrix report の `Verdict` 列 (散文ではなく列をパース) が PASS / FAIL 両方向を含まなければ fail。 PR #118 Codex review で散文スキャンの誤通過を指摘され列パースに改修 |
| round-count-to-encoding check | **retired** (test 化せず) | review round 数は hand-written prose にしか存在せず、 test はその文字列の近傍 proxy にしかなり得ない。 肝心の「encode 忘れ」 case こそ検出できず、 framework 自己膨張パラドックスを再誘発する。 intent は `CLAUDE.md` 終了時ルールの wrap-up checklist 項目 (5+ round 論点の encode check) として常駐 |

**Acceptance**: 完走 (5 implemented + 1 retired)。 schema-grep / dual-case
dogfood を test 化、 round-count は CLAUDE.md wrap-up checklist に格下げ。

### Phase 7: **Memory wrap-up protocol の更新** (CLAUDE.md edit、 半日)

`CLAUDE.md` `終了時ルール (自動トリガー)` を以下追記:

```
実行内容 (本 wrap-up):
- 会話の振り返りサマリーを `.claude/memory/YYYY-MM-DD.md` に保存
- `_index.md` に 1 行 (本来仕様、 2 行以内) サマリーを追記
- 30 日以上前の dated entries を `archive/YYYY-MM/` 移送 (自動 compaction)
- STATUS.md `## 直近 merged` で 5 entries 超過分を archive 移送
- CLAUDE.md / AGENTS.md への更新候補があればユーザーに提案
```

**Acceptance**: 次回 wrap-up で archive 移送が自動実行される pattern が
確立。

---

## 4. Sequencing 推奨

| 順 | Phase | 規模 | 体制 | ROI |
|---|---|---|---|---|
| 1 | **Phase 0: Tier 階層明示** | 半日 | Claude alone (CLAUDE.md edit) | 最高 (後続 phase の基準) |
| 2 | **Phase 2: `_index.md` 復元** | 半日 | Claude alone (memory exception) | **最大 ROI** (~940 lines 削減) |
| 3 | **Phase 1: STATUS.md compaction** | 半日 | Claude alone (memory exception) | 高 (~400 lines 削減) |
| 4 | **Phase 3: AGENTS.md §5 collapse** | 1 日 | split (brief 起草 → Codex 実装) | 中 (~100 lines 削減 + 構造改善) |
| 5 | **Phase 4: Forward Design Note 分離** | 半日 | Claude alone or split | 中 (~220 lines 削減) |
| 6 | **Phase 5: Archive infrastructure** | 半日 | Claude alone (file 移送のみ) | 構造的 |
| 7 | **Phase 7: wrap-up protocol 更新** | 半日 | Claude alone (CLAUDE.md edit) | 構造的 |
| 8 | **Phase 6: test-enforced rule 変換** | 1-2 日 | split | 中長期 (再発防止) |

**累計**: 4-6 日規模、 8 PR (うち 5 PR が memory exception direct push、
3 PR が feature branch)。

**最短経路 (1 day で attention budget 半減狙い)**: Phase 0 + Phase 2 +
Phase 1 を 1 session で連続実行。 ~800 + 400 + 940 = **2,140 lines 削減**、
起動時 attention budget が **2,500 → 800 lines に到達**。

---

## 5. Risk mitigation

| Risk | 対策 |
|---|---|
| **情報損失** | 全 compaction は archive 移送形式、 削除なし。 dated entries は原文不変、 `_index.md` 圧縮も dated file への ref で復元可 |
| **discoverability 損失** | Tier A doc 内に 1 行 pointer を残す pattern を強制、 archive index で全 trail 検索可能 |
| **interim 状態の不整合** | Phase 単位で atomic PR / commit、 各 phase 単独で完結する設計 |
| **process 中断** | Phase 0 (Tier 階層) が最初に landing するので、 後続 phase 中も読み込み tier rule は明示状態 |
| **drift 再発生** | Phase 6 (test-enforced) で再発生を構造防止、 doc rule 単独依存を脱却 |
| **refactoring 自体が新たな bloat 源化** | 本 plan を含む meta-discussion を `docs/ai_velocity_accumulation_case.md` (仮) に 1 セクションで record、 plan doc 自体は本 refactoring 完了で archive 移送 (self-referential test) |

---

## 6. 緊急 action item

**最短経路 = Phase 0 + Phase 2 + Phase 1 を 1 session 連続実行** が緊急
タスクの中核。 これだけで attention budget が目標値到達。

Codex 不在問題に影響されない (全 docs / memory edit、 Claude 単独完結
可能)。 規模感半日〜1 日、 PR 数 3 件 (or memory exception で direct main
3 commit)。

順序:

1. Phase 0: `CLAUDE.md` `Required Reading` を Tier A/B/C/D 形式に書換 +
   数字 budget pin
2. Phase 2: `_index.md` の 30 日経過 entry を 1 行化、 直近 entry も 2 行
   に圧縮
3. Phase 1: `STATUS.md ## 直近 merged` の古い entry を archive 移送、
   `次の発行順序` の stale sweep、 `Frozen / Deferred` の active 化

Phase 3 以降は次セッション以降に分散。 ただし **Phase 4 (Forward Design
Note 分離) は Brief 7 / CSCI-36 entry より先に landing が望ましい**
(CSCI-36 起草時に `AGENTS.md` inline の Forward Design Note を読むのは
attention 過負荷、 専用 doc に分離後の方が context 局所化できる)。

---

## 7. Self-referential note

本 plan doc は完了後に `docs/archive/` へ移送済み。これは「経験値外部化
framework が自分自身を refactor する」dogfood example であり、規律
infrastructure を自身へ適用する self-referential test の最初の case となった。
移送の動作 trail 自体が、経験値外部化 discipline の「圧縮 + 保存」ループを
実証している。

---

## 8. Cross-Reference

- `CLAUDE.md` § Experience Externalization (経験値の外部化) — 本 refactor
  の動機を pin する meta-principle
- `AGENTS.md § 5. Experience Externalization Discipline` — 本 refactor の
  scope に含まれる主対象 (Phase 3 で §5 自体を collapse)
- `.claude/memory/STATUS.md` — Phase 1 の主対象
- `.claude/memory/_index.md` — Phase 2 の主対象
- `.claude/memory/2026-05-21.md` Session 2 — 本 refactor の起草経緯
  (user の bloat 懸念 + Johari Window 比喩での framework 自己検証)
- `docs/multi_agent_audit_case.md` — parallel agent blind spot 観測事例、
  本 refactor 完了で経験値外部化 framework の self-test を追加
- `docs/ai_velocity_accumulation_case.md` (未着手、 仮) — ABCD 完走時点で
  起こす case study、 本 refactor の前後 attention budget 数値を data
  point に組み込む候補

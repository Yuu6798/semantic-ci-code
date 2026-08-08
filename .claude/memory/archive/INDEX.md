# `.claude/memory/archive/` — INDEX

セッション memory の disk-resident artifact compaction の **唯一の
destination**。 ここに置かれた file は `.claude/memory/STATUS.md` /
`.claude/memory/_index.md` / dated `YYYY-MM-DD.md` の active set から
ratched 退避された履歴で、 **情報損失ゼロ** (原文保存) を invariant と
する。

## Layout

```
.claude/memory/archive/
├── INDEX.md                     # 本 file (archive 全体の Tier D 専用 索引)
├── STATUS_MERGED_LOG.md         # STATUS.md `## 直近 merged` 5 entries 超過分
└── YYYY-MM/                     # 月別 dated session log の archive
    ├── 2026-04-XX.md            # (将来 30 日経過時に発生)
    └── ...
```

## Tier 位置付け

本 directory の content は **Tier D (debug / archeology only)** —
`CLAUDE.md` § Required Reading Before Editing で定義された 4 階層の
最下位。 通常 session 起動時の attention budget には入らない。 参照は:

- 特定 PR の歴史的経緯を調べる時 (例: 「PR #42 はどう merged されたか」)
- regression の根本原因が古い decision に遡る時
- `_index.md` 1-line summary では情報不足で dated 原文が必要な時
- archive 移送 protocol 自体の audit / drift check

## Current contents (2026-07-07 時点)

| File / Directory | 移送 cutoff | 移送元 | Migration commit |
|---|---|---|---|
| `STATUS_MERGED_LOG.md` | 2026-06-07 | `STATUS.md ## 直近 merged` の 13 entries (5/15 Session 2 〜 5/5 + 5/27 + 5/28 S1 + 5/29 doc-refactor) | `0db925f` (Phase 1) 〜 2026-06-07 wrap-up |
| `2026-05/2026-05-02.md` | 2026-06-02 (>30 日 TTL) | `_index.md` 2026-05-02 entry (初の dated-log 物理移送) | 2026-06-02 wrap-up |
| `2026-05/2026-05-03.md` | 2026-06-03 (>30 日 TTL) | `_index.md` 2026-05-03 entry (S1+S2+S3 統合) | 2026-06-03 wrap-up |
| `2026-05/2026-05-04.md` | 2026-06-03 (30 日 TTL) | `_index.md` 2026-05-04 entry (Brief 3 残務 + Brief 4 全体) | 2026-06-03 wrap-up (S2) |
| `2026-05/2026-05-05.md` | 2026-06-07 (>30 日 TTL) | `_index.md` 2026-05-05 entry (S1-S4 統合: §23.1 格上げ + Brief 4b/4c/4d + Brief 5 planning) | 2026-06-07 wrap-up |
| `2026-05/2026-05-06.md` | 2026-06-07 (>30 日 TTL) | `_index.md` 2026-05-06 entry (S1-S3 統合: §23.3 + SSP 4 層化 + #50) | 2026-06-07 wrap-up |
| `2026-05/2026-05-07.md` | 2026-06-07 (>30 日 TTL) | `_index.md` 2026-05-07 entry (S1-S5 統合: Brief 5 完走 + D1〜D5 dogfood + Brief 7 申し送り) | 2026-06-07 wrap-up |
| `2026-05/2026-05-08.md` | 2026-06-08 (>30 日 TTL) | `_index.md` 2026-05-08 entry | 2026-06-08 wrap-up |
| `2026-05/2026-05-09.md` | 2026-06-09 (>30 日 TTL) | `_index.md` 2026-05-09 entry (perf brief #70/#71 + ResultStatus C+B) | 2026-06-09 wrap-up |
| `2026-05/2026-05-12.md` | 2026-06-11 (30 日 TTL) | `_index.md` 2026-05-12 entry (ResultStatus planning 取り込み #74) | 2026-06-11 wrap-up |
| `2026-05/2026-05-15.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-05-15 S1-S4 entries (ResultStatus split 完走 + Brief 8 CSCI-41/42/43) | 2026-07-07 wrap-up |
| `2026-05/2026-05-19.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-05-19 entry (canonical-form refactor #85) | 2026-07-07 wrap-up |
| `2026-05/2026-05-21.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-05-21 S1-S5 entries (doc refactor 8 phase + ecosystem framing #86-#96) | 2026-07-07 wrap-up |
| `2026-05/2026-05-22.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-05-22 entry (#98 + source_selection planning #99) | 2026-07-07 wrap-up |
| `2026-05/2026-05-25.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-05-25 entry (F+D queue 完走 #100-#105) | 2026-07-07 wrap-up |
| `2026-05/2026-05-26.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-05-26 entry (authoring UX #106/#107) | 2026-07-07 wrap-up |
| `2026-05/2026-05-27.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-05-27 entry (Brief 7 SSP 完走 #109-#112) | 2026-07-07 wrap-up |
| `2026-05/2026-05-28.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-05-28 S1+S2 entries (Phase G planning + real-PR dogfood tracker #114-#117) | 2026-07-07 wrap-up |
| `2026-05/2026-05-29.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-05-29 S1+S2 entries (doc-refactor Phase 6 + skills/hook #118-#121) | 2026-07-07 wrap-up |
| `2026-06/2026-06-02.md` | 2026-07-07 (>30 日 TTL、2026-06 dir 初設置) | `_index.md` 2026-06-02 entry (Phase G G-1/G-2 #124-#126) | 2026-07-07 wrap-up |
| `2026-06/2026-06-03.md` | 2026-07-07 (>30 日 TTL) | `_index.md` 2026-06-03 S1+S2 entries (G-3〜G-4b + Phase H planning #127-#132) | 2026-07-07 wrap-up |

## 移送 protocol

**`CLAUDE.md § Session Memory → 終了時ルール`** で定義された
archive 移送の要否確認は wrap-up trigger で自動起動する。実際の file 物理
move と index 書換は operator が手動実行する。該当 step:

- **Step 3** (wrap-up checklist): 30 日以上前の dated entries を
  `archive/YYYY-MM/` に移送、 `_index.md` 該当行を 1 行 summary +
  archive path に書換
- **Step 5** (wrap-up checklist): `STATUS.md ## 直近 merged` で
  5 entries 超過分を `archive/STATUS_MERGED_LOG.md` 末尾に移送

移送は `.claude/memory/` の **memory exception** 枠で main 直 push 可能
(feature branch + PR 不要)。

### TTL (各 artifact の retain 期限)

| Artifact | TTL | 移送先 | post-移送の reference |
|---|---|---|---|
| dated `YYYY-MM-DD.md` | 30 日 | `archive/YYYY-MM/YYYY-MM-DD.md` | `_index.md` から 1 行 summary + archive path |
| `_index.md` 該当 entry | 同上 | inline 維持 (圧縮済) → archive path 追記 | 詳細は archive file 経由 |
| `STATUS.md ## 直近 merged` entry | 直近 5 を超えた時点 | `archive/STATUS_MERGED_LOG.md` 末尾 | 原文保存、 全文閲覧可 |
| `STATUS.md 次の発行順序` 完走 entry | merge と同時 | `## 直近 merged` の新 entry に変換 | 完走宣言として保存 (archive 移送ではない) |
| `STATUS.md ## Phase` paragraph | 上書き時 | (archive 移送なし、 1 paragraph 厳守) | 旧 phase history は dated session log に分散保存 |

## Self-referential drift detection

archive 移送 protocol 自体の遵守は `tests/discipline/`
(`docs/archive/doc_refactor_planning.md` Phase 6) で test 化済み:

- `tests/discipline/test_status_md_phase_single_paragraph.py` — Phase
  paragraph 重複検出
- `tests/discipline/test_status_md_next_queue_no_completed.py` — 完走
  entry の sweep 漏れ検出
- `tests/discipline/test_index_md_entry_compactness.py` — essay 化
  regression 検出

これらにより、archive policy の一部 (sweep + compaction discipline) は
CI で mechanically enforce されている。archive 移送 (file 物理 move) 自体は
wrap-up trigger 起動時の手作業 ritual で保持。

## 由来

- Phase 1 (`docs/archive/doc_refactor_planning.md` 2026-05-21、 commit `0db925f`)
  で `STATUS_MERGED_LOG.md` 初設置 (STATUS.md 831 → 505 lines 圧縮の
  destination)
- Phase 2 (commit `4783728`) で `_index.md` 1-line index 復元、 archive
  への dated log 移送は **次回 wrap-up 以降** の TTL-based ritual で発火
- Phase 5 (本 commit) で **本 INDEX.md 設置** + archive layout 公式化 +
  TTL contract 明示 + Phase 6 cross-ref 設置
- Phase 7 (commit `2619753` / fix `75244c7`) で wrap-up trigger に
  archive 移送 step 統合

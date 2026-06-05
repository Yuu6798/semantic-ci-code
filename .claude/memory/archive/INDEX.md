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

## Current contents (2026-06-05 時点)

| File / Directory | 移送 cutoff | 移送元 | Migration commit |
|---|---|---|---|
| `STATUS_MERGED_LOG.md` | 2026-06-05 | `STATUS.md ## 直近 merged` の 13 entries (5/15 Session 2 〜 5/5 + 5/27 + 5/28 S1 + 5/29 doc-refactor) | `0db925f` (Phase 1) 〜 2026-06-05 wrap-up |
| `2026-05/2026-05-02.md` | 2026-06-02 (>30 日 TTL) | `_index.md` 2026-05-02 entry (初の dated-log 物理移送) | 2026-06-02 wrap-up |
| `2026-05/2026-05-03.md` | 2026-06-03 (>30 日 TTL) | `_index.md` 2026-05-03 entry (S1+S2+S3 統合) | 2026-06-03 wrap-up |
| `2026-05/2026-05-04.md` | 2026-06-03 (30 日 TTL) | `_index.md` 2026-05-04 entry (Brief 3 残務 + Brief 4 全体) | 2026-06-03 wrap-up (S2) |
| `2026-05/2026-05-05.md` | 2026-06-05 (>30 日 TTL) | `_index.md` 2026-05-05 entry (S1-S4 統合: P1 完走 + Brief 5 planning + cache slice + §23.1 格上げ) | 2026-06-05 wrap-up |

## 移送 protocol

archive 移送は **`CLAUDE.md § Session Memory → 終了時ルール`** で定義
された wrap-up trigger の一部として自動実行される。 該当 step:

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

archive 移送 protocol 自体の遵守は将来 `tests/discipline/` (`docs/
doc_refactor_planning.md` Phase 6) で test 化される予定:

- `tests/discipline/test_status_md_phase_single_paragraph.py` — Phase
  paragraph 重複検出
- `tests/discipline/test_status_md_next_queue_no_completed.py` — 完走
  entry の sweep 漏れ検出
- `tests/discipline/test_index_md_entry_compactness.py` — essay 化
  regression 検出

これらが landed すると、 archive policy の 一部 (sweep + compaction
discipline) が CI で mechanically enforce される。 archive 移送 (file 物理
move) 自体は wrap-up trigger 起動時の手作業 ritual で保持。

## 由来

- Phase 1 (`docs/doc_refactor_planning.md` 2026-05-21、 commit `0db925f`)
  で `STATUS_MERGED_LOG.md` 初設置 (STATUS.md 831 → 505 lines 圧縮の
  destination)
- Phase 2 (commit `4783728`) で `_index.md` 1-line index 復元、 archive
  への dated log 移送は **次回 wrap-up 以降** の TTL-based ritual で発火
- Phase 5 (本 commit) で **本 INDEX.md 設置** + archive layout 公式化 +
  TTL contract 明示 + Phase 6 cross-ref 設置
- Phase 7 (commit `2619753` / fix `75244c7`) で wrap-up trigger に
  archive 移送 step 統合

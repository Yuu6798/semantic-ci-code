# Model Delegation Policy — design / execution separation

Status: **ACTIVE** (Claude Code session operating policy)。
導入 2026-07-06。ecosystem 並行 repo で恒久化した開発体制ルール
(設計専任モデルの委譲規律) を code domain に移植したもの。
常時ロードされる操作ルール本体は `CLAUDE.md ## Workflow` の
「Model split」節にあり、本 doc はその根拠・判定基準・委譲対象表の
完全版である。

## 1. なぜこの policy が要るか (実測由来)

きっかけは、レビュー 7 巡に及んだ PR 対応 (ecosystem 並行 repo、
2026-07 実測) で設計専任モデル (Fable) がトークンを大量消費した反省。
実測で判明した重要な発見:

- **トークンの主燃焼源は修正作業ではなかった。** 主因は GitHub ツールの
  戻り値ペイロード — レビュースレッド全文の再取得、返信 API 応答への
  差分・本文 echo 同梱 — であり、コード修正そのものの生成コストは従だった。
- したがって「コール数が少なければ直接やってよい」では不十分。
  **1 コールでも戻り値が重い操作は Fable のコンテキストを燃やす。**
  基準は「コール数 × 戻り値の重さ」の AND でなければならない。
- 高価な設計専任モデルが「ついでに自分で手を動かす」癖は、この
  ペイロード直撃と複合して最も高くつく失敗パターンになる。

## 2. 役割の固定

| Model | 責務 | やらないこと |
|---|---|---|
| **Fable** (設計専任) | 設計、仕様、設計判断、レビュー判定 (verdict)、brief 起草、phase planning、設計 artifact (docs / memory) の起草 | 実装、テスト・lint の実行、dogfooding、重量ペイロードのツール呼び出し (スレッド取得・CI ログ等)、多ファイル調査の直接実施 |
| **Opus / Sonnet** (実行担当) | 実装、修正、テスト・lint 実行、dogfooding、検証、GitHub スレッド操作 (取得・返信)、CI ログ取得、多ファイル調査 | 設計判断の確定、レビュー verdict、brief の発行 |

実行担当は subagent (Agent tool の `model: "sonnet"` / `"opus"` 指定) か
別 session として起動する。既存の Codex handoff (`AGENTS.md`) は
この表の「実行担当」の一形態であり、不変 (§6)。

## 3. 本ルート

    Fable が設計 → Opus/Sonnet が実装・実行・検証 → Fable が判定

- Fable の判定材料は実行担当の **distilled summary** (所見 + 最小抜粋 +
  判定に必要な evidence) に限る。raw payload (スレッド全文、CI ログ全文、
  diff 全文) を Fable のコンテキストへ持ち込まない。
- 実行担当への指示は brief / task prompt として明示 artifact 化する
  (Experience Externalization と同型: 暗黙の口頭運用にしない)。
- レビュー多巡 (P2 chase 等) では、巡回ごとの「スレッド取得 → 修正 →
  返信」ループ全体を実行担当に置き、Fable は判定が必要な巡のみ要約を受ける。

## 4. Fable 直接可の判定基準

両方を満たす場合 **のみ** Fable が直接ツールを呼んでよい:

1. 操作全体が **1〜2 コール**で完結する
2. **各戻り値が軽量**である (数十行オーダーの想定が立つ)

例 (直接可): `git status` / `git log --oneline -5` / `wc -l` /
単一の小さいファイル read / 設計 artifact (docs・brief・memory) への
Write・Edit (戻り値は軽量) / metadata 1 件の軽量取得 (`minimal_output`)。

どちらか一方でも欠けるなら委譲する。**迷ったら委譲** —
判定コスト自体を燃やさないための default。

## 5. 常時委譲 (コール数によらず)

以下は 1 コールで済む場合でも戻り値ペイロードが構造的に重いため、
**コール数によらず**実行担当に委譲する:

- レビュースレッド・レビューコメントの取得 (スレッド全文 payload)
- レビュー返信・コメントの投稿 (応答への本文・差分 echo)
- CI ログ・job log の取得
- PR diff / patch 全文の取得
- テストスイート・lint の実行 (出力全文は実行担当が要約)
- 多ファイル read / 横断調査 (Explore / general-purpose agent に委譲)
- 実装・修正の適用 (単一ファイルの設計 artifact 編集を除く)

## 6. `AGENTS.md` (Codex handoff) との関係

- Claude ↔ Codex の handoff protocol (`AGENTS.md` §1-§4) は**不変**。
  Codex ルートが選ばれた場合、本 policy の追加要求はない (Codex が
  実行担当そのものだから)。
- Claude exception (Codex を介さず Claude Code session 内で実装まで
  完走するルート、例: PR #149 / #151〜#153 型) では、本 policy が適用され、
  実装・実行・検証は Opus/Sonnet subagent が担う。「Fable が設計→実装→
  dogfood→レビュー対応→merge を単独完走」する従来型は本 policy で終了。
- user が明示的に Fable の直接作業を指示した場合は user override として
  従う (その場合もスレッド取得等の重量操作は委譲を提案してよい)。

## 7. Scope guard との関係 (non-goal)

本 policy は**開発運用のコスト規律**であり、製品には一切影響しない。
engine / evaluator / CLI の挙動、決定論、`§23.1` input neutrality、
scope guard (not an LLM-as-judge) は本 policy の対象外。製品に LLM 呼び
出しを持ち込む話ではない。

## 8. Enforcement

- agent 挙動そのものは pytest で構造 enforce できないため、操作ルール
  本体を常時ロードされる `CLAUDE.md ## Workflow` に置く (この doc は
  Tier C 参照)。
- leading indicator: Fable session での GitHub ツール直接呼び出し数と
  レビュー巡あたりのトークン消費。wrap-up 時、違反や境界例に気づいたら
  dated session log に記録し、必要なら本 doc の委譲対象表を更新する。

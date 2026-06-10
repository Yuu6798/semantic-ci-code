# PR Validation Planning — Phase X-2 (code domain) 外部検証実験

> **Status: PLANNING (open, 2026-06-10 起草)。** STATUS.md §E-3 (Phase X-2,
> code domain) が呼んでいる「公開 PR を N≥48 集め、semantic-ci の verdict と
> human reviewer の判断の相関を測る」実験計画の本体。これは新機能ではなく
> **中核仮説の falsification 実験**: 「declared intent の下で 2 状態間の intent
> drift を捕まえる」というツールの存在理由が、外部の実 PR で *効く* かを測る。
>
> 既存 dogfooding (real-PR 8 件 / scale 16 runs) は「**動くか**」(クラッシュ
> しない・well-formed JSON) を確認済み。本実験が答えるのは「**効くか**」
> (verdict が reviewer の関心と一致するか) であり、両者は別問題。

## 0. なぜ今これか / 何を恐れるか

- ROADMAP v0.1.0 exit criteria は「D 全解決 + schema/exit-code 安定」を置くが、
  **「効く証拠」は含まれていない**。今あるのは「動く証拠」のみ。プロダクト
  としての本当のリスクは技術的失敗ではなく「綺麗に作ったが誰も authoring
  コストを払わない / verdict が reviewer 判断と無相関」という空振り。
- 上物 (Phase G security / Phase H LLM scout) を積む前に、中核仮説を外部で
  falsify しに行く。土台のコンクリートが乾く前に二階を建てない。
- **小規模 N での統計的不安定さ + Y のノイズが致命的**: ecosystem の text
  domain 側でも「HA20 = 18/20 一致だが n=20 では断言不能、human_score 付きが
  20 件しかない」が課題として記録済み。同じ轍を踏まないため、Y の質と N の
  両方を設計段階で固定する。

## 1. 中核設計 (凍結)

### 1.1 実験の骨子

```
公開 repo → PR を N≥48 サンプリング → 各 PR で 2 値を独立に取得
                                        ├─ X: semantic-ci verdict (pass/repair/fail)
                                        └─ Y: human reviewer 判断 (approve/changes-requested)
       → (X, Y) 表 → 主指標 (AUROC/MCC/F1/混同行列+bootstrap CI) を算出
```

**最重要原則: X と Y を互いに見ずに独立に作る。** Y を先に凍結し、X 生成
(特に target B) に Y 由来情報を一切流さない (§1.5 leakage 禁止)。

### 1.2 D1: 正解ラベル Y = review 結果ベース (merge/reject は不採用)

**決定: Y は formal review state。`CHANGES_REQUESTED = fail` /
`APPROVED = pass`。**

- merge/reject 二値は GitHub API で安く取れるが、reject の大半が「重複・方針
  変更・放置」等 **コード品質と無関係な理由**で、N が小さいと Y のノイズが
  そのまま ρ/AUROC を潰す。
- review 結果は reviewer が能動的に下した判断なので intent drift 概念に素直。
- 代償: review が付かない PR (self-merge / bot / レビュー文化のない repo) を
  母集団から除外 → N 確保に探索コストが増える (§1.6 で吸収)。

### 1.3 D2: 評価対象 diff = 最初の実質レビュー時点の SHA (⚠️最頻出の罠)

**決定: Y を取った review event の `commit_id` (= レビュー時点の head SHA) を
評価対象に固定する。最終 merge 時点の diff で判定してはならない。**

- 理由: `CHANGES_REQUESTED` を受けた PR は通常その後修正されて merge される。
  最終 diff で X を取ると「修正後の綺麗なコード」を「過去の changes-requested」
  で fail 扱いし、**Y が壊れる** (時点不一致)。
- 実装: 各 PR で Y を確定した review の `commit_id` を `candidate-rev` にする。
- **baseline 側の罠 (candidate と同格に重要)**: 収集時点の PR object の
  `base.sha` や「現在の base branch に対する naive な merge-base」を使っては
  ならない。マージ済み PR ではレビュー時 SHA が既に現在の main の祖先になって
  いるため、`git merge-base current-main <review-sha>` が **review SHA 自身を
  返し、空 diff / 逆向き diff で配管が誤って成立**しうる。`baseline-rev` は
  **レビュー時点の base を再構築**して固定する: 例えば
  `git rev-list -1 --before=<review_timestamp> <base-branch>` でレビュー時点の
  base tip を取り、その commit と review SHA の merge-base を採る。さらに
  sanity guard を必須化: `baseline-rev != candidate-rev` かつ diff 非空で
  あること (空なら当該 PR を収集エラーとして記録し、黙って通さない)。この
  配管検証は pilot (§2.1) の主要対象。
- 「最初の実質レビュー」の定義: state が `APPROVED` または `CHANGES_REQUESTED`
  を持つ **最初の** review event。純粋な `COMMENTED` (ask なし) は実質レビュー
  に数えない。最初が approve なら pass、最初が CR なら fail (後で approve に
  転じても **最初を取る**)。

### 1.4 D3: target.yaml = A (generic) + B (PR メタ自動生成) の二本立て

**決定: 一次実験で A と B を並走させる。C (盲目手書き) は一次指標に入れない。**

| target | 生成方法 | 測れるもの | 役割 |
|---|---|---|---|
| **A: generic** | 制約ほぼゼロ | 宣言なし時の下限性能 + **vacuous PASS 率** | authoring バイアス 0 のベースライン |
| **B: PR メタ自動生成** | PR タイトル/本文/ラベル/変更ファイル/diff 統計/テスト有無/公開 CI から **固定ルール**で生成 | 実運用 (authoring ゼロ経路) に近い性能 | 主指標の中心 |

- A+B を並べることで「**宣言がないとどれだけ無力か (A)**」「**PR メタから自動
  生成すればどれだけ回復するか (B−A)**」が同時に測れる。後者がプロダクトの
  positioning (推奨2 = authoring ゼロ経路) の直接の証拠。
- **B は固定ルールにする** (甘い生成ルールは fail すべき PR を pass に寄せる =
  recall を自ら毀損)。生成ルールは事前凍結し、誤判定タグ (§1.7) と構造ゲートで
  後から分解可能にしておく。high-recall 化が「それっぽい一致」を拾う
  trade-off は ecosystem の z-gate 実験でも確認済みで、ここでも同型。

### 1.5 D4: leakage 禁止 (B 生成の入力制約)

**決定: target B 生成が使ってよいのは「レビュー前に存在した情報」のみ。**

- 使ってよい: PR タイトル / 本文 / ラベル / 変更ファイル一覧 / diff 統計 /
  テストファイルの有無 / レビュー時点までに公開された CI 結果。
- **使ってはいけない (= leakage)**: reviewer の指摘内容 / 最終 merge・reject /
  修正後 commit / revert 情報。これらは Y (正解) に近い情報なので、入力に
  混ぜると性能が実力より高く見える。
- 注: leakage = 正解ラベルに近い情報が入力側に混ざり、見かけの性能が実力を
  超える現象。本実験の最大の無効化要因。

### 1.6 D5: サンプリング (凍結ルール + class balance)

**決定: 機械的な事前ルールでサンプリングし、pass/fail を 24/24 に近づける。**

- **事前凍結するルール例** (X を見る前に確定): 「対象 repo ≥3 (litellm /
  langgraph / pdm を軸、レビュー文化のある repo)、2025 年以降、Python ファイルを
  実質的に触る (≥1 Python file かつ非自明 diff)、formal review (approve/CR) が
  付いている PR を、時系列順に各 repo から均等に抽出」。
- **除外**: bot 承認 / author==reviewer の self-approval / draft のまま / Python
  を実質触らない PR。
- **class balance**: `CHANGES_REQUESTED` は `APPROVED` より希少なので、pass/fail
  を ~24/24 に近づけるため **stratified sampling** (CR を oversample) する。
  比率が崩れたら主指標で base-rate を補正 (AUROC は不変、F1/MCC は注記)。
- **複数 repo の理由**: 単一 repo だと「そのチームのレビュー文化」が交絡変数に
  なる。≥3 repo で平均化。

### 1.7 D6: C-lite 誤判定タグ (一次指標ではないが必須)

**決定: C (盲目手書き target) は一次指標に入れないが、エラー分析用の C-lite を
入れる。**

- 対象: **`CHANGES_REQUESTED` の全件 + ツール誤判定 (偽陽性・偽陰性) の全件**
  だけに、粗いタグを 1 つ付ける: `API破壊 / テスト欠落 / 仕様不整合 / 複雑度 /
  スタイル・保守性 / その他`。
- 効果: ρ 1 つでなく「**どの種類の drift なら捕まえ、どれを外すか**」の境界が
  残る (例: API破壊は強いがロジック微変更は無力)。これが README「正直な記録」
  と positioning に直結する本当の資産。
- 工数を抑えるため全件はやらない。主観混入には 2 名タグ付け + 一致率併記で対処
  (人員が 1 名なら一致率は将来課題として明記)。

### 1.8 D7: 主指標 = 二値分類メトリクス (ρ は補助)

**決定: Y が二値なので主指標は分類メトリクス。ρ は補助。**

- **主指標**: AUROC / MCC / F1 / 混同行列。特に **偽陰性 (ツール pass・人間 CR =
  見逃し)** を最重要視 (gate としての致命傷)。
- **bootstrap 信頼区間を必ず出す**: N=48 は ecosystem 側の成功条件 (n≥50 で
  ρ≥0.85 等) に対し最低限に近い規模。点推定だけでは断言不能なので CI 必須。
- **補助指標**: Spearman ρ (verdict を pass<repair<fail の順序尺度として) /
  vacuous PASS 率 (target A) / **B による改善幅 (B−A)**。
- verdict は 3 値 (pass/repair/fail) なので、二値化規則を事前凍結:
  `fail → positive(問題あり)`、`pass → negative`、`repair` の扱い (positive 寄せ
  か中間か) を pre-registration で固定。

## 2. 工程 (pilot → 本番)

### 2.1 Pilot (5 件) — 配管確認のみ、性能は語らない

- **目的**: GitHub からの review event 取得 / **レビュー時点 SHA の固定** /
  ラベル・diff 統計抽出 / target A・B 生成 / `semantic-ci check
  --baseline-rev --candidate-rev` 実行 / 集計、の **配管の穴出し**。
- **Pilot の Y は本番と同一 = review-state ベース (§1.2 の D1)** を使う。
  formal review (approve / changes-requested) が付いた PR を 5 件探し、最初の
  実質レビュー時点 SHA (§1.3) で評価する。理由: 5 件時点で「review event 取得・
  レビュー時点 SHA 固定・**レビュー時点 baseline 再構築 (§1.3 の罠) + 空 diff
  sanity guard**・ラベル抽出」の穴を見つけないと本番 48 件で手戻りする。
  **Y を merge/reject で代理しない。target トラック (§1.4 の A/B) は X 生成
  経路であって、いかなる場合も Y (正解ラベル) の代わりにならない。**
- **禁止**: pilot の数字で相関・性能を語ること。pilot は煙試験 (smoke test)。

### 2.2 本番 (N≥48)

1. **pre-registration を凍結** (§3): サンプリング規則 + 分析計画 + verdict 二値化
   + 主指標を、X を見る前に doc/commit で固定。
2. サンプリング規則に従い PR を収集、各 PR の Y と評価時点 SHA を記録。
3. target A・B を leakage 制約下で生成。
4. `semantic-ci check` で X を取得 (A・B 各々)。
5. (X, Y) 表を構築 → 主指標 + bootstrap CI を算出。
6. 偽陽性・偽陰性 + CR 全件に C-lite タグ → 境界分析。
7. 結果を `docs/` の dogfooding tracker / 新 report に記録 (good/bad 両方正直に)。

## 3. Pre-registration (X を見る前に凍結する項目)

これを X 取得前に commit して **事後の都合よい変更を封じる**:

- [ ] サンプリング規則 (対象 repo / 期間 / 言語条件 / 除外条件 / 抽出順)
- [ ] N と class balance 目標 (≥48, ~24/24)
- [ ] Y の定義 (first formal review state, レビュー時点 SHA)
- [ ] target A / B の生成手順 (B の固定ルール全文 + leakage 禁止入力リスト)
- [ ] verdict → 二値化規則 (repair の扱い含む)
- [ ] 主指標 + CI 手法 + 成功/失敗の事前しきい値 (例: AUROC 下側 CI > 0.5)

## 4. 成果物

- **一次成果**: 主指標 (AUROC/MCC/F1/混同行列 + bootstrap CI) + B−A 改善幅 +
  vacuous PASS 率。
- **本当の資産**: 「**どの種類の drift なら効き、どれは原理的に無理か**」の境界
  (C-lite タグ由来)。README「正直な記録」+ positioning の根拠になる。
- **報告**: 既存 `docs/dogfooding_findings_tracker.md` 形式に乗せ、good/bad
  両方を一次資料として残す (過大主張をしない repo 文化を維持)。

## 5. スコープ / 運用上の制約

- **regular session の GitHub MCP scope は本 repo 限定** → 外部 repo の PR
  収集は別アクセス経路 or 別 Claude Code session。STATUS §E-3 が「別 session
  委譲」とする理由。実験コードは `experiments/pr_validation/` に置き再現可能化
  (`experiments/pre_generation_validation/` の前例に倣う)。
- **engine 不変**: 本実験は engine/CLI を変更しない (既存 `check` を回すだけ)。
  §23.1 input neutrality も不変 (real git ref を使うのは CLI 層の既存機能)。
- **規模感**: pilot 5 件 + 本番 48 件 (収集 + ラベリング + A/B target + 集計) で
  数日〜1 週間規模。半日タスクではない。

## 6. Open Questions

- **Q1**: target B の固定ルールの具体形 (どの PR メタ → どの制約。pilot で較正)。
- **Q2**: `repair` verdict の二値化 (positive 寄せか中間か。pre-reg で固定)。
- **Q3**: C-lite タグの単独タグ付けの主観をどう担保するか (2 名困難時の代替)。
- **Q4**: ecosystem の text domain 実験 (HA-style) と指標を揃えるか
  (cross-domain 比較のため ρ も並記する価値)。
- **Q5**: 失敗 (AUROC CI が 0.5 を跨ぐ) 時の解釈 — ツールの限界か target B の
  弱さか Y のノイズか、の切り分け手順。

# Pre-Generation Validation — 観測事例

> **本文書は core scope 外の応用観測例である。** Code Edition v0.1 の設計判断の根拠ではなく、kernel が generic な比較器であることから自然に派生する応用ユースケースの記録。

## 経緯

`code_semantic_ci_design.md` §23.1 は engine の入力 contract を「`baseline_state` / `candidate_state` は実コード抽出 / 仮想 / mock のいずれも可」と規定している。同 §23.4 は含意として「§21.2 pre-generation validation が core engine 機能として直接成立」と述べる。

これらは設計上の主張だが、外部コードベース上で実装が意図通り動くかは検証されていなかった。本観測は外部 Python リポジトリ（kyegomez/OpenMythos `main`）に対して、本実装を伴わない stub のみの candidate を engine に渡し、判定が想定通りに分離するかを 3 ケースで確かめた記録である。

## 実験設定

- baseline: OpenMythos `main` (pristine), `/tmp/openmythos-experiment/baseline/`
- intent: feature 追加（`checkpoint.save_checkpoint` と `checkpoint.load_checkpoint` を user 制約として要求）
- candidate: OpenMythos に新規 stub ファイル `open_mythos/checkpoint.py` を追加した tree。stub の本体はすべて `raise NotImplementedError("pre-generation stub")`
- engine: `semantic-ci compare`（追加実装なし、現行 CLI 経路のみ）

ケース構成:

| ケース | 予測 stub | 既存コードへの変更 |
|---|---|---|
| F1_pass | `save_checkpoint` + `load_checkpoint` 両方を declare | なし |
| F2_missing | `save_checkpoint` のみ declare | なし |
| F3_collateral | `save_checkpoint` + `load_checkpoint` 両方を declare | `LTIInjection.get_A` を `_compute_A` に privatize |

## 観測された判定

| ケース | 期待 | verdict | 違反した制約 |
|---|---|---|---|
| F1_pass | pass | pass ✓ | (4 制約全 satisfied) |
| F2_missing | fail | fail ✓ | user: `load_checkpoint_added` |
| F3_collateral | fail | fail ✓ | template: `feature:no_removed_api` |

3/3 が期待 verdict と一致。各判定は 1 秒未満（0.48〜0.50s）。

## 含意

### 1. §23.1 入力 contract が実装で動作することの直接証明

candidate ディレクトリ内の `checkpoint.py` は本体を一切持たない stub のみだが、extractor は signature を抽出し、engine は CodeState を生成して制約評価を行った。state の出自を engine が問わない設計が、CLI 経路を含めて end-to-end で機能することが確認された。

### 2. 二系統制約の同時動作

`primary_kind: feature` から自動展開される template 制約（`no_removed_api`, `no_new_effects`）と、target.yaml に明示された user 制約（`save_checkpoint_added`, `load_checkpoint_added`）が、同一 verdict 計算内で独立して評価された。F2 は user 制約のみ違反、F3 は template 制約のみ違反というパターンを分離して捕捉できている。これは §4.2「change_kind は制約テンプレート展開器」の機能仕様の動作確認にあたる。

### 3. omission と commission の分離報告

F2 と F3 はいずれも `verdict=fail` だが、違反した制約が異なる:

- F2: 「**やるべきことが足りない**」(omission) → user 制約違反
- F3: 「**余計なことをしている**」(commission) → template 制約違反

repair plan の構造がこの区別を保持するため、計画修正の方向（追加すべきか撤回すべきか）が verdict の出力から直接読める。

### 4. コスト構造の含意

実装着手前の検証コストは < 1 秒（extractor + engine）。生成→テスト→指摘→再生成の往復に対する **予防コスト**としての非対称性が定量例として残った。

## Scope Guard

本文書は応用観測の記録であり、**Code Edition v0.1 の core scope 拡張を提案するものではない**:

- core scope は引き続き「PR の変更意図と実装の整合検査」
- pre-generation validation は §21.2 vibe coding adapter の射程として既に planning 段階にあり、本観測はその前提となる engine 性質の確認に留まる
- adapter 層が解くべき以下の課題は本観測の範囲外:
  1. AI 出力からの stub 自動生成 / 抽出
  2. intent.yaml の対話的構築支援
  3. 計画修正フィードバックの AI への自然言語化

`CLAUDE.md` の scope guard（linter じゃない、type checker じゃない、test runner じゃない、LLM-as-judge じゃない）は維持する。

## 残された問い

1. **stub と本実装の signature 乖離**: stub と本実装で signature がずれた場合、生成後の compare で初めて捕まる。pre-generation 検証が保証するのは計画レベルの整合性のみ。
2. **stub 自動生成の品質**: 本観測では人間が stub を手書きした。AI agent による予測 stub 生成の精度評価は別実験。
3. **api_surface 以外の slice での pre-generation**: 今回は `api_surface_delta.added` のみを user 制約に乗せた。`effects`、`type_relations`、`module_graph` での pre-generation 制約宣言の運用例は未検証。
4. **専用 subcommand の必要性**: 現状は `compare` を流用しているが、`semantic-ci validate-plan` のような明示的なエントリポイントの導入是非は別途判断。

## 再現

実験スクリプトとケースデータは隔離環境（`/tmp/openmythos-experiment/`）に保管。リポジトリ本体には影響しない。

```bash
# baseline = pristine OpenMythos main を /tmp/openmythos-experiment/baseline/ に展開済み
python /tmp/openmythos-experiment/run_pregen.py
# 期待出力: 3/3 verdicts matched expectation
```

ケースは `cases_pregen/F{1,2,3}_*/candidate/` に毎回 fresh build される（冪等）。

## 出典

本観測は 2026-05-05 の壁打ちセッション中に実行された。本文書は事後の整理であり、実験記録ではない（実行ログ全文・stub ソース・verdict.json は本文書に収録せず、再現スクリプトのみで再生可能とする）。

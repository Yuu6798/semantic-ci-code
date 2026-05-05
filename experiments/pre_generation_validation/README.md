# Pre-Generation Validation Reproduction

Self-contained reproduction for the observation recorded in
[`docs/pre_generation_validation_case.md`](../../docs/pre_generation_validation_case.md).

## What this verifies

`docs/code_semantic_ci_design.md` §23.1 規定の engine 入力 contract:

> `baseline_state` / `candidate_state` は実コード抽出 / 仮想 / mock のいずれも可

を、本実装を伴わない stub のみの candidate に対して `semantic-ci compare` が
想定通りに verdict を分離するかで実証する。

## Cases

| ケース | 予測 stub | 既存コードへの変更 | 期待 verdict |
|---|---|---|---|
| `F1_pass` | `save_counter` + `load_counter` 両方を declare | なし | `pass` |
| `F2_missing` | `save_counter` のみ declare | なし | `fail` |
| `F3_collateral` | `save_counter` + `load_counter` 両方を declare | `Counter.increment` を `_bump` に privatize | `fail` |

stub 本体はすべて `raise NotImplementedError("pre-generation stub")` のみ。
engine から見れば実装由来か予測由来かを区別できない設計が機能していることの確認。

## Running

```bash
pip install -e ".[dev]"   # install semantic-ci if not already
python experiments/pre_generation_validation/run.py
```

期待出力:

```
3/3 verdicts matched expectation
```

exit code は 3/3 一致時 `0`、そうでなければ `1`。スクリプトは
`tempfile.TemporaryDirectory` を使用し、副作用なし・network 不要・stdlib のみで動作。

## Files

```
experiments/pre_generation_validation/
├── README.md                  # this file
├── baseline/
│   └── tinypkg/
│       ├── __init__.py        # re-exports Counter
│       └── counter.py         # ~25 行の minimal public API
└── run.py                     # 3 ケースの orchestrator (idempotent)
```

`baseline/tinypkg/` は実用パッケージではなく、本実験が要求する最小の API surface を
提供するためだけの合成コードベース。`Counter` クラス 1 つ・public method 2 つ
(`increment`, `value`) が定義されている。

## Scope

本実験は engine の入力 contract が virtual state を受け付けることの **存在証明**で
あって、pre-generation validation の adapter 層 (P2.5 vibe coding adapter) を
実装しているわけではない。AI 出力からの stub 自動生成、intent 対話的構築、修正
フィードバックの自然言語化は本実験の範囲外。

詳細な背景・含意・限界は親文書 [`docs/pre_generation_validation_case.md`](../../docs/pre_generation_validation_case.md)
を参照。

# Brief 8 Planning — Authoring Surface (target.yaml provenance neutrality 実装)

> **Status: PLANNING (open)**.
>
> Brief 5(Vibe Coding Adapter + Repair Compiler、P2.5 entry)で確立した
> **§23.3 surface 区分**(Validator / Authoring / Provenance / Advisor)のうち、
> 実装が `init` scaffold 1 点だけにとどまっている **Authoring + Advisor +
> Provenance** の 3 surface を実コマンドに展開する brief。
>
> 設計動機は session 2026-05-09 の議論で確定した次の最終決定:
>
> > target.yaml の難解さは Semantic CI core の本質的欠陥ではない。
> > core は declared intent に対する adherence を決定論的に判定する Validator
> > であり、intent の正しさ・完備性・作者の真意は判定しない。
> >
> > 改善対象は target.yaml を書く前後の Authoring / Advisor / Provenance
> > surface である。target.yaml は人間手書きである必要はなく、recipe、template、
> > PR metadata、commit message、label、外部 AI assistant などから生成してよい。
> > ただし、生成結果は verdict 前に明示的な declared intent として固定され、
> > 生成経路・provenance・advice は evaluator に参加してはならない。
>
> Brief 7(SSP v0.1)とは **disjoint な surface**(SSP は core の隣の独立 protocol、
> Brief 8 は core の入口側の Authoring surface)であり、**並列発行可能**。
> ただし発行順は §13 で議論する。

## 位置付け

`docs/code_semantic_ci_design.md §23.3.1` の Adjacent surfaces 表に対する
**実装側のキャッチアップ**。設計上は 2026-05-04 時点で 4 surface の境界が
確定しており、`§23.3.2` で各 surface の不可侵制約も明記されているが、
実装は以下の状態:

| Surface | 設計上の許可 | 実装の現状 |
|---|---|---|
| **Validator** | core engine | 完全実装(Brief 1〜5 で完走) |
| **Authoring** | target.yaml 形式の作成支援 | `semantic-ci init` の skeleton 出力**だけ** |
| **Provenance** | intent の declared 経路記録 | `authorship` block の **parse のみ**、生成 metadata の自動記録は無し |
| **Advisor** | intent 周辺情報の human 向け配信 | `validate-plan` / `compile-repair` の repair guidance のみ。authoring hazard の advisor 化は未実装 |

session 2026-05-08 で `docs/target_yaml_guide.md` を新設し D1〜D5 を
authoring hazard として **文書化**したが、ガイドを読まないと回避できない
状態は **設計が許容している surface を実装で塞いでいる**ことの裏返し。
本 brief はその surface ギャップを埋める。

## 1. 救済される未解決項目

| 出典 | 項目 | 本 brief での扱い |
|---|---|---|
| `docs/target_yaml_guide.md` D1(`--package-root` scope vs `tests/`) | authoring hazard の機械化 | **CSCI-43** target-doctor の ADVISORY-D1 として検出 |
| `docs/target_yaml_guide.md` D3(template と user constraint の重複) | 同上 | **CSCI-43** target-doctor の ADVISORY-D3 として検出 |
| `docs/target_yaml_guide.md` D4(config-only PR の vacuous PASS) | 同上 | **CSCI-43** target-doctor の ADVISORY-D4 として検出 |
| `docs/target_yaml_guide.md` D5(set operator partial-match) | PR #65 で **Validator 側で解消済**。本 brief では target-doctor が `partial record` 構文の旧誤用を ADVISORY として教える | **CSCI-43** ADVISORY-D5(legacy form) |
| 設計 §23.3.1 Authoring surface | scaffold だけでは authoring 行為(constraint DSL 落とし込み)を支援しきれない | **CSCI-42** init `--recipe` で recipe-driven 生成へ昇格 |
| 設計 §23.3.1 Provenance surface | `authorship.generation_metadata` を parse するが書き出しコマンドが無い | **CSCI-45** draft-target が generation_metadata を自動記録 |
| 設計 §23.3.1 Advisor surface | 既存 `validate-plan` は target.yaml が**正しく書かれている**前提。書く前段階の advisor が無い | **CSCI-43** target-doctor + **CSCI-44** target-catalog で穴埋め |
| session 2026-05-09 議論 | 「target.yaml は人間手書きである必要はない」を **設計文書に明記**する必要 | **CSCI-41**(docs)で `docs/target_authoring_surface.md` 新設 + 既存 docs cross-ref |

## 2. Goals

1. **§23.3.1 surface 境界を実装まで貫徹**: Authoring / Provenance / Advisor
   surface が verdict path に **絶対に介入しない**ことを CLI subcommand 単位で
   構造的に保証する(後述 §7 の不変条件 5 つ)。
2. **target.yaml 生成経路を 4 つに拡張**:
   - 手書き(現行)
   - **recipe**(`init --kind <K> --recipe <R>` から決定論的生成)
   - **draft**(`draft-target` が PR metadata 等から作る draft、要人手確認)
   - **catalog 参照**(AI assistant / IDE / 外部 tool が `target-catalog` の
     機械可読出力を見て生成する)
3. **authoring hazard を Advisor 化**: D1 / D3 / D4 / D5(legacy)
   + positive expectation 欠落 + severity downgrade 等を
   `target-doctor` で検出、verdict は変えない(exit code 0、`--strict-advice`
   は authoring workflow policy として別軸)。
4. **compile を authoring 用に強化**: `compile --explain` で「この target が
   実際に何を gate するか」を template 展開含めて説明。
5. **Provenance metadata の自動記録**: `draft-target` が `authorship.
   generation_metadata` を逐語で書き、`candidate_code_used: false` を default
   にする。
6. **決定論性の維持**:
   - recipe / catalog / doctor は **完全決定論**(LLM / network 不使用)
   - draft-target は LLM をオプションで使用可だが **verdict path には流れない**
     (生成物は user 確認後 file に固定 → engine はそれを declared intent
     として読む)
7. **`semantic-ci check` の挙動を一切変更しない**: 既存 envelope schema /
   exit code / verdict 計算は本 brief で触らない(§7 不変条件 #1)。

## 3. Non-goals(本 brief 範囲外)

- **`semantic-ci check --auto-target`** — `check` 内で target を生成する経路は
  作らない(§23.3 違反、§7 不変条件 #2 で排除)。
- **candidate code から expected constraint を無条件生成** — `draft-target`
  の default は `candidate_code_used: false`。opt-in flag は **本 brief では
  実装しない**(別 brief で安全策込みで議論)。
- **任意 Python 式 / 独自 DSL** — `target.yaml` は YAML + typed operator の
  ままにする(設計 §4 不変)。「authoring が難しいから DSL を自由化」は本
  brief で却下する選択肢として §3 に明記。
- **LLM-as-judge** — `target-doctor` の advisory 計算は完全決定論。LLM は
  `draft-target` でのみ optional 使用可。
- **intent の正しさ判定** — target-doctor は authoring hazard を出すが、
  「この intent は正しい/間違っている」は判定しない(設計 §23.3.3)。
- **non-Python artifact gating** — config / docs / workflow 専用の意味検証は
  Brief 7(SSP)/ 別 protocol の責務。本 brief では `target-doctor` が D4
  vacuous PASS を **advisory として教える**だけにとどめる。
- **新たな constraint kind / operator** — 本 brief は authoring 経路の整備
  であり、constraint DSL 自体は不変。
- **TypeScript / 多言語 catalog** — Brief 6 凍結に従い Python のみ。
  `target-catalog` の出力スキーマは多言語拡張を想定して設計するが、Python
  以外の populate は本 brief で行わない。
- **GitHub App / Action 化** — Brief 8 完了後、別 brief でパッケージング。

## 4. アーキテクチャ全体像

```
┌──────────────────────────────────────────────────────────┐
│  authoring-time(verdict 不参加、§23.3.1)                │
│                                                          │
│   PR body ──┐                                           │
│   commits ──┼──▶ draft-target ─┐                       │
│   labels ──┘   (CSCI-45)        │                       │
│                                  │                       │
│   user input ──▶ init --recipe ──┼──▶ target.yaml      │
│                  (CSCI-42)        │   (declared intent) │
│                                   │                       │
│   AI assistant ──▶ target-catalog ┤                       │
│                    (CSCI-44, JSON)│                       │
│                                   │                       │
│   target.yaml ──▶ target-doctor ──┘ (ADVISORY のみ)       │
│                   (CSCI-43)                              │
│                                                          │
│   target.yaml ──▶ compile --explain (CSCI-46)            │
│                   (compile 拡張、authoring readback)     │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼ ★ verdict 入口で固定
┌──────────────────────────────────────────────────────────┐
│  verdict-time(Validator surface、§23.1 / §23.3 不可侵) │
│                                                          │
│   target.yaml + baseline + candidate                     │
│      ──▶ check / compare / validate-plan / compile-repair│
│                  (Brief 1〜5 で完走、本 brief で不変)   │
└──────────────────────────────────────────────────────────┘
```

### 4.1 責務分離(本 brief 内 surface 配属)

| CSCI | 追加 surface | 役割 | verdict 関与 |
|---|---|---|---|
| CSCI-41 (docs) | (docs) | §23.3.1 surface 区分の **設計文書側追記** + cross-ref | NO |
| CSCI-42 init `--recipe` | Authoring | recipe + user input → target.yaml(決定論) | NO |
| CSCI-43 target-doctor | Advisor | target.yaml の hazard を render(verdict 不変) | NO |
| CSCI-44 target-catalog | Authoring(meta) | target / operator / template / match schema を機械可読出力 | NO |
| CSCI-45 draft-target | Authoring | PR metadata 等 → target.yaml draft + provenance 記録 | NO |
| CSCI-46 compile `--explain` | Authoring readback | compile 既存出力を authoring 用に説明強化 | NO |

#### 4.1.1 surface invariant の test での担保

各 CSCI は acceptance criteria に以下を**必ず含める**:

- **不変条件テスト**: 当該 subcommand を経由しても `check` / `compare` /
  `validate-plan` / `compile-repair` の verdict 出力が **byte-identical**
  であることを、共通 fixture で確認する(§7 不変条件 #1 の回帰)。
- **provenance 非参照テスト**: target.yaml に generation_metadata を
  書き換えても verdict envelope が変わらないことを確認(§7 不変条件 #3)。

## 5. CSCI 分割

合計 6 PR、おおむね各 0.5〜1.5 日。Brief 5 と同サイズ感。

### 5.1 CSCI-41 (P0): 設計文書追記

**Goal**: target.yaml が hand-written 必須でないことを設計側で固定し、
今後の実装判断の前提を明文化する。

**追加 / 変更ファイル**:

- `docs/target_authoring_surface.md` (NEW): §23.3.1 を実装側から再記述。
  「declared intent は固定入力であり、生成経路は engine の関知外」を中心に、
  recipe / draft / catalog / hand-written の 4 経路を一覧化。
- `docs/target_yaml_guide.md` (UPDATE): 冒頭に「target.yaml は人間が直接
  書く前提ではない」「複数の authoring 経路が許容されている」を pin、
  D1〜D5 の章末に「target-doctor で機械化予定」cross-ref を追記。
- `docs/code_semantic_ci_design.md §23.3.1` (UPDATE): Adjacent surfaces 表に
  `init --recipe` / `target-doctor` / `target-catalog` / `draft-target` /
  `compile --explain` を追記、各々が verdict 不参加であることを脚注で明記。
- `CLAUDE.md` Required Reading 章 (UPDATE): Brief 8 着手前に
  `docs/target_authoring_surface.md` を読むよう追加。
- `README.md` (UPDATE): documentation 一覧に新規 doc を追加。
- `docs/cli_usage.md` (UPDATE): 「Authoring subcommands(verdict 不参加)」
  という新節を追加(具体的内容は CSCI-42〜46 で順次埋める、CSCI-41 では
  節見出しと §23.3.1 への cross-ref のみ)。

**Acceptance criteria**:

- [ ] `docs/target_authoring_surface.md` が以下 5 点を明記:
  (a) target.yaml は hand-written 必須でない
  (b) 生成経路の 4 通り(recipe / draft / catalog 参照 / hand-written)
  (c) 全経路は verdict 前に declared intent として固定される
  (d) Authoring / Advisor / Provenance surface は evaluator から参照不可
  (e) candidate-derived expectation は默認禁止、opt-in でも provenance
      `candidate_code_used: true` を必ず記録する
- [ ] CLAUDE.md docs table に新規 doc が status `ACTIVE` で登録
- [ ] `ruff check .` / `pytest -q` 通過(コード変更なし、docs only)

**Surface**: docs only。実装変更なし。
**Brief size**: 0.5 日。

### 5.2 CSCI-42 (P1): `semantic-ci init --kind --recipe`

**Goal**: 現行 `init` の skeleton 出力を壊さずに、recipe mode を追加する。
recipe は決定論的(LLM / network 不使用)で、ユーザー指定値から明示
constraint を生成する。

**追加 / 変更ファイル**:

- `src/semantic_ci_code/cli/init_command.py` (UPDATE): `--kind` /
  `--recipe` / `--add-api` / `--test-case` / `--remove-api` /
  `--allowed-import` 等の引数を追加。recipe registry を呼び出して YAML を
  build。
- `src/semantic_ci_code/cli/init_recipes/` (NEW directory):
  - `__init__.py`: `RECIPES` dict、`apply_recipe()` entry point
  - `feature_add_api.py`: `feature:add-api` recipe
  - `bugfix_regression_test.py`: `bugfix:regression-test`
  - `refactor_preserve_api.py`: `refactor:preserve-api-with-allowlist`
  - `test_update_add_or_change.py`: `test-update:add-or-change-test`
- `src/semantic_ci_code/cli/main.py` (UPDATE): `init` subparser に新引数。
- `tests/cli/test_init_recipe.py` (NEW): 各 recipe で生成される YAML が
  expected と byte-identical(determinism)、生成 YAML が `compile` を
  pass する、`check` の verdict 出力が hand-written と recipe で
  byte-identical(同一 intent を表現する場合)。

**Recipe 仕様(初期 4 件)**:

| Recipe ID | 必須引数 | 生成される positive expectation |
|---|---|---|
| `feature:add-api` | `--add-api FQN+`, optional `--test-case FQN*` | `api_surface_delta.added.fqns includes_all [FQN…]`, `test_surface_delta.new_cases not_equals []` (test-case 指定時) |
| `bugfix:regression-test` | optional `--test-case FQN*` | `test_surface_delta.new_cases not_equals []`, template により `api_surface_delta.removed_public == []` |
| `refactor:preserve-api-with-allowlist` | optional `--allow-add FQN*`, `--allow-remove FQN*` | `api_surface_public.equals_baseline` を allowlist で緩和 |
| `test-update:add-or-change-test` | optional `--test-case FQN*` | `test_surface_delta.changed_or_added not_equals []` |

各 recipe は `change.primary_kind` を必ず設定し、template 展開は engine
側に委ねる(本コマンドは template constraint を **重複生成しない** ——
これが ADVISORY-D3 を踏まないための実装側保証)。

**Acceptance criteria**:

- [ ] 4 recipe すべてが決定論的(同 input → byte-identical YAML、3 回繰返
      テスト)
- [ ] 生成 YAML は `compile` を pass(構文 / path / operator すべて妥当)
- [ ] `init` の既存 behavior(引数なし呼び出し)は不変、既存テスト全 pass
- [ ] LLM / network 呼び出しゼロ(`tests/cli/test_init_recipe.py` で
      `socket` mock を入れて確認)
- [ ] template と user constraint の重複が起きない(ADVISORY-D3 が空に
      なる、CSCI-43 land 後の cross-test で確認、本 PR では unit-level で
      重複ゼロを assert)

**Brief size**: 1〜1.5 日。

### 5.3 CSCI-43 (P2): `semantic-ci target-doctor`

**Goal**: target.yaml の authoring hazard を Advisor として render する
新 subcommand。verdict は変えない(exit code 既定 0、`--strict-advice`
で authoring workflow policy として fail にできる)。

**追加 / 変更ファイル**:

- `src/semantic_ci_code/cli/commands/target_doctor.py` (NEW)
- `src/semantic_ci_code/cli/main.py` (UPDATE): subparser 追加
- `src/semantic_ci_code/authoring/` (NEW): advisory 検出ロジック
  - `__init__.py`
  - `hazards.py`: 各 hazard 検出関数(D1 / D3 / D4 / D5-legacy / P1 /
    P2 / S1)
  - `advisory.py`: `Advisory` dataclass(`code`, `severity`,
    `message`, `evidence`)
- `src/semantic_ci_code/cli/output/doctor_human.py` (NEW)
- `src/semantic_ci_code/cli/output/doctor_json.py` (NEW)
- `tests/cli/test_target_doctor.py` (NEW)

**検出する advisory 一覧**:

| Code | 概要 | 入力 |
|---|---|---|
| `ADVISORY-D1` | `test_surface_delta.*` constraint exists, but `--package-root` does not include `tests/` | target.yaml + package-root |
| `ADVISORY-D3` | user constraint duplicates a template-expanded constraint | target.yaml + change.primary_kind |
| `ADVISORY-D4` | target is lock-only / config-only and candidate diff is config/doc/workflow only; PASS would be vacuous | target.yaml + baseline-rev + candidate-rev |
| `ADVISORY-D5-LEGACY` | bare-string element used where Match Schema expects record (旧 schema_version="4" 形式) | target.yaml |
| `ADVISORY-P1` | `primary_kind=feature` but no positive addition constraint | target.yaml |
| `ADVISORY-P2` | `primary_kind=bugfix` but no `test_surface_delta.new_cases` expectation | target.yaml |
| `ADVISORY-S1` | hard constraint downgraded to info; will not affect verdict | target.yaml |

**CLI**:

```
semantic-ci target-doctor \
  --target .semantic-ci/target.yaml \
  [--package-root .] \
  [--baseline-rev origin/main] \
  [--candidate-rev HEAD] \
  [--format human|json] \
  [--strict-advice]
```

**Exit code 規約**:

| 条件 | 既定 | `--strict-advice` |
|---|---|---|
| advisory 0 件 | 0 | 0 |
| advisory ≥ 1 件 | **0** | 1 |
| 内部エラー | 4 | 4 |

`--strict-advice` の挙動は **`authoring workflow policy`** であって engine
verdict ではない、を `docs/exit_codes.md` に明記する(`--strict-repair`
と同等の独立 lever)。

**Determinism**:

- D1〜D5-LEGACY は target.yaml 単独で決定論
- D4 は git diff numstat に依存 → 同 baseline / candidate rev で
  byte-identical
- LLM / network 不使用

**Acceptance criteria**:

- [ ] 7 advisory 全種が unit テスト fixture で検出される
- [ ] 各 advisory が detect されない fixture(false positive 防止)も持つ
- [ ] `--format json` 出力が `schema_version="advisory-1"` で安定
      (envelope 仕様は §6 で固定)
- [ ] target-doctor を実行しても `check` / `compare` の verdict envelope は
      byte-identical(§7 不変条件 #1 回帰テスト)
- [ ] `--strict-advice` 無し時は exit code 0、有り時のみ 1
- [ ] determinism test(同 input 3 回 → byte-identical)

**Brief size**: 1.5 日。

### 5.4 CSCI-44 (P3): `semantic-ci target-catalog`

**Goal**: target / operator / template / match schema / change_kind を
機械可読 + human readable で出す Advisor surface コマンド。
AI assistant、IDE 拡張、外部 authoring tool が target.yaml を**正しく
生成するため**の reference。

**追加 / 変更ファイル**:

- `src/semantic_ci_code/cli/commands/target_catalog.py` (NEW)
- `src/semantic_ci_code/cli/main.py` (UPDATE): subparser
- `src/semantic_ci_code/authoring/catalog.py` (NEW): 既存
  `compiler/templates.py` / `framework/match_schema.py` /
  `evaluator/operators.py` / `framework/extract_config.py` から catalog を
  build
- `src/semantic_ci_code/schemas/target_catalog.schema.json` (NEW):
  catalog 出力 JSON schema
- `tests/cli/test_target_catalog.py` (NEW)

**CLI**:

```
semantic-ci target-catalog [--format json|human] [--kind feature|...]
                           [--target-path api_surface_delta.added]
```

**JSON 出力(抜粋)**:

```json
{
  "schema_version": "catalog-1",
  "primary_kinds": ["feature", "bugfix", "refactor", "test_update"],
  "targets": {
    "api_surface_delta.added": {
      "kind": "delta",
      "collection": "record",
      "match_schema": {
        "required_key": "fqn",
        "optional_keys": ["signature", "module"]
      },
      "operators": ["includes_all", "includes_any", "excludes_all",
                    "subset_of", "superset_of", "not_equals"]
    },
    "imports_delta.added.modules": {
      "kind": "delta",
      "collection": "string",
      "operators": ["includes_all", "excludes_all"]
    }
  },
  "templates": {
    "feature": {
      "expanded_constraints": [
        "api_surface_delta.removed_public == []",
        "effect_changes.added == []"
      ]
    }
  },
  "operators": {
    "includes_all": {
      "applies_to_collection": ["string", "record"],
      "evidence_emits": ["matched", "missing"]
    }
  }
}
```

**Determinism**:

- 出力は完全に静的(現行コードの定義集計)、LLM / network 不使用
- ordering は alphabetical(JSON key / array)、再生性 byte-identical

**Acceptance criteria**:

- [ ] catalog の JSON schema が `schemas/` に登録され、出力が schema valid
- [ ] catalog に登録された target / operator が evaluator 実装と一致する
      ことを **cross-test**(`evaluator/operators.py` の登録 dict と
      catalog 出力を比較)
- [ ] `--kind feature` で template 展開が想定通り
- [ ] determinism test、verdict 不変条件テスト
- [ ] human format が target.yaml authoring user(人間)に読める粒度

**Brief size**: 1 日。

### 5.5 CSCI-45 (P4): `semantic-ci draft-target`

**Goal**: PR metadata から target.yaml の **draft** を生成する。
candidate code 由来の expectation を default で禁止し、provenance を必ず
記録する。LLM はオプション(後述 source 別の方針)。

**追加 / 変更ファイル**:

- `src/semantic_ci_code/cli/commands/draft_target.py` (NEW)
- `src/semantic_ci_code/cli/main.py` (UPDATE)
- `src/semantic_ci_code/authoring/draft.py` (NEW): source 別 parser
  - `from_pr_body(text) -> partial intent`
  - `from_commits(messages) -> partial intent`
  - `from_labels(labels) -> primary_kind`
  - `merge(*partials) -> target.yaml dict`
- `src/semantic_ci_code/authoring/provenance.py` (NEW):
  `build_generation_metadata()` ユーティリティ
- `tests/cli/test_draft_target.py` (NEW)

**CLI**:

```
semantic-ci draft-target \
  [--from-pr-body pr.md] \
  [--from-commits commits.txt] \
  [--from-labels labels.json] \
  [--from-issue issue.md] \
  [--add-api FQN]* [--test-case FQN]* \
  [--llm-assist {off,advisory,full}]  # default: off
  [--output .semantic-ci/target.yaml]
```

**Source 強度ポリシー**:

| Source | 強さ | 役割 |
|---|---|---|
| `--add-api` / `--test-case`(明示 user input) | strong | positive expectation の確定値 |
| labels(`kind:feature` 等) | strong | `change.primary_kind` 決定 |
| PR body の structured section(`## Expected public API`) | strong | positive expectation のヒント |
| issue acceptance criteria | medium | hint |
| commit message | medium | hint |
| PR title | medium | hint |
| **candidate code body / observed semantic delta** | **forbidden by default** | tautology 化リスクのため `--allow-candidate-derived-expectations` opt-in は **本 brief では実装しない**(別 brief に送り) |

**LLM 使用方針**:

- `--llm-assist off`(default): 完全決定論、natural language は structured
  section parser でのみ拾う(例: `## Expected public API\n- foo\n- bar`)。
- `--llm-assist advisory`: LLM を呼ぶが**生成は draft.advisory_hints
  field のみ**に書き、constraint には反映しない。Provenance に
  `llm_used: true, llm_role: "advisory"` を記録。
- `--llm-assist full`: LLM が constraint 候補を提案。**user の手で確認・
  編集することを前提**とし、生成 file には常に `# DRAFT — review before
  use` を冒頭 comment として書く。Provenance に `llm_used: true,
  llm_role: "constraint_proposer"` を記録。

**重要**: いずれの mode でも生成 file は **最終 declared intent ではなく
draft**。verdict は別途 `check` を呼ばないと出ない。**`draft-target` は
`check` を呼ばない**(§7 不変条件 #2 を物理的に保証)。

**Provenance metadata**(必ず生成):

```yaml
authorship:
  declared_at: "2026-05-09T12:00:00Z"
  generation_metadata:
    tool: semantic-ci-draft-target
    tool_version: "0.x.y"
    source_surfaces:
      - pr_body
      - commit_messages
      - labels
    candidate_code_used: false
    llm_used: false
    llm_role: null
```

`candidate_code_used` field の存在自体が §23.3 の Provenance Invariant を
**運用側で可視化**する(false にせざるを得ない設計が tautology を防ぐ)。

**Acceptance criteria**:

- [ ] `--llm-assist off` で完全決定論(同 input 3 回 → byte-identical)
- [ ] 生成 YAML が `compile` を pass(構文 / path)
- [ ] generation_metadata が必ず書かれる(`candidate_code_used` 含む)
- [ ] `draft-target` は `check` / `compare` / `validate-plan` /
      `compile-repair` を**一切呼ばない**(import / call graph を unit テスト
      で確認、§7 不変条件 #2 物理保証)
- [ ] `--llm-assist full` 時、生成 file 冒頭に `# DRAFT — review before use`
      が必ず付く
- [ ] `--allow-candidate-derived-expectations` フラグは **存在しない**
      (本 brief で実装しないことを test で確認)
- [ ] verdict 不変条件テスト(§7 #1)

**Brief size**: 1.5〜2 日(LLM 経路実装含む。`--llm-assist off` のみで
land する option も §13 で議論)。

### 5.6 CSCI-46 (P5, optional): `semantic-ci compile --explain`

**Goal**: 現行 `compile` の normalized output を、authoring 用に説明強化。
template 展開結果 + effective gate + positive expectation の有無 +
hazard hint を human-readable に出す。

**追加 / 変更ファイル**:

- `src/semantic_ci_code/cli/commands/compile.py` (UPDATE): `--explain`
  flag、`--format human` 時のみ explain 拡張
- `src/semantic_ci_code/cli/output/compile_explain.py` (NEW)
- `tests/cli/test_compile_explain.py` (NEW)

**CLI**:

```
semantic-ci compile --target target.yaml --format human --explain
```

**出力例**:

```
Primary kind: feature

Template constraints (auto):
  - template:feature:no_public_api_removed
  - template:feature:no_new_effects

User constraints:
  - feature_added (hard)
  - regression_test_added (hard)

Effective gate:
  hard: 4   soft: 0   info: 0

Positive expectations:
  - api_surface_delta.added includes src.api.users.fetch_user_profile
  - test_surface_delta.new_cases != []

Potential hazards:
  - run `semantic-ci target-doctor` for details
```

**Determinism / Surface**:

- 完全決定論、現行 compile の出力を上書きしない(`--explain` 無し時の
  output は既存 byte-identical)
- Authoring readback surface = verdict 不参加

**Acceptance criteria**:

- [ ] `--explain` 無し時の `compile` 出力は既存と byte-identical(後方互換)
- [ ] `--explain` 有り時、上記 5 セクション(primary_kind / template /
      user / gate / positive expectations)が必ず render される
- [ ] verdict 不変条件テスト

**Brief size**: 0.5〜1 日。 **本 brief 内 optional**。CSCI-43 target-doctor が
landing した後でも、user 観点で重複情報になる場合は CSCI-46 を defer 可。

## 6. Schema / envelope 影響

新規 envelope:

| Envelope | Schema version | Surface | 関連 CSCI |
|---|---|---|---|
| `target-doctor` advisory output | `advisory-1` | Advisor | CSCI-43 |
| `target-catalog` reference output | `catalog-1` | Authoring meta | CSCI-44 |
| `draft-target` output | (target.yaml そのもの、既存 schema) | Authoring | CSCI-45 |
| `compile --explain` | (compile envelope は不変、`--explain` は human format のみ) | Authoring readback | CSCI-46 |

既存 envelope の schema_version は **bump しない**:

- verdict envelope: `"5"`(PR #65 で確定、本 brief 不変)
- compile envelope: `"5"`(同上)
- compile-repair envelope: `"1"`(不変)
- validate-plan envelope: `"1"`(不変)

`docs/json_schema.md` には新規 envelope 2 つを追記し、それぞれ独立
schema として `schemas/` に登録する。**verdict envelope と混ざらない**
(SSP envelope 設計と同じ思想、`docs/brief_7_planning.md §6` の鏡像)。

## 7. Determinism / surface invariants

実装で**構造的に保証する**5 つの不変条件:

1. **Verdict bytes invariant**:
   `check` / `compare` / `validate-plan` / `compile-repair` の JSON envelope
   は本 brief の全変更後も既存 fixture で byte-identical。
   → CSCI-42〜46 すべての acceptance に「verdict 不変条件テスト」を含める。

2. **`check` does not generate target invariant**:
   `check` 経路から `init` / `target-doctor` / `target-catalog` /
   `draft-target` のいずれの module も import されない。
   → import-graph test を `tests/architecture/test_surface_isolation.py`
   (NEW、CSCI-43 で初出)で固定。

3. **Provenance non-participation invariant**:
   target.yaml の `authorship.generation_metadata` を任意に書き換えても
   verdict envelope は byte-identical。
   → fixture を 1 つ作り、generation_metadata の有無 / 値違いで verdict
   を回し、出力 hash を比較する。

4. **No-LLM-in-verdict invariant**:
   `check` 経路で `httpx` / `requests` / 外部 API client を **import しない**。
   既存だが本 brief で再確認。`draft-target --llm-assist {advisory,full}`
   は `draft-target` 経路でのみ LLM を呼ぶ。

5. **Catalog ↔ implementation parity invariant**:
   `target-catalog` の出力に登録された operator / target / template が
   evaluator 実装と一致する。
   → `tests/cli/test_target_catalog.py` で cross-test。

これら 5 不変条件は **本 brief 完了の必要十分条件**であり、各 CSCI の
acceptance には対応する不変条件番号を明記する。

## 8. CLI surface 全体像(after-state)

```
semantic-ci
├── observe         (Validator: 単発観測)
├── compare         (Validator: 任意 2-rev 比較)
├── check           (Validator: PR モード)
├── pre-commit      (Validator: pre-commit 連携)
├── compile         (Validator readback / Authoring readback with --explain)
├── compile-repair  (Advisor: repair guidance)
├── validate-plan   (Advisor: pre-generation guidance)
├── init            (Authoring: scaffold + recipe)        ★ recipe 拡張
├── target-doctor   (Advisor: authoring hazard)           ★ NEW
├── target-catalog  (Authoring meta: machine-readable ref)★ NEW
└── draft-target    (Authoring: PR metadata → draft yaml)★ NEW
```

合計 11 subcommand(現在 8 + 新規 3、`init` は拡張)。
**Validator 5 / Advisor 2 / Authoring 4** で surface バランスが取れる。

## 9. テスト戦略

### 9.1 各 CSCI 単位

- **unit**: hazards / recipes / catalog builder / draft parser を関数単位
- **CLI integration**: 各 subcommand の golden fixture
- **determinism**: 同 input 3 回呼び出して byte-identical
- **schema valid**: 各 JSON 出力が JSON schema 通過

### 9.2 Brief 全体で要求する横断テスト(`tests/architecture/` 新設)

- `test_surface_isolation.py`: §7 不変条件 #2 / #4 の import-graph 検査
- `test_verdict_bytes_invariant.py`: §7 不変条件 #1 / #3 の golden hash
- `test_catalog_implementation_parity.py`: §7 不変条件 #5

`tests/architecture/` ディレクトリ自体は本 brief で初出(CSCI-43 で
作成、後続 CSCI で追加)。Brief 7 が後続で SSP envelope を分離する際にも
同ディレクトリの不変条件 test pattern が再利用できる(envelope 分離は
両 brief 共通の関心)。

### 9.3 Dogfooding

CSCI-45(draft-target)land 後、`docs/dogfooding_TC10_report.md` の
TC1〜TC10 を **draft-target で再生成して `compile` を pass するか** を
小規模 dogfood として実施し、本 brief 内の最終 PR(CSCI-45 か CSCI-46)
で記録する。

## 10. Brief 全体 Acceptance Criteria

- [ ] CSCI-41〜45 全 PR が merged(CSCI-46 は optional defer 可)
- [ ] §7 不変条件 5 件すべてが test で固定されている
- [ ] `docs/target_authoring_surface.md` が新設、CLAUDE.md docs table に
      ACTIVE で登録
- [ ] `docs/cli_usage.md` に新規 3 subcommand + `init --recipe` +
      (CSCI-46 land 時) `compile --explain` のセクションが追加
- [ ] `docs/exit_codes.md` に `--strict-advice`(target-doctor)が
      authoring workflow policy として明記される
- [ ] `docs/json_schema.md` に `advisory-1` / `catalog-1` envelope が追記
- [ ] CLAUDE.md `次の発行順序` から本 brief 行が削除、Brief 8 が
      `直近 merged` に移動
- [ ] `ruff check .` / `pytest -q` 全 pass
- [ ] verdict envelope の既存 fixture が **すべて byte-identical**
      (本 brief は verdict 不変が大原則)

## 11. リスクと回避

| リスク | 内容 | 回避策 |
|---|---|---|
| **R1 surface 越境** | target-doctor の advisory が evaluator に流れて verdict を変えてしまう | §7 不変条件 #1 + #2 の import-graph test、CSCI-43 で `tests/architecture/` 新設して構造的に固定 |
| **R2 candidate-derived tautology** | draft-target が candidate code を読み expected を生成、同 candidate を check して PASS する vacuous loop | §5.5 で `--allow-candidate-derived-expectations` を **本 brief で実装しない**、provenance `candidate_code_used` を必ず記録 |
| **R3 LLM 非決定性混入** | `draft-target --llm-assist` の出力が verdict path に流れる | `draft-target` は `check` を呼ばない構造(§7 #2 + acceptance test)、生成 file は冒頭 `# DRAFT` で人手確認を強制 |
| **R4 catalog drift** | catalog と evaluator 実装が乖離し、AI assistant が無効な target.yaml を生成 | §7 不変条件 #5 の cross-test を CSCI-44 acceptance に含める |
| **R5 advisory ノイズ** | target-doctor が誤検知だらけで信用されない | 各 advisory に false-positive 防止 fixture を必ず 1 件持つ(§5.3 acceptance) |
| **R6 recipe 不足で結局手書き** | 4 recipe で大半の PR をカバーできない | session 2026-05-09 議論で「4 recipe で大半 cover」の見積、不足時は CSCI-42 follow-up で追加 recipe を増やす(後方互換破壊なし) |
| **R7 init 既存 behavior 退行** | `init` の引数なし呼び出しが broken | CSCI-42 acceptance に「既存 behavior 不変」を test で固定 |

## 12. 順序 / 依存

### 12.1 内部依存

```
CSCI-41 (docs)        ── 独立、最初に着地できる
   │
   ├── CSCI-42 (init --recipe) ── 独立
   ├── CSCI-43 (target-doctor) ── tests/architecture/ を新設、後続が再利用
   ├── CSCI-44 (target-catalog) ── 独立(CSCI-43 の architecture test 流用)
   ├── CSCI-45 (draft-target) ── CSCI-42 の recipe ID と source 強度で連動するが file 共有なし
   └── CSCI-46 (compile --explain) optional ── CSCI-43 land 後に重複情報を確認してから着手
```

### 12.2 推奨着地順

```
CSCI-41 → CSCI-43 → CSCI-42 → CSCI-44 → CSCI-45 → CSCI-46(optional)
```

CSCI-43(target-doctor)を先に出す理由:

- `tests/architecture/` を最初に立てることで、後続 CSCI が surface 越境
  リスクを引きずらない(R1 早期に固定)
- D1〜D4 の advisory 化が CSCI-42 recipe 設計の検証ツールになる
  (recipe 出力で D3 が検出されないことを cross-test できる)

CSCI-42 を CSCI-43 の後ろに置くことで、recipe 出力が doctor を pass する
ことを recipe テストで保証できる(両者 simultaneous 開発でも順序差は最小)。

### 12.3 Brief 7 との関係

Brief 7(SSP)は **Validator surface の隣の独立 protocol**、Brief 8 は
**Authoring surface の入口**。共有ファイルは:

- `docs/code_semantic_ci_design.md §23.3.1`(両方が更新)
- `docs/json_schema.md`(envelope 追記、互いに別節)
- `tests/architecture/`(CSCI-43 で新設、Brief 7 が再利用)

merge conflict 面積は小さい。**並列発行可能**。ただし優先度判断は
別軸:

- **Brief 7(SSP)**: セキュリティ機能の新規追加、外部見栄え重視
- **Brief 8(Authoring)**: 既存 UX の埋戻し、アルファ版到達のための足場

session 2026-05-09 議論の結論「アルファ版到達には Authoring 整備が先」
を採れば **Brief 8 を先行**。SSP の外部公開価値を採れば Brief 7 を先行。
本 planning は Brief 8 の自己完結性を確立するのみで、発行順は user 判断。

## 13. Open questions

1. **CSCI-46(compile --explain)を本 brief に含めるか defer するか**
   - 含める利点: authoring readback が compile 自体で取れて UX 統一
   - defer 利点: target-doctor と機能重複の可能性、本 brief サイズが小さくなる
   - 推奨: **CSCI-43 land 後に判断**(本 planning では optional 扱い)

2. **`draft-target --llm-assist` を本 brief で land するか別 brief に送るか**
   - 含める利点: Authoring surface の決定打、外部評価が上がる
   - 別 brief 利点: LLM 経路の cost / model 選定 / API key 管理など、
     `CLAUDE.md` の「LLM calls / API keys を入れない」default に対する
     例外設計が必要(Codex 起票時に Allowed Dependencies 明示)
   - 推奨: **`--llm-assist off` のみで CSCI-45 を land**、`advisory` /
     `full` は CSCI-45b として直後の follow-up brief に分離。本 planning
     §5.5 はその両ケースを describe するのみ。

3. **target-doctor の `--strict-advice` を default の CI で何にするか**
   - 提案: `docs/cli_usage.md` の「CI 推奨設定」節で **`--strict-advice`
     有効 + advisory 0 件で merge** を推奨パターンとして記載
   - ただし engine verdict ではないことを必ず注記(§5.3 exit code 表)

4. **catalog の human format をどこまで詳細にするか**
   - 案 A: 全 operator + target を 1 ページに展開(長くなる)
   - 案 B: `--target-path X` で部分参照を default にする
   - 推奨: 両方サポート、`--target-path` 無し時は summary のみ表示し
     詳細は JSON へ(human ヒューリスティクス)

5. **recipe registry の plugin 化を将来許容するか**
   - 本 brief: 4 recipe 内蔵のみ
   - 将来 brief で `pyproject.toml` に書ける user-defined recipe を許容
     する余地を残すかは Open(CSCI-42 では internal dict のみ)

## 14. CSCI Task Brief 起草時の checklist

各 CSCI を AGENTS.md フォーマットで Codex に渡す際、必ず以下を Brief に
記載する:

- [ ] **Surface 配属**を明示(本 planning §4.1 の表を参照)
- [ ] **§7 不変条件**のうち該当する番号を Acceptance に転記
- [ ] **`tests/architecture/`** の test を増やすか(CSCI-43 で新設、後続は
      add or skip を明示)
- [ ] **schema_version**(該当する場合)を本 planning §6 と一致させる
- [ ] **LLM / network**: 不使用を default、CSCI-45 のみ optional 経路を
      Allowed Dependencies で個別承認
- [ ] **既存 verdict envelope の byte-identical** を必ず acceptance に
- [ ] **Codex への申し送り**: surface 越境は §23.3 違反として escalation
      対象(AGENTS.md §3 の rule 5)

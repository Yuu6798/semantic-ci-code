# Brief 8 Planning — Authoring Surface (target.yaml provenance neutrality 実装)

> **Status: PLANNING (open, scope confirmed 2026-05-09).** 4 PR 構成、完全
> 決定論。LLM / network / API key を一切導入しない。Brief 5 と同等サイズ。
>
> 設計動機: target.yaml の難解さは Semantic CI core の本質的欠陥ではない。
> core は declared intent に対する adherence を決定論的に判定する Validator
> であり、intent の正しさ・完備性・作者の真意は判定しない(`docs/code_semantic_ci_design.md §23.3`)。
> 改善対象は target.yaml を書く前後の **Authoring / Advisor / Provenance**
> 3 surface であり、target.yaml は人間手書き必須ではない。recipe / template /
> PR metadata / commit message / label から生成してよい。生成結果は verdict
> 前に明示的な declared intent として固定され、生成経路・provenance・advice は
> evaluator に参加しない。LLM 経路は **Brief 8b** で別途扱う(本 brief は
> 完全決定論)。

---

## 1. 位置付け

`docs/code_semantic_ci_design.md §23.3.1` の Adjacent surfaces 表に対する
**実装側のキャッチアップ**。設計上は 4 surface 境界が確定しているが、実装は:

| Surface | 設計上の許可 | 実装の現状 |
|---|---|---|
| **Validator** | core engine | 完全実装(Brief 1〜5) |
| **Authoring** | target.yaml 形式の作成支援 | `init` の skeleton 出力**だけ** |
| **Provenance** | intent の declared 経路記録 | `authorship` block の **parse のみ** |
| **Advisor** | intent 周辺情報の human 向け配信 | `validate-plan` / `compile-repair` のみ |

`docs/target_yaml_guide.md` で D1〜D5 を **文書化** したが、ガイドを読まないと
回避できない状態は設計の許容を実装で塞いでいる。本 brief はそのギャップを
埋める。

## 2. Goals

1. **§23.3.1 surface 境界を実装まで貫徹**: Authoring / Provenance / Advisor が
   verdict path に絶対介入しないことを CSCI 単位で構造保証(§5 不変条件
   INV-1〜INV-5)。
2. **target.yaml 生成経路を 3 つに拡張**: 手書き / recipe + PR metadata
   (`init --recipe --from-*`)/ catalog 参照(AI assistant 経路)。
3. **authoring hazard を Advisor 化**: D1 / D3 / D4 + P1 / P2 / S1 を
   `target-doctor` で検出。advisory presence は exit 0(verdict 不参加)、
   ただし usage/config / engine/git / internal error は repo-wide policy
   (`docs/exit_codes.md`)に従う(§6.3 Exit code 規約)。
4. **Provenance metadata の自動記録**: `--recipe <ID>` 指定時のみ
   `authorship.generation_metadata` を deterministic に記録。`candidate_code_used:
   false` を default にし、LLM 経路は本 brief で実装しない。**plain `init`(引数なし)
   の出力は既存 `TARGET_TEMPLATE` を逐語維持**。
5. **完全決定論**: 全 subcommand で LLM / network / API key 不使用。同 input →
   byte-identical output(§5 INV-4)。
6. **`semantic-ci check` の verdict 計算は不変**: envelope schema / exit code /
   verdict ロジックは本 brief で触らない(§5 INV-1)。

## 3. Non-goals

- `semantic-ci check --auto-target`(`check` 内 target 生成、§23.3 違反)
- LLM 経路全般(`--llm-assist` 系) → **Brief 8b**
- candidate code 由来 expectation 生成 → 本 brief 非実装、`candidate_code_used: false` 固定
- 任意 Python 式 / 独自 DSL 化(`target.yaml` は YAML + typed operator のまま)
- LLM-as-judge(永続的 non-goal)
- intent の正しさ判定(`docs/code_semantic_ci_design.md §23.3.3`)
- `target-doctor --strict-advice`(advisor surface に verdict 圧力をかけない)
- `compile --explain`(既存 `compile --format human` で十分)
- standalone `draft-target` subcommand(`init --recipe + --from-*` に統合)
- non-Python artifact gating(SSP 範疇)
- 新 constraint kind / operator(本 brief は authoring 経路の整備のみ)
- TypeScript / 多言語 catalog(Brief 6 凍結)
- GitHub App / Action 化(別 brief)

## 4. 救済される未解決項目

| 出典 | 項目 | 本 brief での扱い |
|---|---|---|
| `docs/target_yaml_guide.md` D1 / D3 / D4 | authoring hazard の機械化 | **CSCI-43** target-doctor の `ADVISORY-D1` / `D3` / `D4` |
| 同 D5(set operator partial-match) | PR #65 で Validator 側で完全解消 | target-doctor 側で追加検知すべき残存 pattern なし(§6.3 注記参照) |
| 設計 §23.3.1 Authoring | scaffold だけでは constraint DSL 落とし込みを支援しきれない | **CSCI-42** init `--recipe --from-pr-body --from-labels --from-commits --from-issue` |
| 設計 §23.3.1 Provenance | `authorship.generation_metadata` を parse するが書き出しコマンドが無い | **CSCI-42** init recipe が generation_metadata を deterministic に記録 |
| 設計 §23.3.1 Advisor | 既存 `validate-plan` は target.yaml が正しく書かれている前提 | **CSCI-43** target-doctor + **CSCI-44** target-catalog |
| 「target.yaml は手書き必須でない」 を設計文書に明記 | doc gap | **CSCI-41** で `docs/target_authoring_surface.md` 新設 |

---

## 5. アーキテクチャ

### 5.1 Surface 配属

```
┌──────────────────────────────────────────────────────────┐
│  authoring-time(verdict 不参加、§23.3.1)                │
│                                                          │
│   user input ─┐                                          │
│   PR body ────┤                                          │
│   issue ──────┼──▶ init --kind --recipe ──▶ target.yaml  │
│   labels ─────┤    (CSCI-42)              (declared      │
│   commits ────┘                            intent +      │
│                                            provenance)   │
│                                                          │
│   AI assistant ──▶ target-catalog (CSCI-44, JSON)        │
│                                                          │
│   target.yaml ──▶ target-doctor (CSCI-43, advisory)      │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼ ★ verdict 入口で固定
┌──────────────────────────────────────────────────────────┐
│  verdict-time(Validator surface、§23.1 / §23.3 不可侵) │
│                                                          │
│   target.yaml + baseline + candidate                     │
│      ──▶ check / compare / validate-plan / compile-repair│
│                  (Brief 1〜5、本 brief で不変)          │
└──────────────────────────────────────────────────────────┘
```

| CSCI | Surface | 役割 | verdict 関与 |
|---|---|---|---|
| CSCI-41 (docs) | (docs) | §23.3.1 surface 区分の文書側追記 | NO |
| CSCI-42 init `--recipe` + sources | Authoring + Provenance | recipe + user input + PR metadata → target.yaml + generation_metadata 自動記録 | NO |
| CSCI-43 target-doctor | Advisor | target.yaml の hazard を render | NO |
| CSCI-44 target-catalog | Authoring(meta) | target / operator / template / match schema を機械可読出力 | NO |

### 5.2 不変条件(INV-1〜INV-5)

実装で **構造的に保証する** 5 つの不変条件。各 CSCI acceptance に対応番号を
明記する。

**INV-1 — Verdict bytes invariant** (narrow scope):
`check` / `compare` / `compile-repair` の JSON envelope のうち、**evaluator が
決定する field**(`verdict` / `repair_plan` / `summary` および同等の
per-subcommand evaluator output)は本 brief の全変更後も既存 fixture で
byte-identical。

除外する 2 領域:
- `target_authorship` field(`cli/output/json_formatter.py:32-58` `build_payload`、
  `tests/test_authorship.py:73` で stable と既定済)— authorship を意図的に
  reflect する既存仕様。
- `validate-plan` envelope 全体 — adapter `render_pre_gen` が
  `generation_metadata` を逐語 render する設計
  (`repair_compiler/adapters/{markdown,codex,claude_code,cursor}.py` の
  `format_generation_metadata`)、provenance を generator に伝えるのが
  Advisor surface の明示要件(`§23.3.1`)。

→ `tests/architecture/test_verdict_bytes_invariant.py` で除外 helper を提供。

**INV-2 — `check` does not generate target invariant** (semantic layer only):
**`cli/commands/check.py` および `check` subcommand handler が再帰的に import
する verdict 経路の module 集合** が `init` / `target-doctor` /
`target-catalog` のいずれの module も import しない。

`cli/main.py` の subparser registration は CLI dispatcher の事務的 import
であり、verdict 計算意味論の越境ではないため対象外(`cli/main.py:6-14` で
全 subcommand handler が module load 時に import される設計)。

→ `tests/architecture/test_surface_isolation.py` で `cli.commands.check` を
root とした transitive import-graph を walk、対象 module 名が closure に
現れたら fail。

**INV-3 — Provenance non-participation invariant** (narrow scope):
target.yaml の `authorship.generation_metadata` を任意に書き換えても
`check` / `compare` / `compile-repair` の **evaluator-derived field**
(`verdict` / `repair_plan` / `summary`)は byte-identical。除外領域は INV-1
と同じ(`target_authorship` field、`validate-plan` envelope)。

→ fixture を 1 つ作り、generation_metadata の値違いで verdict を回し、
除外 helper 経由で hash 一致を確認(CSCI-42 acceptance)。

**INV-4 — No-LLM / no-network invariant**:
本 brief で追加・変更されたすべての subcommand 経路で `httpx` / `requests` /
`openai` / `anthropic` / `urllib3` 等の network/LLM client を import しない。

→ `tests/architecture/test_surface_isolation.py` で全 authoring subcommand
module の transitive imports を assert。

**INV-5 — Catalog ↔ implementation parity invariant**:
`target-catalog` の出力に登録された target / operator / template / match schema
が `compiler/templates.py` / `evaluator/operators.py` / `framework/match_schema.py`
の実体と一致する。

→ `tests/architecture/test_catalog_implementation_parity.py` で cross-test。

---

## 6. CSCI 分割

合計 4 PR、約 4.5〜5 日。各 CSCI を AGENTS.md Task Brief 形式で記述。

### 6.1 CSCI-41 (P0): 設計文書追記

**Phase**: Brief 8 / Authoring surface(documentation)

**Goal**: target.yaml が hand-written 必須でないことを設計側で固定し、今後の
実装判断の前提を明文化する。

**Acceptance Criteria**:
- [ ] `docs/target_authoring_surface.md` (NEW) が以下 6 点を明記:
  (a) target.yaml は hand-written 必須でない
  (b) 生成経路の 3 通り(recipe + sources / catalog 参照 / hand-written)
  (c) LLM 経路は Brief 8b で別途扱う(本 brief 非導入)
  (d) 全経路は verdict 前に declared intent として固定される
  (e) Authoring / Advisor / Provenance surface は evaluator から参照不可
  (f) candidate-derived expectation は本 brief で実装しない、provenance
      `candidate_code_used` は **必ず false** で記録
- [ ] `CLAUDE.md` docs table に新規 doc が status `ACTIVE` で登録
- [ ] `docs/target_yaml_guide.md` 冒頭に「target.yaml は人間が直接書く前提では
      ない」「複数の authoring 経路が許容されている」を pin、D1〜D5 の章末に
      target-doctor cross-ref を追記
- [ ] `docs/code_semantic_ci_design.md §23.3.1` Adjacent surfaces 表に
      `init --recipe` / `target-doctor` / `target-catalog` を追記
- [ ] `docs/cli_usage.md` に「Authoring subcommands(verdict 不参加)」 節を
      追加(CSCI-42〜44 で順次埋める前提、CSCI-41 では節見出しと §23.3.1
      cross-ref のみ)
- [ ] `docs/exit_codes.md` に target-doctor の exit code 規約を §6.3 と逐語
      一致させて追記
- [ ] `docs/json_schema.md` に `advisory-1` / `catalog-1` envelope を追記
- [ ] `ruff check .` / `pytest -q` 全 pass(docs only、コード変更なし)

**Scope**:
- IN: `docs/target_authoring_surface.md` (NEW), `docs/target_yaml_guide.md`,
  `docs/code_semantic_ci_design.md`, `docs/cli_usage.md`, `docs/exit_codes.md`,
  `docs/json_schema.md`, `CLAUDE.md`, `README.md`
- OUT: ソースコード一切、テスト一切

**Brief size**: 0.5 日。

### 6.2 CSCI-42 (P1): `semantic-ci init --recipe --from-*`

**Phase**: Brief 8 / Authoring + Provenance surface

**Goal**: 現行 `init` の skeleton 出力を壊さずに、recipe mode と PR metadata
取り込み(deterministic-only)を追加する。LLM / network 不使用。

#### 6.2.1 Recipe contract(canonical、本箇所のみが正)

| Recipe ID | 必須 / optional 引数 | 生成される constraint |
|---|---|---|
| `feature:add-api` | **必須**: §6.2.3 fallback chain で API FQN list が非空であること(`--add-api FQN+` ∪ PR body `## Expected public API` ∪ issue body `## Expected public API` または `## Acceptance Criteria` の API FQN bullet)。**optional**: `--test-case ID*`(canonical `path/to/test_file.py::test_function` 形式、§6.2.4 参照) | `api_surface_delta.added includes_all [{fqn: <FQN1>, visibility: "public"}, …]`(record match で **`visibility: "public"` を強制**、平坦投影 alias を使わない、`framework/match_schema.py:47` `_API_SCHEMA.optional_keys={"kind", "visibility"}` を活用)。`--test-case` 指定時は `test_surface_delta.new_cases includes_all [<canonical test ID…>]`、未指定時は test_surface 制約なし |
| `bugfix:regression-test` | **optional**: `--test-case ID*`(canonical `path::name`) | `--test-case` 指定時 `test_surface_delta.new_cases includes_all [<canonical test ID…>]`、未指定時 `test_surface_delta.new_cases not_equals []`。template により `api_surface_public equals_baseline` + `effect_changes.added equals ()`(`compiler/templates.py:64-76`、public API は **追加も削除も不可**)。public API 変更を伴う修正には `feature:add-api` を使う |
| `refactor:preserve-api-with-allowlist` | **optional**: `--allow-fqn FQN*`, `--allow-fqn-prefix PREFIX*` | allowlist 無し: `change.primary_kind: refactor` のみ(template が `api_surface_public equals_baseline` を auto-expand、`compiler/templates.py:43`)。allowlist 有り: `api_surface.allow_changes` rule を生成(`{fqn: …}` または `{fqn_prefix: …}`、`compiler/target_compiler.py:291`、existing policy escape hatch、新 operator 追加なし)。direction 別(add only / remove only)は現行 DSL 制約で表現不能 |
| `test-update:add-test-case` | **optional**: `--test-case ID*`(canonical `path::name`) | `--test-case` 指定時 `test_surface_delta.new_cases includes_all [<canonical test ID…>]`、未指定時 `test_surface_delta.new_cases not_equals []`。`primary_kind=test_update` で template が `api_surface_public equals_baseline` + `effect_changes equals {added: (), removed: ()}` + `imports equals_baseline` を auto-expand(`compiler/templates.py:91-108`、test 追加以外を全 lock) |

各 recipe は `change.primary_kind` を必ず設定し、template constraint を
**重複生成しない**(template と user constraint の重複は ADVISORY-D3、
CSCI-43 で検出される)。

#### 6.2.2 Source 強度ポリシー

| Source | 強さ | 役割 |
|---|---|---|
| `--add-api` / `--test-case` / `--allow-fqn` / `--allow-fqn-prefix` / `--declared-at`(明示 user input) | strong | positive expectation / authorship の確定値、逐語保持 |
| labels(`kind:feature` 等、`--from-labels`) | strong | `change.primary_kind` validation のみ(§6.2.3 precedence 表) |
| PR body の structured section(`--from-pr-body`) | strong | positive expectation の値 |
| issue body の structured section(`--from-issue`) | medium | positive expectation の値、strong layer 空のときのみ参照 |
| commit message Conventional Commits prefix(`--from-commits`) | medium | `primary_kind` の hint(他 source 不在時のみ) |
| **candidate code body / observed semantic delta** | **本 brief 非実装** | tautology 化リスクのため、`--allow-candidate-derived-expectations` flag は **存在しない** |

#### 6.2.3 Source merge と precedence(canonical)

**`change.primary_kind` の precedence**: `--recipe` が authoritative。
`--from-*` / explicit-input flag を `--recipe` 無しで指定すると error
(`docs/code_semantic_ci_design.md §23.3.1` の constraint set 選択は recipe
ID にバインドされている)。

| 入力 pattern | 動作 |
|---|---|
| `init`(引数なし) | scaffold mode、既存 `TARGET_TEMPLATE` を逐語出力、generation_metadata 不生成 |
| `init --recipe <ID>`(他 flag なし) | recipe 実行、generation_metadata 生成 |
| `init --recipe <ID> --from-*` / `--add-api` 等 | recipe + source merge 実行 |
| `init --from-*`(`--recipe` 無し) | **error**: `--recipe is required when source flags (--from-*) are used; recipe ID determines the constraint set` |
| `init --add-api` 等(`--recipe` 無し) | **error**(同上) |

**FQN list の merge(fallback chain)**: source 強度層を尊重し、層を跨いで
union しない:

1. CLI parse: `--add-api` を **optional** として受け取る
2. PR body / issue parse: structured section から FQN list を抽出
3. merge:
   - **strong layer**(`--add-api` ∪ PR body)— 同一 layer 内 union dedup。
     値があれば確定、下位 layer 参照しない。
   - **medium layer**(issue body)— strong layer が空のときのみ参照。
   - **lowest**(commit hint)— FQN 列には貢献しない(primary_kind hint のみ)。
4. 検証: merge 後の FQN list が空ならエラー(明示 message)

**Conflict rules**(`merge.py` で固定):

- **C1**: `--recipe feature:add-api` + `kind:bugfix` label → recipe の
  `feature` と label の `bugfix` が不一致、**error**(message:
  `recipe '{ID}' implies primary_kind '{X}', but label 'kind:{Y}' contradicts;
  remove the conflicting label or use --recipe 'kind:{Y}:...'`)
- **C2**: 異種 labels 混在(例: `kind:feature` + `kind:bugfix`)→ labels
  内部矛盾、**error**
- **C3**: Conventional Commits prefix が recipe primary_kind と不一致 →
  **error**(C1 と同型)
- **C4**: PR body / issue の **intent-declaring structured section**(下記
  registry)が recipe に消費されずに残った場合 → **error**

**Intent-declaring section registry**(parser 側で固定、`## Acceptance Criteria`
は両用途):

| Section title | 用途 |
|---|---|
| `## Expected public API` | API FQN source(PR body / issue 共通) |
| `## Removed public API` | (本 brief の 4 recipe では消費されない、将来 brief で `feature:remove-api` 等を追加する余地) |
| `## Test cases` | test case ID source(canonical `path::name` 形式) |
| `## Acceptance Criteria` | **両用途**: parser が content grammar(行頭 `-` の値が `::` を含めば test ID、`.` のみなら FQN、混在は lexer error)で content 分類。両方混在(別 bullet)なら両方 feed。silent guess 禁止、分類不能な内容は C4 error |

registry に **無い** 一般 section(`## Description` / `## Motivation` /
`## Background` 等の人間向け説明)は declared intent ではないため無視 OK。

#### 6.2.4 `--test-case` の値形式

`--test-case` は **canonical test case ID** 形式
`path/to/test_file.py::test_function`(例: `tests/test_common.py::test_added`)
を必須とする。これは `compute_code_state_delta()._test_case_id()`
(`src/semantic_ci_code/delta/code_state_delta.py:354-355`)が
`f"{entry.test_file}::{entry.test_function}"` で `new_cases` に書き出す
canonical 形式と一致する。Python-style FQN(`tests.test_common.test_added`)
で渡すと `compile` は通るが evaluator が delta に同値の文字列を見つけられず
**永久に fail**。

CLI parse 段階で `::` 区切りを必須化し、含まない値は明示 error
(message: `--test-case value '{val}' is not in canonical 'path::name' form
(e.g. 'tests/test_x.py::test_y'); recipe-generated constraints must match
TestSurfaceDelta.new_cases output of code_state_delta._test_case_id`)。

#### 6.2.5 Provenance metadata(`--recipe` 指定時のみ)

`--recipe` 指定時に `authorship.generation_metadata` を生成。**plain
`init`(引数なし)出力は既存 `TARGET_TEMPLATE` を逐語維持**
(`tests/cli/test_init_command.py:24` `test_init_writes_default_target_template`
が現行 scaffold の bytes を assert 済)。

```yaml
authorship:
  # declared_at は default omit(framework/target_svp.py:58
  # Authorship.declared_at: str | None = None)。--declared-at で明示指定時
  # のみ書く。wall-clock 自動埋め込みは determinism violation のため禁止。
  generation_metadata:
    tool: semantic-ci-init
    tool_version: "<package version, importlib.metadata.version で静的解決>"
    recipe: "feature:add-api"
    source_surfaces:
      - user_input
      - pr_body    # --from-pr-body 指定時のみ
      - issue      # --from-issue 指定時のみ
      - labels     # --from-labels 指定時のみ
      - commits    # --from-commits 指定時のみ
    candidate_code_used: false  # 本 brief では常に false
    llm_used: false  # 本 brief では常に false(Brief 8b で導入)
```

`tool_version` は `importlib.metadata.version()` から静的解決
(wall-clock / git ref 不依存)。`candidate_code_used` / `llm_used` は固定値
で provenance invariant を運用側で可視化する。

#### 6.2.6 追加 / 変更ファイル

- `src/semantic_ci_code/cli/init_command.py` (UPDATE): `--recipe` /
  `--add-api` / `--test-case` / `--allow-fqn` / `--allow-fqn-prefix` /
  `--declared-at` + `--from-pr-body` / `--from-labels` / `--from-commits` /
  `--from-issue` 引数追加
- `src/semantic_ci_code/cli/init_recipes/` (NEW directory):
  - `__init__.py`: `RECIPES` dict、`apply_recipe()` entry point
  - `feature_add_api.py`
  - `bugfix_regression_test.py`
  - `refactor_preserve_api.py`
  - `test_update_add_test_case.py`
- `src/semantic_ci_code/authoring/sources/` (NEW directory):
  - `__init__.py`
  - `pr_body.py`: structured markdown section parser
  - `issue.py`: issue body の structured section parser(PR body と
    semantically 互換だが entry point 分離で provenance を区別)
  - `labels.py`: `kind:feature` 等から `primary_kind` 抽出 + validation
  - `commits.py`: Conventional Commits prefix 抽出 + validation
  - `merge.py`: source 強度 + precedence rule + C1〜C4 conflict detection
- `src/semantic_ci_code/authoring/provenance.py` (NEW):
  `build_generation_metadata()` ユーティリティ
- `src/semantic_ci_code/cli/main.py` (UPDATE): `init` subparser に新引数
- `tests/cli/test_init_recipe.py` (NEW)
- `tests/cli/test_init_sources.py` (NEW)
- `tests/cli/test_init_merge.py` (NEW): C1〜C4 全種の golden fixture
  (成功 / 失敗、エラー message 含む)
- `tests/architecture/test_verdict_bytes_invariant.py` (NEW): INV-1 / INV-3

#### 6.2.7 Acceptance Criteria(CSCI-42)

- [ ] 4 recipe すべて決定論的(同 input 3 回 → byte-identical YAML)
- [ ] 生成 YAML は `compile` を pass(構文 / path / operator / template
      relaxation 経路の妥当性)
- [ ] **Schema grounding cross-test**(§15 checklist の grep 一覧を実装)
- [ ] **Template-expansion-parity cross-test**: recipe の template 説明が
      `compiler/templates.py` の `TEMPLATE_CONSTRAINTS` dict と一致
- [ ] **Visibility-preservation cross-test**: `feature:add-api` 出力が
      `{fqn, visibility: "public"}` record match を含む(平坦投影 alias を
      使わない)
- [ ] **Source-merge fixture** 3 種:
  - PR-body-only flow(`--add-api` 無し、`--from-pr-body` のみで recipe 満足)
  - issue-only flow(`--from-issue` のみで recipe 満足、medium layer fallback)
  - strong-fills-issue-ignored(strong layer 充足時に issue 由来 FQN が混入
    しない)
- [ ] **Conflict-resolution fixture** 4 種(C1〜C4 成功 / 失敗、エラー
      message 含む)
- [ ] `--test-case` の `::` 区切り validation(canonical form check)
- [ ] **Provenance scope** test:
  - plain `init`(引数なし)出力は `tests/cli/test_init_command.py:24`
    既存 assertion を pass、generation_metadata 不在
  - `--recipe` 指定時のみ generation_metadata 生成
  - `--from-*` / explicit-input flag を `--recipe` 無しで指定すると error
  - `candidate_code_used` / `llm_used` は **常に false**
  - `--allow-candidate-derived-expectations` flag は **存在しない**
      (CLI argparse spec で確認)
  - `--declared-at` 未指定時は generation_metadata.declared_at 不在
- [ ] **INV-1 / INV-3 verdict 不変条件テスト**(§5.2 INV-1 / INV-3 の
      除外 helper 経由で hash 一致)
- [ ] **INV-4 No-LLM / no-network test**: `httpx` / `requests` / `openai` /
      `anthropic` / `urllib3` / `socket` を import しない(import-graph)
- [ ] `ruff check .` / `pytest -q` 全 pass

**Brief size**: 1.5〜2 日。

### 6.3 CSCI-43 (P2): `semantic-ci target-doctor`

**Phase**: Brief 8 / Advisor surface

**Goal**: target.yaml の authoring hazard を Advisor として render する新
subcommand。verdict には参加しない(advisory presence は exit 0)。
`--strict-advice` のような advisory→fail flag は **実装しない**。

#### 6.3.1 Advisory 一覧(6 種)

| Code | 概要 | 入力 |
|---|---|---|
| `ADVISORY-D1` | `test_surface_delta.*` constraint exists, but `--package-root` does not include `tests/` | target.yaml + package-root |
| `ADVISORY-D3` | user constraint duplicates a template-expanded constraint | target.yaml + change.primary_kind |
| `ADVISORY-D4` | target is lock-only / config-only and candidate diff is config/doc/workflow only; PASS would be vacuous | target.yaml + baseline-rev + candidate-rev |
| `ADVISORY-P1` | `primary_kind=feature` but no positive addition constraint | target.yaml |
| `ADVISORY-P2` | `primary_kind=bugfix` but no `test_surface_delta.new_cases` expectation | target.yaml |
| `ADVISORY-S1` | constraint has `severity: info` AND `unknown_policy in {fail, repair}`; **violation** は verdict 無視されるが **extraction-cause / open_runtime UNKNOWN(skipped dimensions 等)は `unknown_policy` 経由で依然 verdict 影響**(`evaluator/evaluator.py` `_aggregate`)。 D1-4 (PR #78) で **authoring-cause UNKNOWN は `unknown_policy` 非尊重で常時 FAIL** となり、 S1 の scope は extraction / open_runtime に narrow(`docs/brief_resultstatus_planning.md §1b.3`)。 完全 informational には `unknown_policy: ignore` | target.yaml |

D5 advisory は実装しない(PR #65 で Validator 側に完全吸収済、`TargetSVP` に
target-level `schema_version` field なく `normalize_collection_expected()` で
bare-string が valid shorthand に desugar されるため legacy 形を識別できず
false positive となる、§15 checklist 「advisor は検出可能で意味のある invalid
pattern が現行 schema に実在することを必ず先に確認」に従い不実装)。

#### 6.3.2 CLI

```
semantic-ci target-doctor \
  --target .semantic-ci/target.yaml \
  [--package-root .] \
  [--baseline-rev origin/main] \
  [--candidate-rev HEAD] \
  [--format human|json]
```

#### 6.3.3 Exit code 規約(canonical)

`docs/exit_codes.md` repo-wide policy に整合:

| 条件 | exit code |
|---|---|
| advisory 0 件(成功 + 出力) | 0 |
| advisory ≥ 1 件(成功 + 出力) | **0**(advisor surface、verdict ではない) |
| **Usage / configuration error**(target.yaml 不在 / 不正、CLI flag 不正、`--baseline-rev` / `--candidate-rev` parse 不能) | **2**(`exit_codes.md` l.14) |
| **Expected engine / git error**(target.yaml 構文エラー = `CompileError`、git revision 解決失敗、git 利用不可) | **3**(`exit_codes.md` l.67-70) |
| 内部エラー(unhandled exception) | 4 |

**advisor surface でも silent success on bad input は禁止**: advisor 検出の
有無のみが verdict 不参加で 0、入力 / engine 失敗は 2 / 3 / 4 を返す。
`--strict-advice` は実装せず、CI で advisory 0 件を gate したいユーザは
`--format json` 出力を外部 workflow policy で処理する。

#### 6.3.4 追加 / 変更ファイル

- `src/semantic_ci_code/cli/commands/target_doctor.py` (NEW)
- `src/semantic_ci_code/cli/main.py` (UPDATE): subparser
- `src/semantic_ci_code/authoring/` (UPDATE):
  - `hazards.py` (NEW): D1 / D3 / D4 / P1 / P2 / S1 の検出関数
    (D5 は実装しない、§6.3.1 注記)
  - `advisory.py` (NEW): `Advisory` dataclass
- `src/semantic_ci_code/cli/output/doctor_human.py` (NEW)
- `src/semantic_ci_code/cli/output/doctor_json.py` (NEW)
- `src/semantic_ci_code/schemas/doctor_advisory.schema.json` (NEW)
- `tests/cli/test_target_doctor.py` (NEW)
- `tests/architecture/test_surface_isolation.py` (NEW): INV-2 / INV-4

#### 6.3.5 Acceptance Criteria(CSCI-43)

- [ ] 6 advisory 全種(D1 / D3 / D4 / P1 / P2 / S1)が unit テスト fixture で
      検出される
- [ ] 各 advisory に **false positive 防止 fixture** を 1 件持つ(detect
      されないケース)
- [ ] **Advisor-no-false-positive cross-test**: `severity: info` +
      `unknown_policy: ignore` の真に informational なケースで S1 が発火
      しない
- [ ] `--format json` 出力が `schema_version="advisory-1"` で安定
- [ ] **Exit code 規約**(§6.3.3):
  - 正常入力で advisory 0 / ≥ 1 の両方とも exit 0
  - target.yaml 不在 / 不正 flag → exit 2
  - target.yaml 構文エラー / git 解決失敗 → exit 3
  - `--strict-advice` flag は **存在しない**(argparse spec で確認)
- [ ] **INV-1 verdict 不変条件テスト**: target-doctor を実行しても
      `check` / `compare` / `compile-repair` の verdict envelope は
      byte-identical
- [ ] **INV-2 surface isolation test**: `cli.commands.check` の transitive
      imports に `target-doctor` の module が現れない
- [ ] **INV-4 no-LLM / no-network**: import-graph で `httpx` / `requests` /
      `openai` / `anthropic` 不在
- [ ] determinism test(同 input 3 回 → byte-identical)
- [ ] `ruff check .` / `pytest -q` 全 pass

**Brief size**: 1.5 日。

### 6.4 CSCI-44 (P3): `semantic-ci target-catalog`

**Phase**: Brief 8 / Authoring (meta) surface

**Goal**: target / operator / template / match schema を機械可読 + human
readable で出す Advisor surface コマンド。AI assistant、IDE 拡張、外部
authoring tool が target.yaml を **正しく生成するため** の reference。

#### 6.4.1 CLI

```
semantic-ci target-catalog [--format json|human] [--kind feature|...]
                           [--target-path api_surface_delta.added]
```

#### 6.4.2 JSON 出力(抜粋、registry と逐語一致)

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
        "optional_keys": ["kind", "visibility"],
        "forbidden_keys": {
          "signature": "signature is extractor-format coupling and is not stable policy input"
        }
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

`api_surface_delta.added` の `optional_keys` は `["kind", "visibility"]` のみ
(`framework/match_schema.py:47` `_API_SCHEMA` と逐語一致)。`signature` は
forbidden、`module` は未登録。

#### 6.4.3 追加 / 変更ファイル

- `src/semantic_ci_code/cli/commands/target_catalog.py` (NEW)
- `src/semantic_ci_code/cli/main.py` (UPDATE): subparser
- `src/semantic_ci_code/authoring/catalog.py` (NEW): catalog builder
- `src/semantic_ci_code/schemas/target_catalog.schema.json` (NEW)
- `tests/cli/test_target_catalog.py` (NEW)
- `tests/architecture/test_catalog_implementation_parity.py` (NEW): INV-5

#### 6.4.4 Acceptance Criteria(CSCI-44)

- [ ] catalog の JSON schema が `schemas/` に登録、出力が schema valid
- [ ] **INV-5 catalog ↔ implementation parity cross-test**: catalog 出力の
      target / operator / template が `evaluator/operators.py` / 
      `compiler/templates.py` / `framework/match_schema.py` の実体と一致
- [ ] **Match-schema-parity cross-test**: `api_surface_delta.added` の
      `optional_keys` は `["kind", "visibility"]` のみ、`forbidden_keys` は
      `signature` を含む、`module` は登録しない
- [ ] AI assistant が catalog を見て生成した target.yaml が `compile` で
      reject されないこと(roundtrip cross-test)
- [ ] `--kind feature` で template 展開が想定通り
- [ ] human format が target.yaml authoring user に読める粒度
- [ ] **INV-1 verdict 不変条件テスト**(§5.2)
- [ ] **INV-4 no-LLM / no-network**(import-graph)
- [ ] determinism test(同 input 3 回 → byte-identical)
- [ ] `ruff check .` / `pytest -q` 全 pass

**Brief size**: 1 日。

---

## 7. Schema / envelope 影響

新規 envelope 2 種:

| Envelope | Schema version | Surface | 関連 CSCI |
|---|---|---|---|
| `target-doctor` advisory output | `advisory-1` | Advisor | CSCI-43 |
| `target-catalog` reference output | `catalog-1` | Authoring meta | CSCI-44 |

既存 envelope の schema_version は **bump しない**:

- verdict envelope: `"5"`(PR #65 で確定、本 brief 不変)
- compile envelope: `"5"`(同上)
- compile-repair envelope: `"1"`(不変)
- validate-plan envelope: `"1"`(不変)

target.yaml 自体の schema は **不変**。`generation_metadata` block は既存
optional field の populate。

## 8. CLI surface(after-state)

```
semantic-ci
├── observe         (Validator: 単発観測)
├── compare         (Validator: 任意 2-rev 比較)
├── check           (Validator: PR モード)
├── pre-commit      (Validator: pre-commit 連携)
├── compile         (Validator readback)
├── compile-repair  (Advisor: repair guidance)
├── validate-plan   (Advisor: pre-generation guidance)
├── init            (Authoring: scaffold + recipe + PR sources)  ★ 拡張
├── target-doctor   (Advisor: authoring hazard)                  ★ NEW
└── target-catalog  (Authoring meta: machine-readable ref)       ★ NEW
```

合計 10 subcommand(現在 8 + 新規 2、`init` は拡張)。**Validator 5 / Advisor
3 / Authoring 2** で surface バランス。

## 9. テスト戦略

### 9.1 各 CSCI 単位

各 CSCI 内で:
- **unit**: hazards / recipes / catalog builder / source parser を関数単位
- **CLI integration**: 各 subcommand の golden fixture
- **determinism**: 同 input 3 回呼び出して byte-identical
- **schema valid**: 各 JSON 出力が JSON schema 通過

### 9.2 横断テスト(`tests/architecture/` 新設)

- `test_surface_isolation.py`(CSCI-43 で新設): INV-2 / INV-4
- `test_verdict_bytes_invariant.py`(CSCI-42 で新設): INV-1 / INV-3
- `test_catalog_implementation_parity.py`(CSCI-44 で新設): INV-5

`tests/architecture/` は本 brief で初出。Brief 7(SSP)が後続で SSP envelope
分離する際にも同 pattern が再利用できる。

### 9.3 Dogfooding

CSCI-42 land 後、`docs/dogfooding_TC10_report.md` の TC1〜TC10 を
**`init --recipe` で再生成して `compile` を pass するか**を最終 PR
(CSCI-44)で記録。recipe 4 種で実用 PR の大半をカバーできることの経験的検証。

---

## 10. Brief 全体 Acceptance Criteria

- [ ] CSCI-41〜44 全 PR が merged
- [ ] §5.2 INV-1〜INV-5 全件が test で固定されている
- [ ] `docs/target_authoring_surface.md` 新設、CLAUDE.md docs table に
      ACTIVE で登録
- [ ] `docs/cli_usage.md` に `init --recipe + --from-*` / `target-doctor` /
      `target-catalog` のセクションが追加
- [ ] `docs/exit_codes.md` に target-doctor の exit code 規約が §6.3.3 と
      逐語一致(advisory presence は 0、usage/config = 2、engine/git = 3、
      internal = 4。「常に 0」 とは書かない、silent success on bad input は
      禁止)
- [ ] `docs/json_schema.md` に `advisory-1` / `catalog-1` envelope 追記
- [ ] CLAUDE.md `次の発行順序` から本 brief 行が削除、Brief 8 が
      `直近 merged` に移動。Brief 7(SSP)発行を本 brief 後に置く順序が
      `docs/code_semantic_ci_design.md §25` に反映
- [ ] `ruff check .` / `pytest -q` 全 pass
- [ ] LLM / network 呼び出しがゼロであることが import-graph で固定
      (本 brief 完全決定論)

---

## 11. リスクと回避

| ID | Risk | 回避 |
|---|---|---|
| **R1** | Surface 越境(advisor / authoring が verdict 経路に介入) | INV-1 / INV-2 / INV-3 の test を CSCI 単位で fail-fast 化、`tests/architecture/` で構造保証 |
| **R2** | Candidate-derived tautology(候補コードを expectation source にして vacuous PASS) | `--allow-candidate-derived-expectations` flag を実装しない、`candidate_code_used` を常に false 固定、CLI argparse spec で flag 不在を test 固定 |
| **R3** | LLM / network の意図せぬ混入(将来 dependency 追加経由) | INV-4 import-graph test で `httpx` / `requests` / `openai` / `anthropic` 等を禁止、Brief 8b で LLM 経路を追加する際に本 invariant の境界(authoring 限定)を再確認 |
| **R4** | Catalog drift(catalog と evaluator 実装の乖離) | INV-5 cross-test を CSCI-44 acceptance に含める |
| **R5** | Advisor noise(target-doctor の誤検知) | 各 advisory に false-positive 防止 fixture を 1 件持つ、§15 checklist「検出可能で意味のある invalid pattern の実在を先に確認」 を遵守 |
| **R6** | Recipe 不足(4 recipe で実用 PR を cover しきれない) | §9.3 dogfood で経験的検証、不足時は CSCI-42 follow-up で追加(後方互換破壊なし) |
| **R7** | `init` 既存 behavior 退行(plain init 出力が変わる) | provenance metadata 生成を `--recipe` 指定時のみに narrow、CSCI-42 acceptance に既存テスト不変を含める |
| **R8** | Spec drift(brief 内の同一 spec を複数箇所で paraphrase した結果一致しなくなる) | 本 brief 全 spec table は §6 内の **canonical 1 箇所のみ**、他は cross-ref。§15 brief drafting checklist に「spec table 修正時は対応する spec 文字列を grep で全箇所検出して同時更新」を必須化 |

R9 履歴(round-1〜20 の specific findings 28 件)は **Appendix A** に audit
trail として保存。本表に統合した防御原則は §15 checklist で再利用可能。

---

## 12. 順序 / 依存

### 12.1 内部依存

```
CSCI-41 (docs)         ── 独立、最初に着地
   │
   ├── CSCI-42 (init --recipe + --from-*) ── 独立
   │      │
   │      └── tests/architecture/test_verdict_bytes_invariant.py 新設
   │
   ├── CSCI-43 (target-doctor) ── 独立
   │      │
   │      └── tests/architecture/test_surface_isolation.py 新設
   │           (後続 CSCI-44 が再利用)
   │
   └── CSCI-44 (target-catalog) ── CSCI-43 の architecture test 流用
          │
          └── tests/architecture/test_catalog_implementation_parity.py 新設
```

### 12.2 推奨着地順

```
CSCI-41 → CSCI-43 → CSCI-42 → CSCI-44
```

CSCI-43 を CSCI-42 より先に出す理由: `tests/architecture/` を最初に立てて
後続 CSCI が surface 越境リスクを引きずらない(R1 早期固定)。CSCI-42 を
CSCI-43 の後ろに置くことで、recipe 出力が doctor を pass することを recipe
テストで保証可能。

### 12.3 Brief 7(SSP)との関係 — Brief 8 先行を確定

**Brief 8 を Brief 7 より先に発行することを本 planning で確定**。

1. **adoption bottleneck の所在**: 現時点の adoption 障壁は SSP sibling
   protocol の不在ではなく target.yaml authoring の摩擦。SSP は `AGENTS.md`
   Forward Design Note の正規 framing に従い「**deterministic security
   sensor delta を扱う sibling protocol、core verdict semantics を変更・拡張
   しない**」 protocol。core 入口の authoring 摩擦は sibling protocol の
   追加では解消されない。
2. **surface の独立性**: Brief 7 SSP は core verdict path から独立した
   sibling protocol(`docs/brief_7_planning.md §1`、`AGENTS.md` Forward
   Design Note「semantic-ci core を太らせない」 / 「SSP envelope と core
   verdict envelope は分離」)。Brief 8 が Authoring surface を整備しても
   SSP 設計に影響しない。
3. **共有ファイルの merge 面積**: 両 brief が触る箇所は
   `docs/code_semantic_ci_design.md §23.3.1` / `docs/json_schema.md` /
   `tests/architecture/`、いずれも別節 / 別 file で conflict は最小。
4. **Brief 8b(LLM 経路)との時系列**: Brief 8 完了後、Brief 8b 発行可。
   Brief 7 と Brief 8b の順序は Brief 8 完了後の状況で再評価。

`docs/code_semantic_ci_design.md §25` の Brief 表を CSCI-41 で更新し、
Brief 8 を Brief 7 より上(先発行)に並べる。

---

## 13. Open questions

1. **catalog の human format の詳細度**(CSCI-44): 全 operator / target
   展開 vs `--target-path` 部分参照 default。確定タイミング: CSCI-44 task
   brief 起草時。
2. **recipe registry の plugin 化**(CSCI-42): 本 brief は 4 recipe 内蔵のみ。
   `pyproject.toml` user-defined recipe は将来 brief。確定タイミング: Brief 8
   完走後の dogfood で需要観察してから。
3. **Brief 8b と Brief 7 の順序**(本 planning 範囲外): 両方 Brief 8 完了
   前提。確定タイミング: Brief 8 完走後。

---

## 14. CSCI Task Brief 起草時の checklist

各 CSCI を AGENTS.md フォーマットで Codex に渡す際、必ず Brief に記載:

- [ ] **Surface 配属**を明示(本 planning §5.1 表)
- [ ] **§5.2 INV-1〜INV-5** のうち該当番号を Acceptance に転記
- [ ] **`tests/architecture/`** test を増やすか(CSCI-42 / 43 / 44 でそれぞれ
      新設、対応 test 名を Brief に明記)
- [ ] **schema_version**(該当する場合)を §7 と一致
- [ ] **LLM / network**: 不使用を default、本 brief 全 PR で `httpx` /
      `requests` / `openai` / `anthropic` などの依存追加を Allowed Dependencies
      で **明示的に禁止**
- [ ] **既存 verdict envelope の byte-identical** を必ず acceptance に
      (除外領域は §5.2 INV-1 / INV-3 参照)
- [ ] **`--strict-advice` / `--llm-assist` / `--allow-candidate-derived-
      expectations` flag が CLI に存在しない**ことを test で固定
- [ ] **§15 brief drafting checklist** を起草前に走らせる(実 schema grep、
      cross-ref 同期確認、surface 越境 audit)
- [ ] **Codex への申し送り**: surface 越境は §23.3 違反として escalation
      対象(`AGENTS.md §3` rule 5)

---

## 15. Brief drafting checklist(再利用可能、20 round の蒸留)

新 brief / CSCI brief を書くとき / 既存 brief に変更を入れる時、**起草前**
に必ず走らせる checklist。各項目は `tests/architecture/` で構造保証 or
CSCI acceptance の cross-test に対応。

### 15.1 Schema grounding(spec を書く前に)

- [ ] **実 schema を grep して検証**: 提案する path / operator / match_schema
      key / template constraint が実装に存在することを以下のファイルで確認:
  - `src/semantic_ci_code/domain/state_schema.py`(Delta field)
  - `src/semantic_ci_code/evaluator/operators.py`(operator 名と semantic)
  - `src/semantic_ci_code/evaluator/evaluator.py`(template relaxation 経路)
  - `src/semantic_ci_code/compiler/templates.py`(`TEMPLATE_CONSTRAINTS` dict)
  - `src/semantic_ci_code/compiler/target_compiler.py`(allow_changes 等の policy hatch)
  - `src/semantic_ci_code/compiler/path_schema.py`(path validation)
  - `src/semantic_ci_code/framework/match_schema.py`(registry: required/optional/forbidden keys)
  - `src/semantic_ci_code/framework/target_svp.py`(field optionality / target-level keys)
- [ ] **template 説明は `TEMPLATE_CONSTRAINTS` dict を逐語参照**(brief 起草時
      に思い込みで書かない)
- [ ] **collection constraint の値形式**は実 delta producer の出力と一致
      (例: `new_cases` は `code_state_delta._test_case_id()` の `path::name`
      形式、Python-style FQN との取り違えは compile pass / evaluator 永久
      fail category)

### 15.2 Authoring intent の保存

- [ ] **修飾子(visibility / kind / scope)** が含まれる場合は **平坦投影
      alias を避け record match で強制**(match_schema registry の
      optional_keys を活用)
- [ ] **明示 user input は逐語保持**して constraint に反映(明示値を捨てて
      `not_equals []` だけ生成すると無関係な追加で pass する false negative)

### 15.3 Source merge / contract 整合

- [ ] **recipe contract の必須性は source merge 後に検証**(CLI parse 段階で
      reject しない、PR-body-only / issue-only flow を許す)
- [ ] **source 強度層を跨いで union しない**(strong layer 充足時に medium /
      lowest 層を参照しない、source 強度表と merge step の挙動を文面上一致)
- [ ] **`primary_kind` 推論は recipe ID とのバインディング完結時のみ意味が
      ある**(本 brief のように固定 recipe ID で constraint set を選ぶ設計
      では `--recipe` を source flag 使用時必須にし、推論だけで recipe を
      自動選択する silent fallback を入れない)
- [ ] **複数 strong source が同一 field を独立に決定し得る場合**は明示
      precedence + conflict error を planning レベルで固定(silent override /
      silent ignore は禁止)
- [ ] **conflict rule を立てた直後に各 case が自身の防御原則と整合している
      かを再 audit**(silent ignore 禁止と書いた直後に他 rule で silent ignore
      しないか、等)
- [ ] **declared intent と human prose の区別** は parser 側に固定 registry を
      持たせ silent guess を禁止(両用途の section は content grammar で
      明示分類、不明確な content は error)

### 15.4 CLI flag / source の整合

- [ ] **CLI flag を file list に追加する際は merge / consumption / provenance
      trigger の 3 点をすべて定義**(未定義なら削除)
- [ ] **source flag を expose する際は対応する parser file + provenance
      `source_surface` entry を必ず併設**(片方だけ追加しない)

### 15.5 Advisor 設計

- [ ] **検出可能で意味のある invalid pattern が現行 schema に実在することを
      必ず先に確認**(D5-LEGACY type の false positive 防止)
- [ ] **verdict 影響に関する advisor message** は `evaluator._aggregate` の
      VIOLATED / UNKNOWN 両 branch を確認(severity だけで判断せず
      unknown_policy との組合せで spec 化、半正確な advisor message は
      false advisory category)
- [ ] **Advisor 削除時** は file 列挙 / 関数 stub / acceptance count を
      すべて grep して整合化

### 15.6 Invariant の scope

- [ ] **byte-identical / import-graph 系 invariant の対象は意味論層に
      narrow**:
  - 比較対象は **evaluator-derived field**(`verdict` / `repair_plan` /
    `summary`)に限定、`target_authorship` field と `validate-plan.rendered`
    は除外(adapter / output layer が provenance を意図的に reflect する
    surface は invariant 対象外、reflect することがその surface の存在
    理由)
  - import-graph は **`cli/commands/<sub>.py` の transitive imports** に
    narrow、`cli/main.py` の subparser registration(全 subcommand handler を
    必然的 import)は対象外

### 15.7 他 brief / 他 doc 整合

- [ ] **他 brief への参照は `AGENTS.md` Forward Design Note の正規 framing を
      逐語使用**(SSP は「sibling protocol、core verdict semantics を変更
      しない」 が正規)
- [ ] **新 subcommand の exit code 表は `docs/exit_codes.md` の repo-wide
      policy(0 / 1 / 2 / 3 / 4)を必ず参照**(advisor / authoring surface
      でも usage error / engine error の silent success は禁止)
- [ ] **brief 内の repeated spec を 0 にする**: 各 spec の canonical 箇所を
      brief 内に 1 つ決め、他は cross-ref。表を更新したら **対応する spec
      文字列を grep で全箇所検出**(§0 / §2 Goals / §3 Non-goals / §5 各
      CSCI Goal / §10 acceptance / §11 R 行)し同期更新

### 15.8 同期更新の発火条件

以下を変更したら brief 全体の grep audit を必須化:

- recipe table → recipe contract / acceptance fixture / 「いずれか必須」 列挙
- merge step / fallback chain → recipe contract / acceptance fixture
- exit code 表 → §0 / §2 / §3 / §5 各 CSCI Goal 文 / §10 acceptance / §11
- invariant 範囲 → §4.1.1 cross-test note / §10 acceptance / R 行 / 各 CSCI
  acceptance
- registry(intent-declaring section、advisory list 等)→ parser file 列挙 /
  acceptance count

---

## Appendix A: Audit trail(round-1〜20)

PR #73 の 20 round / 計 28 P2 findings の category 別圧縮。本 brief 本文の
規律は §15 checklist に統合済、本表は履歴保存目的のみ。

### A.1 Schema grounding(brief 表が実 schema と乖離)

| # | Finding | 本文反映先 |
|---|---|---|
| a | `test_surface_delta.changed_or_added` 不在(`TestSurfaceDelta` は `new_files`/`new_cases`/`removed_cases` のみ) | §6.2.1 test-update recipe |
| b | `equals_baseline + allowlist` semantic 不在 | §6.2.1 refactor recipe |
| c | refactor template は user `subset_of` では緩まず `api_surface.allow_changes` 経由のみ | §6.2.1 refactor recipe |
| e | catalog example の `optional_keys: ["signature", "module"]` は registry と矛盾 | §6.4.2 catalog JSON |
| f | catalog に `kind` / `visibility` を出していない | §6.4.2 catalog JSON |
| j | bugfix template 説明が `compiler/templates.py` と乖離 | §6.2.1 bugfix recipe |
| t | `--test-case` の値形式が Python-style FQN想定で `_test_case_id()` の `path::name` と不一致 | §6.2.4 |

### A.2 Recipe / contract 整合

| # | Finding | 本文反映先 |
|---|---|---|
| d | `--test-case` 明示 FQN を捨てて `not_equals []` のみ生成 | §6.2.4 「逐語保持の理由」 |
| i | `feature:add-api` 必須引数固定で PR-body-only flow が CLI parse で reject | §6.2.3 precedence 表 + 「以下のいずれか必須」 |
| k | 平坦投影 alias で visibility 情報を捨てる | §6.2.1 feature recipe |
| w | merge step に medium layer を導入後、recipe contract 更新漏れ | §6.2.1 + §6.2.7 acceptance |
| z | `## Acceptance Criteria` を test-case 専用と分類して issue-only flow と矛盾 | §6.2.3 intent-declaring section registry |

### A.3 Source merge / precedence

| # | Finding | 本文反映先 |
|---|---|---|
| p | 複数 strong source の primary_kind 矛盾 silent 解決 | §6.2.3 precedence + C1〜C4 |
| q | C4 silent ignore が自身の防御原則と矛盾 | §6.2.3 C4 + intent-declaring registry |
| r | merge step が issue を strong sources の上に常に union | §6.2.3 fallback chain |
| s | labels/commits-only path で recipe 自動選択 mapping 無し | §6.2.3 「`--recipe` は recipe 生成の必須前提」 |

### A.4 Ghost flag / unconsumed flag

| # | Finding | 本文反映先 |
|---|---|---|
| l | `--allowed-import` が merge / consumption / provenance trigger 未定義 | (削除) |
| m | `--kind` flag が未消費(recipe ID で固定済) | (削除) |
| n | `--remove-api` flag が未消費 | (削除) |
| o | `--from-issue` flag に対応する parser / provenance entry 不在 | §6.2.6 + §6.2.5 |

### A.5 Invariant 過剰要求

| # | Finding | 本文反映先 |
|---|---|---|
| g | `ADVISORY-D5-LEGACY` は valid YAML を warn する false positive | §6.3.1 注記(D5 不実装) |
| h | D5 削除後も `hazards.py` 列挙に `D5-legacy` 残存 | §6.3.4 file list 整理済 |
| u | `ADVISORY-S1` の verdict 影響 message が VIOLATED branch のみで UNKNOWN を捨てる | §6.3.1 S1 spec |
| v | INV-2 を envelope 全体に書くと CLI dispatcher と矛盾 | §5.2 INV-2 narrow scope |

### A.6 Wall-clock / determinism

| # | Finding | 本文反映先 |
|---|---|---|
| - | wall-clock `declared_at` 自動埋め込みで determinism 違反 | §6.2.5 「declared_at は default omit」 |

### A.7 Spec drift / 同期更新漏れ

| # | Finding | 本文反映先 |
|---|---|---|
| aa | round-18 で §5.3 exit code を更新したが §10 acceptance は「常に 0」 残置 | §10 acceptance + §15.7 / §15.8 |
| bb | round-19 で §10 を更新したが §0.2 / §2 / §3 / §5.3 Goal 文に同型残置 | §15.8 grep audit 強制化 |

### A.8 他 brief / framing

| # | Finding | 本文反映先 |
|---|---|---|
| x | §12.3 で SSP を core 機能追加と framing(AGENTS.md 違反) | §12.3 sibling protocol framing |
| y | target-doctor exit code が 0 / 4 のみで repo-wide policy 違反 | §6.3.3 exit code 表 |
| - | INV-1 / INV-3 を envelope 全体で書くと `target_authorship` field と矛盾 | §5.2 INV-1 / INV-3 narrow scope |
| - | INV-1 / INV-3 が `validate-plan` で生成 metadata が rendered field に流れる設計と矛盾 | §5.2 INV-1 / INV-3 除外領域 |

履歴の各 finding の発覚 round 詳細は `git log docs/brief_8_planning.md` の
commit message 参照。

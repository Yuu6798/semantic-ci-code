# Brief 8 Planning — Authoring Surface (target.yaml provenance neutrality 実装)

> **Status: PLANNING (open, scope confirmed 2026-05-09)**.
>
> Brief 5(Vibe Coding Adapter + Repair Compiler、P2.5 entry)で確立した
> **§23.3 surface 区分**(Validator / Authoring / Provenance / Advisor)のうち、
> 実装が `init` scaffold 1 点だけにとどまっている **Authoring + Advisor +
> Provenance** の 3 surface を実コマンドに展開する brief。**完全決定論**で
> 設計し、LLM / network / API key を一切導入しない。
>
> 設計動機は session 2026-05-09 の議論で確定した次の最終決定:
>
> > target.yaml の難解さは Semantic CI core の本質的欠陥ではない。
> > core は declared intent に対する adherence を決定論的に判定する Validator
> > であり、intent の正しさ・完備性・作者の真意は判定しない。
> >
> > 改善対象は target.yaml を書く前後の Authoring / Advisor / Provenance
> > surface である。target.yaml は人間手書きである必要はなく、recipe、template、
> > PR metadata、commit message、label などから生成してよい。ただし、生成結果は
> > verdict 前に明示的な declared intent として固定され、生成経路・provenance・
> > advice は evaluator に参加してはならない。
>
> 初稿の draft 段階で 5 つの異論が出され、本 planning に **すべて反映済み**:
>
> 1. **LLM 経路を Brief 8 から完全除外**: `draft-target --llm-assist` は
>    `CLAUDE.md` の「LLM / network / API key を explicit Brief decision なしに
>    入れない」 default に抵触するため、本 brief から削除。LLM authoring は
>    **Brief 8b** として独立 brief で API key / network policy / vendor coupling /
>    failure semantics / process isolation / Authoring-only guarantee を個別設計
>    する。
> 2. **`target-doctor --strict-advice` を削除**: advisory output で exit 1 を
>    返すと §23.3.1 Advisor non-participation invariant を実態として破る。
>    target-doctor は **常に exit 0**(内部エラー除く)。CI gate が必要な
>    ユーザーは `--format json` を外部 workflow policy で処理する。
> 3. **Brief 8 を Brief 7(SSP)より先行**を明示。adoption bottleneck は
>    target.yaml authoring friction であり、SSP は Brief 8 完了後に発行する
>    (詳細 §12)。
> 4. **`compile --explain` を削除**: 既存 `compile --format human` /
>    `target-doctor` / `target-catalog` の 3 系統で十分。説明 command を
>    増やすと「どれを叩けば良いか分からない」 UX 退行を招く。
> 5. **`draft-target` を独立 subcommand として削除し、`init --recipe` に
>    統合**: deterministic-only なら両者の差分は薄い。`init` に
>    `--from-pr-body` / `--from-labels` / `--from-commits` を flag として
>    吸収し、subcommand 数を抑える。
>
> 結果として Brief 8 は **CSCI-41〜44 の 4 PR** に圧縮、Brief 5 と同等サイズ。

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
| `docs/target_yaml_guide.md` D1(`--package-root` scope vs `tests/`) | authoring hazard の機械化 | **CSCI-43** target-doctor の `ADVISORY-D1` |
| `docs/target_yaml_guide.md` D3(template と user constraint の重複) | 同上 | **CSCI-43** target-doctor の `ADVISORY-D3` |
| `docs/target_yaml_guide.md` D4(config-only PR の vacuous PASS) | 同上 | **CSCI-43** target-doctor の `ADVISORY-D4`(advisory のみ、verdict は変えない) |
| `docs/target_yaml_guide.md` D5(set operator partial-match) | PR #65 で Validator 側で解消済 | **CSCI-43** `ADVISORY-D5-LEGACY`(旧 schema_version="4" 形式の警告のみ) |
| 設計 §23.3.1 Authoring surface | scaffold だけでは authoring 行為(constraint DSL 落とし込み)を支援しきれない | **CSCI-42** init `--kind --recipe --from-pr-body --from-labels --from-commits` で recipe-driven 生成 + PR metadata 取り込みへ昇格 |
| 設計 §23.3.1 Provenance surface | `authorship.generation_metadata` を parse するが書き出しコマンドが無い | **CSCI-42** init recipe が generation_metadata(`source_surfaces`, `candidate_code_used: false`)を自動記録 |
| 設計 §23.3.1 Advisor surface | 既存 `validate-plan` は target.yaml が**正しく書かれている**前提。書く前段階の advisor が無い | **CSCI-43** target-doctor + **CSCI-44** target-catalog で穴埋め |
| session 2026-05-09 議論 | 「target.yaml は人間手書きである必要はない」を **設計文書に明記**する必要 | **CSCI-41**(docs)で `docs/target_authoring_surface.md` 新設 + 既存 docs cross-ref |

## 2. Goals

1. **§23.3.1 surface 境界を実装まで貫徹**: Authoring / Provenance / Advisor
   surface が verdict path に **絶対に介入しない**ことを CLI subcommand 単位で
   構造的に保証する(後述 §7 の不変条件 5 つ)。
2. **target.yaml 生成経路を 3 つに拡張**:
   - 手書き(現行)
   - **recipe + PR metadata**(`init --kind <K> --recipe <R> --from-pr-body
     pr.md --from-labels labels.json --from-commits commits.txt` から決定論的
     生成)
   - **catalog 参照**(AI assistant / IDE / 外部 tool が `target-catalog` の
     機械可読出力を見て生成する)
3. **authoring hazard を Advisor 化**: D1 / D3 / D4 / D5(legacy)
   + positive expectation 欠落 + severity downgrade 等を `target-doctor` で
   検出、verdict は変えない(exit code 常に 0、`--strict-advice` は **実装
   しない**)。
4. **Provenance metadata の自動記録**: `init --recipe` 系コマンドが
   `authorship.generation_metadata` を逐語で書き、`candidate_code_used: false`
   を default にする。candidate code 由来 expectation の生成経路は本 brief
   では一切実装しない。
5. **完全決定論**:
   - recipe / catalog / doctor / metadata 記録のすべてが LLM / network / API
     key を使用しない
   - 同 input → byte-identical output(各 CSCI の acceptance に明記)
6. **`semantic-ci check` の挙動を一切変更しない**: 既存 envelope schema /
   exit code / verdict 計算は本 brief で触らない(§7 不変条件 #1)。

## 3. Non-goals(本 brief 範囲外)

- **`semantic-ci check --auto-target`** — `check` 内で target を生成する経路は
  作らない(§23.3 違反、§7 不変条件 #2 で排除)。
- **LLM-assisted authoring(`--llm-assist` 系)** — 本 brief から完全除外。
  **Brief 8b** として独立 brief で扱う。Brief 8b で扱うべき論点:
  - API key / 環境変数管理(OPENAI_API_KEY / ANTHROPIC_API_KEY 等)
  - network 依存による install profile 変化
  - LLM provider 選定の vendor coupling
  - 「LLM 経路は authoring 限定」を構造的に保証する仕組み(import-graph では
    不十分、process / dependency 分離が必要)
  - 失敗時の semantics(API down / rate limit / hallucination → draft yaml
    不正の扱い)
- **candidate code から expected constraint を無条件生成** — `init --recipe`
  の default は `candidate_code_used: false`。opt-in flag は本 brief では
  実装しない(別 brief で安全策込みで議論)。
- **任意 Python 式 / 独自 DSL** — `target.yaml` は YAML + typed operator の
  ままにする(設計 §4 不変)。「authoring が難しいから DSL を自由化」は本
  brief で却下する選択肢として明記。
- **LLM-as-judge** — verdict path への LLM 混入は永続的に non-goal
  (`docs/code_semantic_ci_design.md §23.3` / Scope guard)。
- **intent の正しさ判定** — target-doctor は authoring hazard を出すが、
  「この intent は正しい / 間違っている」は判定しない(設計 §23.3.3)。
- **target-doctor `--strict-advice`** — advisory output で exit 1 を返す
  flag は実装しない。exit code は常に 0(内部エラー除く)。CI gate が必要な
  場合は `--format json` を外部 workflow policy で処理する運用とする。
- **`compile --explain`** — 既存 `compile --format human` / `target-doctor` /
  `target-catalog` の 3 系統で説明用途は十分。subcommand 過密を避けるため
  本 brief では追加しない。
- **standalone `draft-target` subcommand** — `init --recipe` に PR metadata
  flag を統合することで吸収。subcommand を独立させない。
- **non-Python artifact gating** — config / docs / workflow 専用の意味検証は
  Brief 7(SSP)/ 別 protocol の責務。本 brief では target-doctor が D4
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
│   user input ─┐                                          │
│   PR body ────┤                                          │
│   labels ─────┼──▶ init --kind --recipe ──▶ target.yaml  │
│   commits ────┤    (CSCI-42)                (declared    │
│                                              intent +    │
│                                              provenance) │
│                                                          │
│   AI assistant ──▶ target-catalog (CSCI-44, JSON)        │
│                                                          │
│   target.yaml ──▶ target-doctor (CSCI-43)                │
│                   (ADVISORY のみ、exit 0 固定)            │
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
| CSCI-42 init `--recipe` + sources | Authoring + Provenance | recipe + user input + PR metadata → target.yaml(決定論)+ generation_metadata 自動記録 | NO |
| CSCI-43 target-doctor | Advisor | target.yaml の hazard を render(verdict 不変、exit 0 固定) | NO |
| CSCI-44 target-catalog | Authoring(meta) | target / operator / template / match schema を機械可読出力 | NO |

#### 4.1.1 surface invariant の test での担保

各 CSCI は acceptance criteria に以下を**必ず含める**:

- **不変条件テスト**: 当該 subcommand を経由しても `check` / `compare` /
  `validate-plan` / `compile-repair` の verdict 出力が **byte-identical**
  であることを、共通 fixture で確認する(§7 不変条件 #1 の回帰)。
- **provenance 非参照テスト**: target.yaml に generation_metadata を
  書き換えても verdict envelope が変わらないことを確認(§7 不変条件 #3)。
- **no-LLM / no-network テスト**: 本 brief の全 subcommand 経路で `httpx` /
  `requests` / 外部 API client を import しないことを import-graph で確認
  (§7 不変条件 #4)。

## 5. CSCI 分割

合計 4 PR、おおむね各 0.5〜2 日。Brief 5 同等サイズ。

### 5.1 CSCI-41 (P0): 設計文書追記

**Goal**: target.yaml が hand-written 必須でないことを設計側で固定し、
今後の実装判断の前提を明文化する。

**追加 / 変更ファイル**:

- `docs/target_authoring_surface.md` (NEW): §23.3.1 を実装側から再記述。
  「declared intent は固定入力であり、生成経路は engine の関知外」を中心に、
  recipe / catalog 参照 / hand-written の 3 経路を一覧化。LLM 経路は
  Brief 8b で別途扱うことを脚注で明記。
- `docs/target_yaml_guide.md` (UPDATE): 冒頭に「target.yaml は人間が直接
  書く前提ではない」「複数の authoring 経路が許容されている」を pin、
  D1〜D5 の章末に「target-doctor で機械化予定」cross-ref を追記。
- `docs/code_semantic_ci_design.md §23.3.1` (UPDATE): Adjacent surfaces 表に
  `init --recipe` / `target-doctor` / `target-catalog` を追記、各々が
  verdict 不参加であることを脚注で明記。LLM 経路の Brief 8b 切り出しを
  脚注で補足。
- `CLAUDE.md` Required Reading 章 (UPDATE): Brief 8 着手前に
  `docs/target_authoring_surface.md` を読むよう追加。
- `README.md` (UPDATE): documentation 一覧に新規 doc を追加。
- `docs/cli_usage.md` (UPDATE): 「Authoring subcommands(verdict 不参加)」
  という新節を追加(具体的内容は CSCI-42〜44 で順次埋める、CSCI-41 では
  節見出しと §23.3.1 への cross-ref のみ)。

**Acceptance criteria**:

- [ ] `docs/target_authoring_surface.md` が以下 6 点を明記:
  (a) target.yaml は hand-written 必須でない
  (b) Brief 8 で実装される生成経路の 3 通り(recipe + sources / catalog
      参照 / hand-written)
  (c) LLM 経路は Brief 8b で別途扱う(本 brief では非導入)
  (d) 全経路は verdict 前に declared intent として固定される
  (e) Authoring / Advisor / Provenance surface は evaluator から参照不可
  (f) candidate-derived expectation は本 brief で実装しない、provenance
      `candidate_code_used` field は **必ず false** で記録
- [ ] CLAUDE.md docs table に新規 doc が status `ACTIVE` で登録
- [ ] `ruff check .` / `pytest -q` 通過(コード変更なし、docs only)

**Surface**: docs only。実装変更なし。
**Brief size**: 0.5 日。

### 5.2 CSCI-42 (P1): `semantic-ci init --kind --recipe --from-*`

**Goal**: 現行 `init` の skeleton 出力を壊さずに、recipe mode と PR metadata
取り込み(deterministic-only)を追加する。LLM / network 不使用、ユーザー
指定値と structured markdown section parser から明示 constraint を生成する。

**追加 / 変更ファイル**:

- `src/semantic_ci_code/cli/init_command.py` (UPDATE): `--kind` /
  `--recipe` / `--add-api` / `--test-case` / `--remove-api` /
  `--allowed-import` + `--from-pr-body` / `--from-labels` /
  `--from-commits` / `--from-issue` 引数を追加。
- `src/semantic_ci_code/cli/init_recipes/` (NEW directory):
  - `__init__.py`: `RECIPES` dict、`apply_recipe()` entry point
  - `feature_add_api.py`: `feature:add-api`
  - `bugfix_regression_test.py`: `bugfix:regression-test`
  - `refactor_preserve_api.py`: `refactor:preserve-api-with-allowlist`
  - `test_update_add_or_change.py`: `test-update:add-or-change-test`
- `src/semantic_ci_code/authoring/sources/` (NEW directory):
  PR metadata 系の deterministic parser
  - `__init__.py`
  - `pr_body.py`: structured markdown section parser
    (`## Expected public API` / `## Test cases` 等の固定セクションを抽出)
  - `labels.py`: `kind:feature` / `kind:bugfix` 等から `primary_kind`
  - `commits.py`: Conventional Commits prefix(`feat:` / `fix:` / `refactor:`
    / `test:`)から `primary_kind` 推定 hint
  - `merge.py`: source 強度に従って partial intent を merge
- `src/semantic_ci_code/authoring/provenance.py` (NEW):
  `build_generation_metadata(source_surfaces, candidate_code_used=False)`
- `src/semantic_ci_code/cli/main.py` (UPDATE): `init` subparser に新引数。
- `tests/cli/test_init_recipe.py` (NEW): 各 recipe で生成される YAML が
  expected と byte-identical(determinism)、生成 YAML が `compile` を
  pass する、`check` の verdict 出力が hand-written と recipe で
  byte-identical(同一 intent を表現する場合)。
- `tests/cli/test_init_sources.py` (NEW): PR metadata source parser の
  unit テスト + structured section が無い PR body で graceful degradation。

**Recipe 仕様(初期 4 件)**:

| Recipe ID | 必須引数 | 生成される positive expectation |
|---|---|---|
| `feature:add-api` | `--add-api FQN+`, optional `--test-case FQN*` | `api_surface_delta.added.fqns includes_all [FQN…]`, `test_surface_delta.new_cases not_equals []` (test-case 指定時) |
| `bugfix:regression-test` | optional `--test-case FQN*` | `test_surface_delta.new_cases not_equals []`, template により `api_surface_delta.removed_public == []` |
| `refactor:preserve-api-with-allowlist` | optional `--allow-add FQN*`, `--allow-remove FQN*` | allowlist 無し: `api_surface_public.equals_baseline`(strict)/ allowlist 有り: 既存 operator の組合せで表現(下表) |
| `test-update:add-test-case` | optional `--test-case FQN*` | `test_surface_delta.new_cases not_equals []`(`primary_kind=test_update` で template 展開) |

各 recipe は `change.primary_kind` を必ず設定し、template 展開は engine
側に委ねる(本コマンドは template constraint を **重複生成しない** ——
これが ADVISORY-D3 を踏まないための実装側保証)。

**`refactor:preserve-api-with-allowlist` の constraint 展開**:

allowlist semantic は **新規 operator を追加せず**、既存 set operator
(`subset_of` — PR #65 / CSCI-35c で確定)で表現する:

| `--allow-*` 指定 | 生成される constraint |
|---|---|
| 両方 unset | `api_surface_public equals_baseline`(strict baseline lock) |
| `--allow-remove` のみ | `api_surface_delta.removed_public subset_of [<allow-remove>]` |
| `--allow-add` のみ | `api_surface_delta.added.fqns subset_of [<allow-add>]` |
| 両方指定 | 上記 2 constraint を併記 |

`subset_of` は「実際の delta が allowlist の **部分集合**である」ことを
要求するため、「allowlist 内の API 変更のみ許可、それ以外は不許可」
という refactor invariant を新 operator なしで表現できる。
**equals_baseline operator に allowlist semantics を後付けしない**
(operators.py:200 の `_equals_baseline` は strict 等価のみ、本 brief
Non-goals 「新 operator 追加なし」を遵守)。

**test-update recipe の表現範囲**:

`TestSurfaceDelta` の現行 schema(`new_files` / `new_cases` /
`removed_cases` の 3 field、`domain/state_schema.py:144`)で表現可能な
範囲に限定し、存在しない path(`changed_or_added` 等)は使わない。
「既存 test case の修正(削除なし、追加なし)」は CodeState 上は
`new_cases` / `removed_cases` ともに空となるため delta では検知不能だが、
これは本 brief の射程外(`docs/target_yaml_guide.md` D4 と同型の構造的
限界)。test 修正 PR 全般を gate したいユーザーには target-doctor で
ADVISORY を出す方向は将来 brief で検討。

**Source 強度ポリシー**:

| Source | 強さ | 役割 |
|---|---|---|
| `--add-api` / `--test-case` / `--remove-api` / `--allow-add` / `--allow-remove`(明示 user input) | strong | positive expectation の確定値 |
| labels(`kind:feature` 等) | strong | `change.primary_kind` 決定 |
| PR body の structured section(`## Expected public API\n- FQN1\n- FQN2`) | strong | positive expectation の hint(明示 user input が無い時のみ採用) |
| issue acceptance criteria の structured section | medium | 同上 |
| commit message(Conventional Commits prefix) | medium | `primary_kind` の hint(labels が無い時のみ採用) |
| **candidate code body / observed semantic delta** | **本 brief で非実装** | tautology 化リスクのため、`--allow-candidate-derived-expectations` flag は **存在しない** |

**Provenance metadata**(必ず生成):

```yaml
authorship:
  declared_at: "2026-05-09T12:00:00Z"
  generation_metadata:
    tool: semantic-ci-init
    tool_version: "0.x.y"
    recipe: "feature:add-api"  # null if --recipe 未指定
    source_surfaces:
      - user_input
      - pr_body  # --from-pr-body が指定された場合のみ
      - labels
      - commits
    candidate_code_used: false  # 本 brief では常に false
    llm_used: false  # 本 brief では常に false
```

`candidate_code_used` / `llm_used` field の存在自体が §23.3 の Provenance
Invariant を **運用側で可視化**する(false が固定値である設計が tautology
と LLM 混入を防ぐ)。

**Acceptance criteria**:

- [ ] 4 recipe すべてが決定論的(同 input → byte-identical YAML、3 回繰返
      テスト)
- [ ] 生成 YAML は `compile` を pass(構文 / path / operator すべて妥当)
- [ ] **recipe が参照する path / operator が現行 schema に実在する**ことを
      cross-test:
  - `test_surface_delta.*` は `new_files` / `new_cases` / `removed_cases`
    のみ(`domain/state_schema.py:144` `TestSurfaceDelta`)
  - allowlist は `subset_of` で表現(`equals_baseline` に allowlist
    semantics を期待しない、`evaluator/operators.py:200` `_equals_baseline`
    は strict 等価のみ)
  - すべての recipe 出力で `compiler/path_schema.py` の path validation を
    pass
- [ ] `init` の既存 behavior(引数なし呼び出し)は不変、既存テスト全 pass
- [ ] LLM / network 呼び出しゼロ(`socket` / `httpx` / `requests` を import
      しないことを import-graph test で確認、§7 不変条件 #4)
- [ ] template と user constraint の重複が起きない(ADVISORY-D3 が空に
      なる、CSCI-43 land 後の cross-test で確認、本 PR では unit-level で
      重複ゼロを assert)
- [ ] PR body / issue に structured section が無い場合は **degrade** して
      動作(明示 user input + recipe default のみで YAML 生成)、source
      surface に該当 source を含めない
- [ ] generation_metadata.candidate_code_used が **常に false**(test で
      固定)、`--allow-candidate-derived-expectations` flag が**存在しない**
      ことを CLI argparse spec で確認
- [ ] verdict 不変条件テスト(§7 #1)

**Brief size**: 1.5〜2 日。

### 5.3 CSCI-43 (P2): `semantic-ci target-doctor`

**Goal**: target.yaml の authoring hazard を Advisor として render する
新 subcommand。verdict は変えない(exit code 常に 0、内部エラー時のみ 4)。
`--strict-advice` のような advisory→fail 化 flag は **実装しない**。

**追加 / 変更ファイル**:

- `src/semantic_ci_code/cli/commands/target_doctor.py` (NEW)
- `src/semantic_ci_code/cli/main.py` (UPDATE): subparser 追加
- `src/semantic_ci_code/authoring/` (UPDATE): advisory 検出ロジック追加
  (CSCI-42 で初出した `authoring/` directory を共有)
  - `hazards.py` (NEW): 各 hazard 検出関数(D1 / D3 / D4 / D5-legacy / P1 /
    P2 / S1)
  - `advisory.py` (NEW): `Advisory` dataclass(`code`, `severity`,
    `message`, `evidence`)
- `src/semantic_ci_code/cli/output/doctor_human.py` (NEW)
- `src/semantic_ci_code/cli/output/doctor_json.py` (NEW)
- `src/semantic_ci_code/schemas/doctor_advisory.schema.json` (NEW)
- `tests/cli/test_target_doctor.py` (NEW)
- `tests/architecture/test_surface_isolation.py` (NEW): §7 不変条件 #2 / #4
  の import-graph 検査(本 brief 横断テストの起点)

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
  [--format human|json]
```

**Exit code 規約**:

| 条件 | exit code |
|---|---|
| advisory 0 件 | 0 |
| advisory ≥ 1 件 | **0** |
| 内部エラー | 4 |

`--strict-advice` flag は **存在しない**。CI で advisory 0 件を gate
したい場合は `--format json` 出力を外部 workflow policy(GitHub Actions
の `if` / 別スクリプト)で処理する。`docs/cli_usage.md` に運用例を
記載するが、それは workflow recipe であって engine verdict ではない。

**Determinism**:

- D1〜D5-LEGACY / P1 / P2 / S1 は target.yaml 単独で決定論
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
- [ ] exit code は advisory の有無に関わらず 0(内部エラー除く)
- [ ] `--strict-advice` flag が **存在しない**ことを CLI argparse spec で
      確認
- [ ] determinism test(同 input 3 回 → byte-identical)
- [ ] `tests/architecture/test_surface_isolation.py` で
      target-doctor 経路に `httpx` / `requests` / `openai` /
      `anthropic` が import されないことを assert(§7 不変条件 #4)

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
- `tests/architecture/test_catalog_implementation_parity.py` (NEW):
  §7 不変条件 #5

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
      catalog 出力を比較、§7 不変条件 #5)
- [ ] `--kind feature` で template 展開が想定通り
- [ ] determinism test、verdict 不変条件テスト(§7 #1)
- [ ] human format が target.yaml authoring user(人間)に読める粒度
- [ ] LLM / network 呼び出しゼロ(import-graph、§7 不変条件 #4)

**Brief size**: 1 日。

## 6. Schema / envelope 影響

新規 envelope:

| Envelope | Schema version | Surface | 関連 CSCI |
|---|---|---|---|
| `target-doctor` advisory output | `advisory-1` | Advisor | CSCI-43 |
| `target-catalog` reference output | `catalog-1` | Authoring meta | CSCI-44 |

既存 envelope の schema_version は **bump しない**:

- verdict envelope: `"5"`(PR #65 で確定、本 brief 不変)
- compile envelope: `"5"`(同上)
- compile-repair envelope: `"1"`(不変)
- validate-plan envelope: `"1"`(不変)

`docs/json_schema.md` には新規 envelope 2 つを追記し、それぞれ独立
schema として `schemas/` に登録する。**verdict envelope と混ざらない**
(SSP envelope 設計と同じ思想、`docs/brief_7_planning.md §6` の鏡像)。

target.yaml 自体の schema は **不変**(`init --recipe` は既存 schema に
従う YAML を出力する。`generation_metadata` block は既存の任意 field の
populate)。

## 7. Determinism / surface invariants

実装で**構造的に保証する**5 つの不変条件:

1. **Verdict bytes invariant**:
   `check` / `compare` / `validate-plan` / `compile-repair` の JSON envelope
   は本 brief の全変更後も既存 fixture で byte-identical。
   → CSCI-42〜44 すべての acceptance に「verdict 不変条件テスト」を含める。

2. **`check` does not generate target invariant**:
   `check` 経路から `init` / `target-doctor` / `target-catalog` の
   いずれの module も import されない。
   → import-graph test を `tests/architecture/test_surface_isolation.py`
   (CSCI-43 で新設)で固定。

3. **Provenance non-participation invariant**:
   target.yaml の `authorship.generation_metadata` を任意に書き換えても
   verdict envelope は byte-identical。
   → fixture を 1 つ作り、generation_metadata の有無 / 値違いで verdict
   を回し、出力 hash を比較する(CSCI-42 acceptance)。

4. **No-LLM / no-network invariant**:
   本 brief で追加・変更されたすべての subcommand 経路で `httpx` /
   `requests` / `openai` / `anthropic` / `urllib3` などの
   network/LLM client を import しない。
   → `tests/architecture/test_surface_isolation.py` で全 authoring
   subcommand に対して assert。

5. **Catalog ↔ implementation parity invariant**:
   `target-catalog` の出力に登録された operator / target / template が
   evaluator 実装と一致する。
   → `tests/architecture/test_catalog_implementation_parity.py`
   (CSCI-44 で新設)で cross-test。

これら 5 不変条件は **本 brief 完了の必要十分条件**であり、各 CSCI の
acceptance には対応する不変条件番号を明記する。

## 8. CLI surface 全体像(after-state)

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

合計 10 subcommand(現在 8 + 新規 2、`init` は拡張)。
**Validator 5 / Advisor 3 / Authoring 2** で surface バランスが取れる
(`init` は Authoring + Provenance、`compile` は Validator readback として
カウント)。

## 9. テスト戦略

### 9.1 各 CSCI 単位

- **unit**: hazards / recipes / catalog builder / source parser を関数単位
- **CLI integration**: 各 subcommand の golden fixture
- **determinism**: 同 input 3 回呼び出して byte-identical
- **schema valid**: 各 JSON 出力が JSON schema 通過

### 9.2 Brief 全体で要求する横断テスト(`tests/architecture/` 新設)

- `test_surface_isolation.py`(CSCI-43 で新設): §7 不変条件 #2 / #4 の
  import-graph 検査
- `test_verdict_bytes_invariant.py`(CSCI-42 で新設): §7 不変条件 #1 / #3
  の golden hash
- `test_catalog_implementation_parity.py`(CSCI-44 で新設): §7 不変条件 #5

`tests/architecture/` ディレクトリ自体は本 brief で初出。Brief 7 が後続で
SSP envelope を分離する際にも同ディレクトリの不変条件 test pattern が再利用
できる(envelope 分離は両 brief 共通の関心)。

### 9.3 Dogfooding

CSCI-42(init recipe + sources)land 後、`docs/dogfooding_TC10_report.md`
の TC1〜TC10 を **init --recipe で再生成して `compile` を pass するか** を
小規模 dogfood として実施し、本 brief 内の最終 PR(CSCI-44)で記録する。
これで「recipe 4 種で実用 PR の大半をカバーできる」が経験的に検証される。

## 10. Brief 全体 Acceptance Criteria

- [ ] CSCI-41〜44 全 PR が merged
- [ ] §7 不変条件 5 件すべてが test で固定されている
- [ ] `docs/target_authoring_surface.md` が新設、CLAUDE.md docs table に
      ACTIVE で登録
- [ ] `docs/cli_usage.md` に `init --recipe + --from-*` / `target-doctor` /
      `target-catalog` のセクションが追加
- [ ] `docs/exit_codes.md` に target-doctor の exit code 規約(常に 0)が
      明記される
- [ ] `docs/json_schema.md` に `advisory-1` / `catalog-1` envelope が追記
- [ ] CLAUDE.md `次の発行順序` から本 brief 行が削除、Brief 8 が
      `直近 merged` に移動。Brief 7(SSP)発行を本 brief 後に置く順序が
      `docs/code_semantic_ci_design.md §25` に反映される
- [ ] `ruff check .` / `pytest -q` 全 pass
- [ ] verdict envelope の既存 fixture が **すべて byte-identical**
      (本 brief は verdict 不変が大原則)
- [ ] LLM / network 呼び出しがゼロであることが import-graph で固定
      (本 brief 完全決定論)

## 11. リスクと回避

| リスク | 内容 | 回避策 |
|---|---|---|
| **R1 surface 越境** | target-doctor の advisory が evaluator に流れて verdict を変えてしまう | §7 不変条件 #1 + #2 の import-graph test、CSCI-43 で `tests/architecture/` 新設して構造的に固定 |
| **R2 candidate-derived tautology** | init recipe が candidate code を読み expected を生成、同 candidate を check して PASS する vacuous loop | `--allow-candidate-derived-expectations` flag を **本 brief で実装しない**、provenance `candidate_code_used` を必ず false で記録、CLI argparse spec で flag 不在を test 固定 |
| **R3 LLM 経路の意図せぬ混入** | 将来の dependency 追加で `openai` / `anthropic` 等が入る | §7 不変条件 #4 の import-graph test を本 brief で固定。Brief 8b で LLM 経路を追加する際は、本 invariant の境界(authoring subcommand のみ許可、verdict path には絶対不参加)を再確認 |
| **R4 catalog drift** | catalog と evaluator 実装が乖離し、AI assistant が無効な target.yaml を生成 | §7 不変条件 #5 の cross-test を CSCI-44 acceptance に含める |
| **R5 advisory ノイズ** | target-doctor が誤検知だらけで信用されない | 各 advisory に false-positive 防止 fixture を必ず 1 件持つ(§5.3 acceptance) |
| **R6 recipe 不足で結局手書き** | 4 recipe で大半の PR をカバーできない | session 2026-05-09 議論で「4 recipe で大半 cover」の見積、§9.3 dogfood で経験的検証、不足時は CSCI-42 follow-up で追加 recipe を増やす(後方互換破壊なし) |
| **R7 init 既存 behavior 退行** | `init` の引数なし呼び出しが broken | CSCI-42 acceptance に「既存 behavior 不変」を test で固定 |
| **R8 PR body parser の脆弱性** | non-structured な PR body で誤動作 / クラッシュ | structured section が存在しない場合は **graceful degrade**(明示 user input + recipe default のみで生成、source surface に該当 source を含めない)、CSCI-42 acceptance に明記 |
| **R9 recipe schema grounding ずれ** | recipe が現行 schema に存在しない path / operator semantics を生成し、`compile` で fail(初稿で `test_surface_delta.changed_or_added` / `equals_baseline + allowlist` の 2 件発覚、PR #73 codex review で指摘) | recipe 表は **必ず実 schema を grep して検証**(`domain/state_schema.py` / `evaluator/operators.py` / `compiler/path_schema.py`)、CSCI-42 acceptance に schema cross-test を含める、Non-goals「新 operator 追加なし」を recipe 設計時に再確認 |

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

CSCI-43(target-doctor)を CSCI-42 より先に出す理由:

- `tests/architecture/` を最初に立てることで、後続 CSCI が surface 越境
  リスクを引きずらない(R1 早期に固定)
- D1〜D4 の advisory 化が CSCI-42 recipe 設計の検証ツールになる
  (recipe 出力で D3 が検出されないことを cross-test できる)

CSCI-42 を CSCI-43 の後ろに置くことで、recipe 出力が doctor を pass する
ことを recipe テストで保証できる(両者 simultaneous 開発でも順序差は最小)。

### 12.3 Brief 7(SSP)との関係 — Brief 8 先行を確定

**Brief 8 を Brief 7 より先に発行することを本 planning で確定する**。
判断根拠:

1. **adoption bottleneck の所在**: session 2026-05-09 までの議論で、
   現時点の adoption 障壁は SSP の不在ではなく、target.yaml authoring の
   摩擦であることが確認された。SSP は **まだ誰も使っていない core に
   セキュリティ機能を追加**する性質で、adoption 改善には寄与しない。

2. **surface の独立性**: Brief 7 SSP は core verdict path から独立した
   protocol(`docs/brief_7_planning.md §1` で確認済)。Brief 8 が core の
   入口側 Authoring surface を整備しても、SSP 設計に影響しない。順序を
   入れ替えても SSP の design / spec は変わらない。

3. **共有ファイルの merge 面積**: Brief 7 と Brief 8 が両方触る箇所は
   `docs/code_semantic_ci_design.md §23.3.1` / `docs/json_schema.md` /
   `tests/architecture/`。いずれも別節 / 別 file で、conflict は最小。

4. **Brief 8b(LLM 経路)との時系列**: Brief 8 完了後、Brief 8b
   (LLM authoring)を発行可。Brief 7(SSP)は Brief 8b の前後どちらでも
   発行可能(独立性が高い)。推奨順:
   `Brief 8 → Brief 7 → Brief 8b` または `Brief 8 → Brief 8b → Brief 7`。

`docs/code_semantic_ci_design.md §25` の Brief 表を CSCI-41 で更新し、
Brief 8 を Brief 7 より上(先発行)に並べる。

## 13. Open questions

初稿の 5 点(LLM / strict-advice / 順序 / explain / draft-target 統合)は
すべて解決済み。残る Open は次の 3 点のみ:

1. **catalog の human format をどこまで詳細にするか**(CSCI-44)
   - 案 A: 全 operator + target を 1 ページに展開(長くなる)
   - 案 B: `--target-path X` で部分参照を default にする
   - 推奨: 両方サポート、`--target-path` 無し時は summary のみ表示し
     詳細は JSON へ(human ヒューリスティクス)
   - 確定タイミング: CSCI-44 task brief 起草時

2. **recipe registry の plugin 化を将来許容するか**(CSCI-42)
   - 本 brief: 4 recipe 内蔵のみ
   - 将来 brief で `pyproject.toml` に書ける user-defined recipe を許容
     する余地を残すかは Open(CSCI-42 では internal dict のみ)
   - 確定タイミング: Brief 8 完走後の dogfood で需要を観察してから

3. **Brief 8b(LLM authoring)を Brief 7 より先に発行するか後にするか**
   - Brief 8 が先、これは確定(§12.3)
   - Brief 8b と Brief 7 の順序は本 planning 範囲外(両方が Brief 8
     完了を前提とする)
   - 確定タイミング: Brief 8 完走後の状況で再評価

## 14. CSCI Task Brief 起草時の checklist

各 CSCI を AGENTS.md フォーマットで Codex に渡す際、必ず以下を Brief に
記載する:

- [ ] **Surface 配属**を明示(本 planning §4.1 の表を参照)
- [ ] **§7 不変条件**のうち該当する番号を Acceptance に転記
- [ ] **`tests/architecture/`** の test を増やすか(CSCI-42 / 43 / 44 で
      それぞれ新設、対応 test 名を Brief に明記)
- [ ] **schema_version**(該当する場合)を本 planning §6 と一致させる
- [ ] **LLM / network**: 不使用を default、本 brief 全 PR で `httpx` /
      `requests` / `openai` / `anthropic` などの依存追加を Allowed
      Dependencies で **明示的に禁止**
- [ ] **既存 verdict envelope の byte-identical** を必ず acceptance に
- [ ] **`--strict-advice` / `--llm-assist` / `--allow-candidate-derived-
      expectations` などの flag が CLI に存在しない**ことを test で固定
- [ ] **Codex への申し送り**: surface 越境は §23.3 違反として escalation
      対象(AGENTS.md §3 の rule 5)

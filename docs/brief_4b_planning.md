# Brief 4b Planning — CI integration outputs (SARIF + GH Actions + pre-commit manifest)

> **STATUS: Brief 4b complete (2026-05-05).**
> CSCI-28 (PR #40) として merged。`semantic-ci compare` / `check` / `pre-commit` で
> `--format sarif` / `--format gh-actions` が動作し、`.pre-commit-hooks.yaml` manifest
> もリポジトリ同梱(`semantic-ci` / `semantic-ci-smoke` 2 hook)。Brief 4 Open
> Questions Q9 / Q10 / Q11 は全て resolved。本文書は Brief 5 / Brief 7 起草時の
> reference として retain する。後続の dogfooding 結果や hardening は
> `dogfooding_TC10_report.md` と `.claude/memory/2026-05-07.md` を参照。

> Brief 4 (CSCI-15〜19) で確立した `semantic-ci` CLI 5 subcommand の上に、
> CI integration 向けの 3 つの追加出力経路を 1 PR で完結させる薄い follow-up brief。
> Brief 4b 完了で `semantic-ci` は GitHub Actions / pre-commit framework / SARIF
> 互換セキュリティスキャナの 3 経路から呼び出し可能になる。

## 位置付け

`docs/code_semantic_ci_design.md §25` の Brief 4b 行 + `docs/brief_4_planning.md §11` で
予告されていた CI integration 出力を実装する。本 brief 完結で:

- Brief 4 の Open Questions Q9 / Q10 / Q11 が全て resolved
- Brief 5 (P2.5 entry: Vibe Coding Adapter + Repair Compiler) が「CI 経路は揃った」
  前提で planning できる
- Brief 4c (effects extractor `fqn` semantics 修正) と並列発行可

## 1. 救済される未解決項目

| 出典 | 項目 | 本 brief での扱い |
|---|---|---|
| `brief_4_planning.md §10 Q9` | SARIF 出力 | **CSCI-28** で `--format sarif` を追加 |
| `brief_4_planning.md §10 Q10` | GitHub Actions annotation | **CSCI-28** で `--format gh-actions` を追加 |
| `brief_4_planning.md §10 Q11` | pre-commit framework manifest | **CSCI-28** で `.pre-commit-hooks.yaml` を repo 同梱 |
| `design.md §25` Brief 4b 行 (PR #36 で確定) | Q9 + Q10 + Q11 を 1 brief で扱う | 同上 |

## 2. Goals

1. **SARIF 2.1.0 出力**: `--format sarif` で verdict 結果を SARIF JSON にエンコード。
   `compare` / `check` / `pre-commit` の verdict 出す系 subcommand で動作。
2. **GitHub Actions annotation 出力**: `--format gh-actions` で workflow command
   (`::error` / `::warning` / `::notice`) を stdout に出力。GH Actions runner が
   PR review に annotation として反映する。
3. **pre-commit framework manifest**: repo root に `.pre-commit-hooks.yaml` を同梱。
   他 repo から `repos: - repo: https://github.com/Yuu6798/semantic-ci-code` で
   `semantic-ci pre-commit` を hook として呼べる状態にする。

## 3. Non-goals (本 brief 範囲外)

- **GitHub Actions marketplace publication** — packaging とは別 workflow、別 brief。
- **SARIF を verdict 計算に巻き込む** — SARIF は出力エンコードのみ、内部 model は不変。
- **pre-commit hook の auto-fix** — 構造化 RepairPlan の出力のみ。Repair Compiler は Brief 5。
- **Codeberg / GitLab CI 等の他 CI 向け annotation** — P4 範囲。
- **SARIF v2.2** — 2.1.0 (OASIS standard) のみ対応。
- **verdict envelope JSON schema の bump** — SARIF / gh-actions は別 envelope、verdict
  envelope は v2 のまま据え置き。
- **`observe` / `compile` での SARIF / gh-actions** — verdict を出さない subcommand
  なので意味的に未対応 (exit 2)。

## 4. SARIF 出力設計 (2.1.0)

### 4.1 Schema 構造

SARIF 2.1.0 の最小構成:

```json
{
  "$schema": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/cs01/schemas/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "semantic-ci",
          "version": "0.x.x",
          "semanticVersion": "0.x.x",
          "informationUri": "https://github.com/Yuu6798/semantic-ci-code",
          "rules": [
            {
              "id": "<constraint_id>",
              "name": "<constraint_id>",
              "shortDescription": { "text": "<rule label>" },
              "defaultConfiguration": { "level": "error" }
            }
          ]
        }
      },
      "invocations": [
        {
          "executionSuccessful": true,
          "exitCode": 0,
          "properties": {
            "extractor_pyver": "3.11",
            "package_version": "0.x.x"
          }
        }
      ],
      "results": [
        {
          "ruleId": "<constraint_id>",
          "level": "error",
          "message": { "text": "<violation message>" },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "<relative path>" },
                "region": { "startLine": 42 }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### 4.2 Severity mapping

| ConstraintResult status + RepairInstruction category | SARIF level |
|---|---|
| `status=violated` & `category=FIX_REQUIRED` (= severity hard 違反) | `error` |
| `status=violated` & `category=SUGGESTED` (= REPAIR tier) | `warning` |
| `status=unresolved` (extractor 失敗 / unknown_policy=warn) | `warning` |
| `category=INFO` | `note` |
| `status=skipped` (smoke mode 等の partial extraction) | `note` |
| `status=satisfied` | **results に出力しない** (SARIF results は違反のみ) |

### 4.3 Rules vs Results の関係

- `rules[]` は `runs[0].tool.driver.rules` に **precomputed**(SARIF spec 推奨)。
  各 constraint id を 1 rule として宣言、`shortDescription.text` に template 名 or
  user-provided id をセット。
- `results[]` は `ruleId` で rules を参照。message は instruction.message を転記。
- ruleId は JSON envelope の `results[].constraint_id` と完全一致。doc / SARIF 経由で
  追跡できるよう同 identifier を維持。

### 4.4 Locations 戦略

- `evidence` に `file` / `line` を持つ制約のみ `physicalLocation` を埋める
  (effects 制約 / api_surface 一部 / template 制約は line 不明 → location 省略可)。
- `artifactLocation.uri` は **repository root からの相対 path**(SARIF spec が推奨)。
  `compare` 時は `--candidate-dir` を root とし、その下からの相対。`check` / `pre-commit`
  時は git working tree root を root とする。
- `region.startLine` のみ。`startColumn` は extractor が出さないので omit。

### 4.5 出力 mechanism

- 既存 `--format {json,human}` を `{json,human,sarif,gh-actions}` に拡張。
- `--output <file>` で SARIF を file に書き出す (CI 標準 pattern: `--format sarif --output results.sarif`)。
- subcommand 制限: `compare` / `check` / `pre-commit` のみ許容。`observe` / `compile` で
  指定すると **exit 2 (USAGE)**。
- `--strict-repair` の解釈は SARIF 出力に影響しない (exit code policy のみ変える)。

### 4.6 決定論

既存 JSON 出力同様:
- field 挿入順固定 (Python 3.7+ dict insertion order)
- `indent=2`, `ensure_ascii=False`, LF 改行
- `results[]` は constraint 評価順 (CSCI-13 で確立済み順序)
- `rules[]` は `results[]` で初出順 (重複 dedupe しつつ順序保持)
- PYTHONHASHSEED 異値で byte-identical (既存 determinism test pattern)

## 5. GitHub Actions annotation 出力設計

### 5.1 Workflow command syntax

GH Actions の workflow command (`::error file=path,line=N::message` 等) を stdout に出力。

```text
::error file=src/api/users.py,line=42::Constraint feature_added violated: missing api_surface_delta.added entry
::warning file=src/models/user.py,line=12::Constraint complexity_budget exceeds tolerance
::notice::Constraint test_added skipped (smoke mode)
```

### 5.2 Severity mapping

| RepairInstruction category | GH command |
|---|---|
| `FIX_REQUIRED` | `::error` |
| `SUGGESTED` (REPAIR tier) | `::warning` |
| `INFO` | `::notice` |
| `unresolved` | `::warning` |
| `skipped` | `::notice` |
| `satisfied` | 出力しない |

### 5.3 Escaping (GH Actions spec)

GH Actions workflow command は以下のエスケープが必要:
- `%` → `%25`
- `\r` → `%0D`
- `\n` → `%0A`
- properties 内の `,` → `%2C`
- properties 内の `:` → `%3A`

`message` 部分には改行/`%`/`:`が混入する可能性あり、必ずエスケープ。

### 5.4 出力 mechanism

- stdout に出す (GH Actions runner が parse する標準経路)。
- `--output <file>` 指定は **exit 2** (file 出力は GH Actions が parse しないので意味なし)。
- ANSI なし、`--no-color` 自動相当。
- 末尾に summary line 1 行 (`# semantic-ci: 2 fix required, 1 suggested, 0 info`)。
  workflow command syntax の `::` prefix とは衝突しない (`#` で開始するため)。
- subcommand 制限: SARIF と同じ (`observe` / `compile` で exit 2)。

### 5.5 file path 戦略

- `--candidate-dir` (compare) / git working tree root (check / pre-commit) からの相対 path。
- GH Actions は `${{ github.workspace }}` 起点で path を解決するので、それと整合する。
- Action 内 invocation を想定: `working-directory: .` で `semantic-ci check --format gh-actions`。

## 6. `.pre-commit-hooks.yaml` 設計

### 6.1 ファイル内容

repo root の `.pre-commit-hooks.yaml`:

```yaml
- id: semantic-ci
  name: Semantic CI (pre-commit mode)
  description: Run semantic CI on staged Python changes
  entry: semantic-ci pre-commit
  language: python
  types: [python]
  pass_filenames: false
  require_serial: true
  stages: [pre-commit]
```

### 6.2 設計判断

| key | 値 | 理由 |
|---|---|---|
| `id` | `semantic-ci` | pre-commit framework 内の hook id |
| `entry` | `semantic-ci pre-commit` | 既存 subcommand を直接呼ぶ |
| `language` | `python` | console_script 経由、pre-commit が venv を作る |
| `types` | `[python]` | Python file が staged のときのみ trigger |
| `pass_filenames` | `false` | semantic-ci pre-commit は git index を直接読んで diff を計算するため、file 引数は不要 |
| `require_serial` | `true` | subprocess + git worktree 操作の並列実行を防ぐ |
| `stages` | `[pre-commit]` | commit-msg / push hook には乗らない |

### 6.3 ユーザ視点の使い方

他 repo で:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yuu6798/semantic-ci-code
    rev: v0.x.x  # tag 必須 (pre-commit framework 仕様)
    hooks:
      - id: semantic-ci
```

`pre-commit run --all-files` または `pre-commit run` (staged のみ) で実行。

### 6.4 制約

- pre-commit framework は `rev:` に **tag を要求**。release tag を切る運用に乗る前提。
  Brief 4b の本 PR では tag は切らない (リリース時に別 PR で切る)。
- `pre-commit try-repo .` で local validate 可 (本 PR の test に組み込む)。

## 7. CLI surface 変更 summary

| 変更 | 内容 |
|---|---|
| `--format` 値域 | `{json,human}` → `{json,human,sarif,gh-actions}` |
| `compare` / `check` / `pre-commit` での `--format sarif` | 許容、SARIF を出力 |
| `compare` / `check` / `pre-commit` での `--format gh-actions` | 許容、workflow command を stdout に出力 |
| `observe` / `compile` での `--format sarif|gh-actions` | exit 2 (USAGE) |
| `--format gh-actions --output <file>` | exit 2 (file 出力は意味なし) |
| `--format sarif --output <file>` | 許容 (SARIF は file 出力 OK) |
| 既存 `--format json` / `--format human` | 挙動変更なし |
| 5 subcommand の他引数 | 変更なし |

## 8. JSON schema 影響

**なし**。SARIF と gh-actions はそれぞれ独立した出力フォーマット、verdict envelope JSON schema は v2 のまま据え置き。

`docs/json_schema.md` に「SARIF / gh-actions は別 envelope であり verdict envelope の compatibility policy に縛られない」 旨を 1 段落追記。

## 9. Test 計画

### 9.1 SARIF 出力
- fixture 1 件 (fail verdict + 1 violation with file:line evidence) で SARIF JSON を生成
  - `runs[0].tool.driver.name == "semantic-ci"` を assert
  - `runs[0].tool.driver.rules[]` に違反した constraint id が含まれる
  - `runs[0].results[]` に `level=="error"` の entry が 1 件
  - `runs[0].results[0].locations[0].physicalLocation.artifactLocation.uri` に相対 path
  - `runs[0].invocations[0].properties` に `extractor_pyver` / `package_version` が転記
- fixture 1 件 (pass verdict) で `results[]` が空配列 (satisfied は出ない)
- determinism: PYTHONHASHSEED 異値で byte-identical

### 9.2 GH Actions annotation
- fixture 1 件 (repair / fail) で stdout を行ベース parse
  - `::error file=...,line=...::msg` 形式
  - `::warning` / `::notice` も category 別に発火
  - GH Actions escaping (`%0A` / `%25` / `%3A` など) が message に適用される
- fixture 1 件 (pass) で workflow command 0 件 + summary line 1 行
- `--format gh-actions --output <file>` で **exit 2**

### 9.3 pre-commit manifest
- `.pre-commit-hooks.yaml` を YAML パース → 必須 key (id, entry, language, types) 揃う
- 値の型と値 (`pass_filenames: false`, `require_serial: true`, `stages: [pre-commit]`) 一致
- `pre-commit try-repo .` を subprocess で起動して hook 認識を確認 (CI で pre-commit が
  install できる前提、無理なら静的 YAML 検証のみで OK)

### 9.4 既存 test 影響
- 既存 CLI tests は `--format` choice 拡張による影響を受けない (引数 parser だけ拡張)。
- 既存 JSON / human output の golden file は無変更。

## 10. PR split

**1 PR (CSCI-28) で完結**。SARIF + gh-actions + manifest の 3 件は:

- 別ファイル (`output_sarif.py` / `output_gh_actions.py` / `.pre-commit-hooks.yaml`) で互いに干渉しない
- 共通変更点は `cli/main.py` の `--format` choices 拡張のみ
- test 込み 400-600 行想定、1〜1.5 日規模 (AGENTS.md target 0.5-2 日に収まる)

実装中に SARIF だけが膨らむ場合のみ事後分割 (CSCI-28a SARIF / CSCI-28b gh-actions+manifest) を許容。Codex が判断して escalate 可能。

## 11. Allowed dependencies

**なし**。SARIF / gh-actions / manifest はいずれも標準 stdlib (json / yaml は既存 dep) で実装可。

## 12. Open Questions / decisions before implementation

1. **SARIF の `helpUri`**: rule per constraint id に doc URL を埋めるか?
   - 推奨: **本 brief では omit**。P3a empirical alignment 段階で必要なら導入。
   - 理由: `docs/code_semantic_ci_design.md` の anchor は public URL として stable でない。
2. **SARIF rules の `defaultConfiguration.level`**:
   - hard 制約は `"error"` / soft 制約は `"warning"` を default に置くか、全部 `"error"` でいくか?
   - 推奨: **constraint の `severity` に従う**。template から compile した制約は severity を持つ。
3. **gh-actions の `summary` line の形式**:
   - 推奨: `# semantic-ci: <fix> fix required, <suggested> suggested, <info> info, <unresolved> unresolved`
   - 推奨: pass 時も `# semantic-ci: pass (N constraints satisfied)` を出す (CI ログが空にならない)
4. **SARIF results の order**:
   - 推奨: ConstraintResult の評価順 (CSCI-13 順) を維持。SARIF spec は順序不定だが
     determinism 確保のため固定。
5. **`.pre-commit-hooks.yaml` の `stages`**:
   - 推奨: `[pre-commit]` のみ。`commit-msg` / `pre-push` 等への展開は需要が出てから。
6. **CSCI-28 の PR split escalation**:
   - 推奨: 上記 §10 通り 1 PR 完結が default、SARIF が 300 行超えたら Codex が escalate して 2 分割を提案。

これら 6 件は **本 planning 文書の merge 時点で確定**。Codex が判断停止する事態を避ける。

## 13. 残課題 (Brief 4b 完了後)

- **Brief 4c (effects extractor `fqn` semantics 修正)** — Brief 4b と並列発行可、独立 PR
- **Brief 4d (`init` + spec authorship + soft/info constraint kind)** — Brief 4b/4c と並列発行可、独立 PR
- **Brief 5 planning** — Vibe Coding Adapter + Repair Compiler、Brief 4b/c/d 完了後に着手
- ~~**Brief 6 (TypeScript)** — Brief 5 と並列発行 (§22 設計通り)~~ → **凍結**(2026-05-06 Session 2 確定、`design.md §12 P3b` / `docs/brief_7_planning.md` 参照)。Brief 5 完了後の次は **Brief 7 (SSP v0.1)** の直列発行

## 14. Task Brief (CSCI-28、AGENTS.md format)

````markdown
# Task Brief: CSCI-28 - SARIF + GH Actions annotation + pre-commit manifest

## Phase
P1 (Brief 4b) — CI integration 出力の追加。`docs/brief_4b_planning.md` 参照。

## Goal
`semantic-ci` CLI に `--format sarif` と `--format gh-actions` を追加し、
`.pre-commit-hooks.yaml` manifest を repo 同梱して、3 つの CI integration 経路を
1 PR で完結させる。既存 `--format json` / `--format human` の挙動は変更しない。

## Acceptance Criteria
- [ ] `--format sarif` が `compare` / `check` / `pre-commit` で動作し、SARIF 2.1.0
      準拠の JSON を出力する (planning §4 schema を満たす)
- [ ] `--format gh-actions` が `compare` / `check` / `pre-commit` で動作し、
      `::error` / `::warning` / `::notice` を stdout に出力する (planning §5 spec)
- [ ] `observe` / `compile` で `--format sarif` または `--format gh-actions` を渡すと
      exit 2
- [ ] `--format gh-actions --output <file>` は exit 2 (file 出力は意味なし)
- [ ] `--format sarif --output <file>` は file に SARIF JSON を書く
- [ ] `.pre-commit-hooks.yaml` が repo root に存在し、planning §6.1 の形式に一致
- [ ] PYTHONHASHSEED 異値で SARIF / gh-actions 出力 byte-identical
      (既存 determinism test pattern を踏襲)
- [ ] `docs/cli_usage.md` に `--format sarif` / `--format gh-actions` の節追加
- [ ] `docs/json_schema.md` に「SARIF / gh-actions は別 envelope」 の 1 段落追記
- [ ] verdict envelope JSON schema は v2 のまま据え置き
- [ ] 既存 CLI / extractor / evaluator の test は全て pass

## Scope
- IN:
  - `src/semantic_ci_code/cli/main.py` (`--format` choices 拡張、subcommand 別の許可制限)
  - `src/semantic_ci_code/cli/output_sarif.py` (新規、SARIF encoder)
  - `src/semantic_ci_code/cli/output_gh_actions.py` (新規、workflow command encoder)
  - `.pre-commit-hooks.yaml` (新規、repo root)
  - `tests/cli/test_output_sarif.py` (新規)
  - `tests/cli/test_output_gh_actions.py` (新規)
  - `tests/cli/test_pre_commit_manifest.py` (新規、static YAML 検証)
  - `docs/cli_usage.md` (節追加)
  - `docs/json_schema.md` (1 段落追記)
- OUT:
  - 既存 `--format json` / `--format human` の挙動
  - verdict envelope JSON schema (v2 のまま)
  - `src/semantic_ci_code/effects/` (Brief 4c の領域)
  - `src/semantic_ci_code/framework/` (target.yaml schema 変更なし)
  - 既存 5 subcommand の引数体系 (`--format` choices 拡張のみ)
  - GitHub Actions marketplace publication (別 brief)

## Allowed Dependencies
なし。新規 dependency 不要。

## Implementation Hints
- SARIF schema: https://docs.oasis-open.org/sarif/sarif/v2.1.0/cs01/sarif-v2.1.0-cs01.html
- GH workflow commands: https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions
- 既存 `--format json` の deterministic 挿入順 / indent=2 / LF 改行のパターンを踏襲
- ConstraintResult / RepairInstruction の existing serializer (CSCI-13/14) を再利用
- gh-actions の severity mapping: `instruction.category` (FIX_REQUIRED / SUGGESTED / INFO) が直接対応 (planning §5.2)
- SARIF `level` mapping: `status` + `category` の組合せ (planning §4.2)
- evidence に file:line を持つ制約のみ SARIF location を埋める、持たない制約は location 省略
- `runs[0].invocations[0].properties` に既存 `engine.extractor_pyver` / `engine.package_version` を転記
- gh-actions の escaping は GH Actions spec (planning §5.3) に従う
- pre-commit manifest は静的 YAML、test は YAML パース + 必須 key + 値の検証で OK

## Required Outputs
- Branch name: `codex/csci-28-sarif-gh-actions-precommit`
- PR title: `feat(cli): add SARIF + GH Actions annotation outputs and pre-commit hooks manifest`
- Expected files changed:
  - 新規: `src/semantic_ci_code/cli/output_sarif.py`, `src/semantic_ci_code/cli/output_gh_actions.py`, `.pre-commit-hooks.yaml`, `tests/cli/test_output_sarif.py`, `tests/cli/test_output_gh_actions.py`, `tests/cli/test_pre_commit_manifest.py`
  - 修正: `src/semantic_ci_code/cli/main.py`, `docs/cli_usage.md`, `docs/json_schema.md`
- Required tests (above acceptance criteria に対応):
  - SARIF JSON が planning §4 schema を満たす (top-level key、severity mapping、location 埋め込み)
  - gh-actions stdout が `::(error|warning|notice) [file=...,line=...]::msg` 形式
  - 決定論: PYTHONHASHSEED 異値で byte-identical
  - manifest が pre-commit framework に認識される (YAML パース + 必須 key)
  - 既存 tests pass

## Done When
- All acceptance criteria are checked
- `ruff check .` passes
- `pytest -q` passes
- PR body starts with a Completion Summary

## Escalation triggers
- SARIF 実装が 300 行超える見込み → CSCI-28a (SARIF only) と CSCI-28b (gh-actions + manifest) に 2 分割を提案、Codex が Completion Summary で報告
- planning §12 の Open Questions に未確定が見つかった → 実装停止、Claude に escalate
````

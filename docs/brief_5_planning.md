# Brief 5 Planning — Repair Compiler + Vibe Coding Adapters (P2.5 Entry)

> **Status: Brief 5 完走(2026-05-07)。** CSCI-31〜35 全 PR が merge され、`compile-repair` /
> `validate-plan` 2 subcommand + Claude Code / Cursor / Codex 3 adapter が release 可能
> 状態。`risk_summary` 4 要素(`would_violate` / `forbidden_zones` /
> `required_additions` / `template_implications`)が deterministic に計算され、Adapter
> Protocol は明示引数経由(CSCI-35 で ContextVar 案を撤回し `risk_summary` を
> `render_pre_gen` の named arg に追加)で risk_summary を受ける。Brief 5 完了に伴い
> semantic-ci は「PR review tool」から「**AI 生成ループの一部として動作する gate +
> feedback layer**」に昇格。Brief 7(SSP v0.1)と CSCI-35b sweep brief が次の発行候補。
> 本文書は Brief 7 / 関連 brief 起草時の参照として保存する。
>
> Brief 1〜4d で確立した P1 MVP(`semantic-ci` CLI 5 subcommand + SARIF/GH Actions/
> pre-commit manifest + effects fqn schema 適合 + `init` + authorship + soft/info
> severity)の上に、**Repair SVP を generator-specific prompt/instruction に変換する
> 層**(`design.md §9.3 / §21.4`)と **vibe coding ツール統合 adapter 群**
> (`design.md §21.3`)を追加した **P2.5 entry** brief。

## 位置付け

`docs/code_semantic_ci_design.md §25` の Brief 5 行(PR #36 redistribution で確定)。
元 §25 計画では Brief 7 に置かれていた Vibe Coding Adapter / Repair Compiler を、
§21.1 で **P5 → P2.5 に前倒し** + redistribution で **Brief 5 に集約**。`init` /
authorship / severity routing は Brief 4d に分離済みで、本 brief は **Repair Compiler
core + adapter 群 + pre-generation validation 専用 entry point** の 3 軸に絞る。

## 1. 救済される未解決項目

| 出典 | 項目 | 本 brief での扱い |
|---|---|---|
| Brief 3 残課題 #4 | Repair Compiler(§9.3, §21.4)— Repair SVP → generator-specific prompt | **CSCI-31**(core)で解消 |
| `design.md §21.3` adapter list | Claude Code / Cursor / Codex adapter | **CSCI-32〜34** で解消 |
| `docs/pre_generation_validation_case.md` 残された問い #4 | `semantic-ci validate-plan` 専用エントリポイント | **CSCI-35** で解消 |
| `design.md §21.5` IDE / pre-commit integration | pre-commit hook 統合(軽量モード)/ LSP server 化 | **本 brief では pre-commit 連携の最小実装まで**(LSP は Brief 8+ deferred — Brief 7 は SSP v0.1 で予約済み、`design.md §25` 参照) |

## 2. Goals

1. **Repair Compiler core**: `RepairPlan`(CSCI-14)と `TargetSVP`(CSCI-12)を入力に、
   adapter プラガブル経路で外部 generator 向け prompt/instruction を render する layer
2. **Adapter Protocol** 抽象化: 1 つの interface(`render_repair` / `render_pre_gen`)で
   複数 generator に対応、新規 adapter の追加コストを最小化
3. **3 つの reference adapter** 実装: Claude Code / Cursor / Codex
4. **`semantic-ci validate-plan` 新規 subcommand**: target.yaml + baseline state から
   pre-generation guidance を render(adapter 選択可能)
5. **`semantic-ci compile-repair` 新規 subcommand**: 既存 verdict 出力の `repair_plan`
   を adapter 経由で render
6. **決定論性の維持**: 同 input → 同 output(既存 §14.2 / determinism test pattern を adapter にも拡張)

## 3. Non-goals (本 brief 範囲外)

- **v0 / Lovable / Bolt adapter** — §21.3 に「後続」 と明記、HTTP integration 形式は別 brief
- **LSP server 化**(§21.5) — IDE 内 real-time gate、Brief 8+ deferred(Brief 7 は SSP v0.1 で予約)
- **AI tool auto-detection**(§17.4) — `generation_metadata` field は Brief 4d で受け付け済み
  だが、自動検出ロジックは別 brief
- **Repair の自動適用**(generator 呼び出し) — Repair Compiler は **prompt/instruction を
  emit するのみ**。実際の patch 適用は外部 generator(Codex / Claude Code)の責務
  (§9.2 維持)
- **TypeScript extractor** — ~~Brief 6 範囲(P2.5 並列発行、§22)~~ Brief 6 は **凍結**(2026-05-06 Session 2 確定、`design.md §12 P3b` / `docs/brief_7_planning.md` 参照)。P3 以降に再評価
- **新たな constraint kind / operator** — Brief 4d で `severity: hard/soft/info` の routing
  は完成、本 brief で追加 constraint type は不要
- **`reduce` / `defer` / `lock` operator の完全実装** — §12 P2 予定、本 brief は
  既存 `RepairPlan` 出力 shape に依存して render するのみ
- **Hash trail per-extractor version** — §10 / Brief 3 #9 残部、§12 P2 細目に明記済み

## 4. アーキテクチャ全体像

```
┌────────────────────────────────────────────────────────┐
│  既存 P1 pipeline                                       │
│  Target SVP → Compiler → Evaluator → RepairPlan        │
│  (CSCI-12)    (CSCI-13)   (CSCI-14)                    │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  Brief 5 で追加: Repair Compiler                        │
│                                                         │
│  RepairPlan ──┐                                        │
│               ├──▶ RepairCompiler ──▶ Adapter ──▶ str  │
│  TargetSVP ──┘                                         │
│  (+ CodeState)                                         │
│                                                         │
│  Adapter:                                              │
│   ├─ ClaudeCodeAdapter   (markdown, instruction files) │
│   ├─ CursorAdapter       (.mdc rule files)             │
│   └─ CodexAdapter        (text prompt)                 │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  CLI integration                                        │
│   semantic-ci validate-plan   --adapter <name>         │
│   semantic-ci compile-repair  --adapter <name>         │
└────────────────────────────────────────────────────────┘
```

### 4.1 責務分離

| layer | 責務 | 触らない | surface (§23.3) |
|---|---|---|---|
| Engine(P1) | verdict 決定、RepairPlan 生成 | adapter / format | Validator |
| Repair Compiler core | RepairPlan + TargetSVP の正規化、adapter dispatch | engine 判定 / adapter 内部 / declared intent の意味論 | Advisor |
| Adapter | generator-specific format への **render**(translate ではない) | engine 判定 / 別 adapter / declared intent の意味論変更 | Advisor |
| CLI(本 brief で拡張) | subcommand 引数 → core dispatch → output | engine 判定 / adapter 内部 | Validator + Advisor |

#### 4.1.1 Adapter invariant: render-not-translate (§23.3 適用)

Adapter の出力は `RepairPlan` / `TargetSVP` の **文字列形式の翻訳**であり、 **意味論の再解釈ではない**。 declared intent の (severity / kind / target / operator / expected) は逐語で render 出力に出現すること。 これは `§23.3` の「engine は intent の真意を問わない」 を adapter 層に展開したもので、 adapter が「これは guidance なので柔軟に対処せよ」 と LLM に伝えると effective severity が adapter 側で勝手に下がり、 verdict と adapter 出力が乖離する。

各 adapter test には以下の assertion を含める:

- 入力 constraint の `severity` 値が rendered string に逐語で出現する
- 入力 constraint の `target` (例: `api_surface_public`) が rendered string に逐語で出現する
- 同 input に対して同 output (既存 §14.2 determinism test pattern を踏襲)

determinism test だけでは「rendered 文言が intent を歪めていないか」 は捕捉できないため、 上記 2 つの「逐語出現」 assertion を独立に置く。

## 5. Repair Compiler core 設計

### 5.1 入力 / 出力 contract

```python
@dataclass(frozen=True)
class CompiledRepair:
    """Adapter-rendered repair guidance, ready for hand-off to a generator."""
    adapter_name: str           # "claude-code" / "cursor" / "codex"
    output_format: str          # "markdown" / "mdc" / "text"
    rendered: str               # 最終 string(file 出力 or stdout に流す)
    metadata: dict              # adapter 共通 metadata(planning §5.3)


@dataclass(frozen=True)
class CompiledPreGen:
    """Adapter-rendered pre-generation guidance."""
    adapter_name: str
    output_format: str
    rendered: str
    metadata: dict
    risk_summary: dict          # baseline 比較で見つかった risk(planning §7.3)
```

### 5.2 RepairCompiler API

```python
class RepairCompiler:
    def __init__(self, adapter: Adapter) -> None: ...

    def render_repair(
        self,
        plan: RepairPlan,                  # CSCI-14 既存型
        target: TargetSVP | None = None,   # 元 intent を adapter 表示に転記する用
    ) -> CompiledRepair: ...

    def render_pre_gen(
        self,
        target: TargetSVP,                 # CSCI-12 既存型
        baseline_state: CodeState,         # CSCI-10 既存型
    ) -> CompiledPreGen: ...
```

### 5.3 共通 metadata 構造

adapter 出力に必ず含める metadata:

```python
{
    "schema_version": "1",                 # CompiledRepair / CompiledPreGen 固有 schema
    "engine_package_version": "0.x.x",
    "adapter_name": "...",
    "adapter_version": "1",                 # adapter 固有 schema 版
    "intent": "<from TargetSVP>",
    "primary_kind": "feature|bugfix|refactor|test_update",
    "constraint_count": int,
    "render_timestamp": null,               # determinism のため null 固定
    "input_kind": "verdict_envelope" | "raw_repair_plan" | "target_svp",
                                            # compile-repair: "verdict_envelope" or "raw_repair_plan"
                                            # validate-plan : "target_svp" 固定
}
```

`render_timestamp` は **always null**(§14.2 determinism 維持)。
`input_kind` は §8.1 の auto-detect 結果を hint として転記。

### 5.4 Adapter Protocol 抽象

```python
class Adapter(Protocol):
    name: str                               # registry key("claude-code" 等)
    output_format: str                      # "markdown" / "mdc" / "text"
    schema_version: str                     # adapter 固有 schema 版

    def render_repair(self, plan: RepairPlan, target: TargetSVP | None) -> str: ...
    def render_pre_gen(self, target: TargetSVP, baseline_state: CodeState) -> str: ...
```

registry: `_ADAPTERS: dict[str, Adapter]` を `repair_compiler/__init__.py` に置き、
新規 adapter は `_ADAPTERS["my-adapter"] = MyAdapter()` で 1 行追加。

## 6. Adapter 個別設計

### 6.1 Claude Code adapter(`claude-code`)

**output_format**: `markdown`(`.md` ファイル想定、stdout でも可)

**用途**: `CLAUDE.md` snippet 生成 / Task Brief 生成 / instruction file 連携

**スタイル**: imperative、構造化 markdown、`#` heading + bullet list ベース

**render_repair example**:
```markdown
# Repair Instructions

**Intent**: <intent string>
**Verdict**: repair (fix_required: 0, suggested: 2, info: 0)

## To Address (Suggested)
1. **R_COMPLEXITY_BUDGET** — `complexity_budget` exceeds tolerance
   - Constraint: `template:feature:complexity_budget`
   - Observed: 12, Expected: ≤ 5
   - Hint: extract helper from `src/api/users.py:fetch_user_profile`

2. **R_NO_NEW_EFFECTS** — Unannounced effect introduced
   - Constraint: `template:feature:no_new_effects`
   - Observed: `requests.get` in `src/api/users.fetch_user_profile`
   - Hint: declare in `target.yaml` constraints or remove
```

**render_pre_gen example**:
```markdown
# Plan Validation — Pre-Generation Guidance

**Intent**: <intent string>
**Primary kind**: feature

## Required by intent
- Add public function `fetch_user_profile` to `src.api.users`
- Add at least 1 test case under `tests/test_users.py`

## Forbidden in this scope
- Modify or remove existing public API in `src.api.users.*`
- Add new I/O effects outside declared constraints

## Risk areas detected from baseline
- `src.models.user` is currently public; refactoring may break callers
- Existing complexity baseline: 8 (target tolerance: ≤ 5)
```

### 6.2 Cursor adapter(`cursor`)

**output_format**: `mdc`(`.cursor/rules/*.mdc` 想定)

**用途**: Cursor IDE の rule file として配置、prompt 自動注入

**スタイル**: frontmatter(YAML)+ rule body markdown

**render_repair example**:
```mdc
---
description: Semantic CI repair guidance for current change
globs:
  - "src/**/*.py"
  - "tests/**/*.py"
alwaysApply: false
---

# Semantic CI Repair Guidance

When editing files in this PR, observe the following constraints:

## Fix Required
(none)

## Suggested
- Reduce cyclomatic complexity in `src/api/users.fetch_user_profile` to ≤ 5
- Remove or declare `requests.get` effect in user constraints

## Forbidden
- Removing public API symbols from `src.api.users.*`
- Modifying type signatures of existing public functions
```

**render_pre_gen example**: 同 frontmatter + rule body 形式、`alwaysApply: true` で
intent scope 全体に適用。

### 6.3 Codex adapter(`codex`)

**output_format**: `text`(plain text、structured sections、stdout 直流し想定)

**用途**: OpenAI Codex CLI / API への prompt 直接転記

**スタイル**: section labels(`[INTENT]`, `[CONSTRAINTS]`, `[FORBIDDEN]`, `[HINTS]`)で
明示構造化、indent + ASCII のみ

**render_repair example**:
```text
[INTENT]
Add fetch_user_profile to src.api.users.

[CURRENT VERDICT]
repair (fix_required: 0, suggested: 2, info: 0)

[FIX REQUIRED]
(none)

[SUGGESTED]
- R_COMPLEXITY_BUDGET: cyclomatic of src.api.users.fetch_user_profile is 12, expected ≤ 5
- R_NO_NEW_EFFECTS: requests.get used but not declared; either declare or remove

[HINTS]
- Extract helper from fetch_user_profile to reduce branching
- If requests.get is intentional, add to target.yaml constraints
```

### 6.4 共通設計判断

| 項目 | 全 adapter 共通 |
|---|---|
| 改行 | LF 固定 |
| 文字 encoding | UTF-8、ASCII safe(determinism + CI log で破綻しない) |
| 順序 | RepairPlan の category 順(FIX_REQUIRED → SUGGESTED → INFO → UNRESOLVED)、各 category 内は constraint 評価順(CSCI-13 確立) |
| 空 section | `(none)` テキスト固定で出す(category 不在を明示) |
| timestamp / commit hash | **含めない**(determinism 維持、§14.2) |
| color / ANSI | 全 adapter で off |

## 7. `semantic-ci validate-plan` subcommand

### 7.1 目的

「コードを書く前」に `target.yaml` を engine に通し、baseline state と比較して risk 領域を
adapter 経由で render する。`docs/pre_generation_validation_case.md` で実証された engine
の §23.1 入力 contract(state 出自不問)を、専用 entry point として提供する。

### 7.2 引数

```text
semantic-ci validate-plan
    --target <yaml>                          # 必須
    [--baseline-rev <ref>]                   # default: origin/main → main → master
    [--baseline-dir <dir>]                   # baseline-rev の代替(任意 directory)
    [--package-root <dir>]
    --adapter {claude-code,cursor,codex}     # 必須(default なし、明示要求)
    [--output <file>]
    [--format json]                          # 任意、JSON envelope 出力(下記 §8)
    [--no-fetch] [--allow-dirty]
```

### 7.3 risk_summary 計算

baseline state を起点に target.yaml を **virtual candidate** として engine に通し、以下を計算:

- `would_violate`: virtual candidate が state-as-baseline と比較して違反する constraint
  (= intent が現状から達成困難な要素)
- `forbidden_zones`: target が `lock` / `equals_baseline` 系で守る範囲(adapter は
  forbidden として明示)
- `required_additions`: target が `includes_any` / `includes_all` で要求する要素
- `template_implications`: `primary_kind` から自動展開された template 制約

これら 4 つを `CompiledPreGen.risk_summary` dict に格納、adapter は section に展開して
render。

## 8. CLI surface 変更 summary

| 変更 | 内容 |
|---|---|
| **新規 subcommand**: `validate-plan` | target.yaml + baseline → adapter rendered output |
| **新規 subcommand**: `compile-repair` | 既存 RepairPlan → adapter rendered output(input は JSON file or stdin) |
| `--format` 値域 | 既存 `{json,human,sarif,gh-actions}` に追加なし(adapter は専用 subcommand) |
| 既存 5 subcommand | 引数体系・挙動変更なし |
| `--output` flag | `validate-plan` / `compile-repair` で同一仕様(file or stdout) |

### 8.1 `compile-repair` 詳細

```text
semantic-ci compile-repair
    [--input <plan.json>]                    # default: stdin
    --adapter {claude-code,cursor,codex}     # 必須
    [--output <file>]
    [--format json]                          # 任意、JSON envelope
```

`--input` は **2 種類の input shape を auto-detect** で受け付ける:

1. **verdict envelope**(`semantic-ci check / compare / pre-commit --format json` の出力、
   `repair_plan` を **nested field** として持つ、`docs/json_schema.md` Verdict Envelope 仕様)
   → top-level の `subcommand` field 存在 + `repair_plan` field 存在で envelope と判定し、
   `repair_plan` を抽出して core に渡す
2. **raw RepairPlan JSON**(CSCI-14 `RepairPlan.model_dump()` 等を直接 dump したもの)
   → top-level に `instructions` 等の RepairPlan 専用 key を持ち、`subcommand` を持たない

これにより `semantic-ci check --format json | semantic-ci compile-repair --adapter
claude-code` の pipe 接続が、**user 側で field 抽出する必要なく**動作する(既存 CLI の
主用途を尊重)。同時に raw `RepairPlan` JSON を直接持つ test fixture / 外部生成物にも
対応する。

不正な shape(どちらにも該当しない)は **exit 2** + 人間可読エラー(`unrecognized
input: expected verdict envelope (with subcommand + repair_plan) or raw RepairPlan
(with instructions)` 相当)。

`compile-repair` は **input 種別を `metadata.input_kind` field に転記**(値は
`"verdict_envelope"` or `"raw_repair_plan"`)。下流が input 経路を区別したいときの
hint。`metadata` schema は planning §5.3 を拡張。

## 9. JSON schema 影響

### 9.1 新 envelope: validate-plan

```jsonc
{
  "schema_version": "1",
  "subcommand": "validate-plan",
  "intent": "...",
  "primary_kind": "feature",
  "adapter_name": "claude-code",
  "rendered": "<string>",                    // adapter 出力
  "risk_summary": {                          // planning §7.3
    "would_violate": [...],
    "forbidden_zones": [...],
    "required_additions": [...],
    "template_implications": [...]
  },
  "engine": {
    "extractor_pyver": "3.11",
    "package_version": "0.x.x"
  }
}
```

### 9.2 新 envelope: compile-repair

```jsonc
{
  "schema_version": "1",
  "subcommand": "compile-repair",
  "adapter_name": "claude-code",
  "rendered": "<string>",
  "metadata": { ... },                       // planning §5.3
  "engine": {
    "extractor_pyver": "3.11",
    "package_version": "0.x.x"
  }
}
```

### 9.3 既存 envelope への影響

- verdict envelope(`compare`/`check`/`pre-commit`)— **影響なし**
- compile envelope(`compile`)— **影響なし**

## 10. CSCI 分割案(5 PR — 全 merged)

| CSCI | スコープ | 状態 |
|---|---|---|
| **CSCI-31** | Repair Compiler core + Adapter Protocol + registry + 1 reference adapter(Claude Code) | ✅ merged (PR #52) |
| **CSCI-32** | Cursor adapter | ✅ merged (PR #53) |
| **CSCI-33** | Codex adapter | ✅ merged (PR #54) |
| **CSCI-34** | `compile-repair` subcommand + JSON envelope + pipe 連携 | ✅ merged (PR #55) |
| **CSCI-35** | `validate-plan` subcommand + risk_summary 計算 + 全 adapter で pre_gen render | ✅ merged (PR #56) |

合計 ~1,700 LoC、tests 込み(2026-05-07 merge 完了時点で 793 passed)。Brief 3(CSCI-10〜14)/ Brief 4(CSCI-15〜19)と同規模。

CSCI-32 / 33 は CSCI-31 完了後に **並列発行可**。CSCI-34 / 35 は 3 adapter 揃った後。

## 11. Allowed dependencies

**なし**。Repair Compiler core も全 adapter も標準 stdlib + 既存 pydantic / pyyaml で
実装可。

`.mdc` フォーマット(Cursor)は frontmatter + markdown body の単純構造、stdlib `yaml` で
frontmatter dump、本文は string concat で OK。

## 12. Open Questions / decisions before implementation

1. **subcommand 名**:
   - `compile-repair` vs `repair-compile` vs `compile --target=repair`(format flag 拡張)
   - 推奨: **`compile-repair`**(動詞-名詞、既存 `compile` と区別、format flag に詰めない)
2. **validate-plan の adapter default**:
   - default を `claude-code` にする vs 必須(default なし)
   - 推奨: **必須(default なし)**。明示的に選ばせる(誤設定で別 generator 用 prompt が出る事故を防ぐ)
3. **validate-plan の baseline 取得方法**:
   - git ref のみ vs `--baseline-dir <dir>` も許す
   - 推奨: **両対応**(`compare` と同じ pattern、何もコミットしていない repo でも使える)
4. **CompiledRepair / CompiledPreGen の schema_version 扱い**:
   - 1 から開始、独立に bump、verdict envelope と非同期
   - 推奨: **独立 schema_version**(`docs/json_schema.md` Compatibility Policy に節追加)
5. **Adapter Protocol を `Protocol` typing で書くか ABC で書くか**:
   - 推奨: **`Protocol`**(structural typing、registry pattern と相性が良い、既存 Pydantic 模型と直交)
6. **Cursor adapter の `globs` 値**:
   - 推奨: target.yaml の `change.scope.files` がある場合はそれを転記、ない場合は
     `["**/*.py"]`(P1 Python only 前提)
7. **Codex adapter の structured sections 名**:
   - `[INTENT]` / `[CONSTRAINTS]` / `[FORBIDDEN]` / `[HINTS]` 等の section 名は固定
   - 推奨: 固定(generator 側 prompt template が前提にできる)
8. **`render_pre_gen` で baseline が取れない場合**:
   - 例: 新規 repo / git 未初期化
   - 推奨: empty CodeState を baseline として渡し、risk_summary は `forbidden_zones` 空 +
     `required_additions` のみ render
9. **adapter 出力に CI status 情報を含めるか**:
   - 例: 「current verdict: repair」 を Claude Code adapter に出すか
   - 推奨: **含める**(generator が次のサイクルで状況を理解するため)。Cursor / Codex も同様
10. **CSCI 分割の妥当性**:
    - 5 PR vs 4 PR(CSCI-32 + 33 を 1 PR に集約)
    - 推奨: **5 PR**(adapter ごとに分ける方が review が小さくなる、Cursor / Codex は
      並列発行可)
11. **`--format json` で rendered string をそのまま JSON 内に乗せるか base64 化するか**:
    - 推奨: **そのまま乗せる**(JSON string escape で十分、可読性優先)
12. **既存 `RepairPlan` の serialization shape を変更するか**:
    - 推奨: **変更しない**(CSCI-14 で確立済み、Repair Compiler は既存 shape を読むだけ)
13. **adapter 出力の改行末尾**:
    - 推奨: **`rendered.endswith("\n")` を保証**(CI log / file output で trailing newline が
      自然に入る)
14. **AI 生成 spec の検出(§17.4)を validate-plan で render するか**:
    - target.yaml の `authorship.generation_metadata` を adapter 出力に転記するか
    - 推奨: **転記する**(Brief 4d で field は受け付け済み、adapter で activate)。検出
      ロジック自体は別 brief

これら 14 件は **本 planning 文書 merge 時点で確定**。Codex が判断停止する事態を避ける。

## 13. Test 計画

### 13.1 Repair Compiler core(CSCI-31)
- Mock adapter(`name="mock"`, render_repair / render_pre_gen が固定 string を返す)で
  `RepairCompiler` の dispatch を確認
- Adapter Protocol の structural typing を Pydantic 模型と直交に保つ
- registry が adapter 重複登録時に raise
- determinism: 同 RepairPlan + 同 adapter で byte-identical output(PYTHONHASHSEED 異値テスト)

### 13.2 Adapter individual(CSCI-31 / 32 / 33)
- 各 adapter で fixture(repair / fail / pass + INFO / SUGGESTED / FIX_REQUIRED)を render
- 出力 string を golden file と比較(planning §6.1 / 6.2 / 6.3 の example が baseline)
- 空 section の `(none)` 表記
- determinism: PYTHONHASHSEED 異値で byte-identical

### 13.3 `compile-repair` subcommand(CSCI-34)
- stdin input + adapter 指定 → rendered output
- file input(`--input plan.json`)
- `--output` で file 書き出し
- `--format json` で JSON envelope に rendered + metadata
- **input shape auto-detect**(planning §8.1):
  - **verdict envelope input**(`{subcommand: "check", verdict: ..., repair_plan: {...}, ...}`)で `metadata.input_kind == "verdict_envelope"`、`repair_plan` を抽出して render
  - **raw RepairPlan input**(`{instructions: [...], ...}`)で `metadata.input_kind == "raw_repair_plan"`、そのまま render
  - **同 RepairPlan を verdict envelope で包んだ場合と raw で渡した場合で、`rendered` が byte-identical**(extraction の正確性)
  - **不正 shape**(`subcommand` も `instructions` も持たない)で exit 2 + 人間可読エラー
- pipe 連携: `semantic-ci check --format json | semantic-ci compile-repair --adapter claude-code` が **user 側 jq 等の field 抽出なしで** pass through(verdict envelope auto-detect 経路の end-to-end test)

### 13.4 `validate-plan` subcommand(CSCI-35)
- target.yaml + baseline-rev で render(全 adapter)
- target.yaml + baseline-dir(git なし)で render
- risk_summary の 4 component が独立に埋まる test
- adapter 必須(指定なしで exit 2)
- determinism: 同 target + 同 baseline + 同 adapter で byte-identical

### 13.5 既存 test 影響
- 既存 5 subcommand / verdict envelope / SARIF / gh-actions の test は全 pass
- `RepairPlan` の serialization shape は不変(既存 CSCI-14 test 維持)

## 14. 残課題 (Brief 5 完了後)

> **Status (2026-05-07 Session 4 / 5 時点)**: CSCI-35b sweep の 4 候補のうち 2 件は
> 単発 PR で先行解消済み(PR #58 / #59)。残 2 件は次の sweep brief で同梱予定。
> 全体の最新 tracking は `CLAUDE.md` 次の発行順序 §A を参照。

- **CSCI-35b sweep brief**(残 2 件まで縮小): Brief 5 review で deferred とした技術的負債をまとめて 1 PR で消化:
  - ~~`would_violate` の delta-kind constraint 盲点を `docs/cli_usage.md` に明記~~ → **既明記済**(`docs/cli_usage.md:348-353` で self-comparison 下では delta-kind が `would_violate` に上がらない旨を文書化済、Session 4 で確認、撤回)
  - `compute_risk_summary` の `target_svp_to_yaml → compile_target_svp` round-trip にコメント追加(将来 `compile_target_svp` に `TargetSVP` 直接受付 overload を入れる前提)— **未着手**
  - ~~`_resolve_package_root` に `Path.is_relative_to(root.resolve())` で symlink escape 防御深度を追加~~ → **完了**(PR #59、CSCI-35b sweep #3、`check.py` / `pre_commit.py` の `_resolve_package_root` を `validate_plan` 既存パターンに対称化)
  - Claude Code adapter の `Forbidden Zones` / `Required Additions` を JSON dict dump から markdown human-friendly 表現にするか検討(adapter ごと専用 formatter)— **未着手**
- ~~**Brief 6** TypeScript extractor — Brief 5 と並列発行可、§22 設計通り~~ → **凍結**(2026-05-06 Session 2 確定、`design.md §12 P3b` / `docs/brief_7_planning.md` 参照)。P3 以降に再評価。Brief 5 完了後の次は **Brief 7 (SSP v0.1)** 直列発行
- **v0 / Lovable / Bolt adapter**(§21.3「後続」)— HTTP integration 形式、別 brief
- **LSP server 化**(§21.5)— IDE 内 real-time gate、Brief 8+ deferred(Brief 7 は SSP v0.1 で予約、`design.md §25` 参照)
- **AI tool auto-detection**(§17.4)— `generation_metadata` 自動推定ロジック、別 brief
- **P2 Brief 化時の細目**: Lock violation 即 fail / per-extractor timeout /
  per-extractor version hash trail(`design.md §12 P2` に明記済み、Brief 5 完了後に着手)
- **D1〜D5 dogfood-driven 課題群**(2026-05-07 Session 4 / 5 由来): `target.yaml` authoring guide 新設(D1/D3/D4)、extractor exclude 機構(D2)、set operator partial-match semantics(D5 = FINDING-1、未解決)— 詳細と現行 routing は `CLAUDE.md` 次の発行順序 §A'/§D/§F、`docs/dogfooding_TC10_report.md` 参照

## 15. 次のアクション(完了履歴)

1. ✅ 本 planning 文書を `docs/brief_5_planning.md` として merge(PR #44)
2. ✅ §12 Open Questions 14 件を planning merge 時点で確定
3. ✅ CSCI-31〜35 を順次 Task Brief 化 → 全 merge(2026-05-07 完走)
4. ✅ CSCI-35b sweep #3(symlink escape 防御)を PR #59 で先行解消
5. **次**: §14 の **CSCI-35b sweep brief 残 2 件**(round-trip コメント + Claude Code adapter human-friendly レンダリング)を発行 → その後 **Brief 7 (SSP v0.1)** entry

---

**この planning 文書は Brief 5 完走(2026-05-07、CSCI-31〜35 全 merge)で役割を終えた。Brief 7 起草時の参照として保存。**

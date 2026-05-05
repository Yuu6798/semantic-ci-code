# Brief 4c Planning — Effect Extractor `fqn` Semantics Fix

> Brief 4 (CSCI-15〜19) で確立した CLI 5 subcommand と Brief 4b (CSCI-28) で完成させた
> CI integration 経路の上で、effect extractor の出力が設計 §3.1 schema に適合するよう
> 修正する **P1 内 hot-fix(優先)**。Brief 4b と並列発行可、本体規模は 1 ファイル
> 修正 + テスト migration で半日〜1 日。

## 位置付け

`docs/code_semantic_ci_design.md §25` の Brief 4c 行として確定済み(PR #36 redistribution
で Brief 5 から分離)。`.claude/memory/2026-05-05.md` Session 2 で発見した effects slice
gap の 2 系統(extractor の `fqn` semantics + effect_db の Level 2/3 拡張)のうち、
**前者(設計射程内の単純な意味修正)を P1 内で完結させる**。

後者(effect_db の Level 2/3 拡張、`Path.write_text` 等 method call 解決)は §12 P2
予定どおり据え置き、本 brief では触らない。

## 1. 救済される未解決項目

| 出典 | 項目 | 本 brief での扱い |
|---|---|---|
| `.claude/memory/2026-05-05.md` Session 2 | extractor の `fqn` が callee 指向(`print`)で、設計 §3.1 schema が要求する enclosing function 指向(`audit.audit_state`)になっていない | **CSCI-29** で `_extract_call_effects` を NodeVisitor 化、enclosing function を `fqn` に格納 |
| `design.md §25` Brief 4c 行 | effect extractor `fqn` semantics 修正(callee → enclosing function、§3.1 schema 適合) | 同上 |
| 副次効果 | `template:feature:no_new_effects` の per-fqn 比較が機能し始める。`refactor:effects_unchanged` の精度向上 | 自動的に解消(extractor 出力構造が下流要求と整合) |

## 2. Goals

1. **`_extract_call_effects` を AST `NodeVisitor` 化** し、`EffectEntry.fqn` を call の
   **enclosing function/method** の qualified name にする。
2. **`evidence` に呼び先(callee)を保持** する形で旧情報を失わない(`evidence.resolved_call`
   は既存、新たに `evidence.enclosing_function_fqn` は不要 — `fqn` 自身が enclosing function)。
3. **CodeState cache の `CACHE_FORMAT_VERSION` を bump**(Brief 4b で導入された cache が
   旧 fqn semantics で書かれた payload を読み込まないように)。
4. **既存テスト 31 個の `entry.fqn` assertion を新 semantics に migration**。
5. **新規テスト**で per-fqn 集約が正しく機能することを確認(同 enclosing function 内の
   複数 call が同 fqn になり、別 function は別 fqn になる)。

## 3. Non-goals (本 brief 範囲外)

- **`_extract_global_mutations` の修正** — 既存の `module:` / `global:` / `nonlocal:`
  prefix は mutation の subject(何が変わるか)を表しており、本 brief の agent(誰が
  effect を持つか)修正とは別軸。下流評価は effect_class の値で区別できるので、call と
  mutation の fqn 規約が別でも実害はない。**P2 で `lock` operator 完全実装と一緒に再検討**。
- **effect_db の Level 2 / 3 拡張**(`Path.write_text` 等 method call 解決)— §12 P2
  予定どおり据え置き。
- **`template:feature:no_new_effects` constraint logic 自体の変更** — extractor 出力が
  per-fqn になれば既存 constraint logic が機能する想定。動かない場合は別 brief に escalate。
- **`docs/json_schema.md` の verdict envelope schema bump** — extractor 出力構造の修正は
  内部的、JSON envelope の field shape は変わらない(`code_state.effects[].fqn` の値が
  変わるだけで、key 構造は同じ)。
- **新たな evidence field 追加** — 既存 `resolved_call` で callee を保持できるので追加不要。

## 4. 設計: enclosing function tracking

### 4.1 NodeVisitor の構造

```python
class _CallEffectVisitor(ast.NodeVisitor):
    def __init__(
        self,
        index: dict[str, EffectSignature],
        alias_map: dict[str, str],
        filename: str,
    ) -> None:
        self.index = index
        self.alias_map = alias_map
        self.filename = filename
        self.entries: list[EffectEntry] = []
        self._scope_stack: list[str] = []  # ["ClassName", "method_name", ...]

    def _enclosing_fqn(self) -> str:
        return ".".join(self._scope_stack) if self._scope_stack else "<module>"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # lambdas: synthetic name, kept for visibility
        self._scope_stack.append("<lambda>")
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        raw = _resolve_dotted_name(node.func)
        if raw is not None:
            resolved, level = _resolve_call(raw, self.alias_map)
            signature = self.index.get(resolved)
            if signature is not None:
                self.entries.append(
                    EffectEntry(
                        fqn=self._enclosing_fqn(),
                        effect_class=signature.effect_class,
                        confidence=1.0,
                        evidence={
                            "raw_call": raw,
                            "resolved_call": resolved,
                            "file": self.filename,
                            "line": node.lineno,
                            "resolution_level": level.value,
                        },
                    )
                )
        self.generic_visit(node)
```

### 4.2 fqn 命名規則

| context | 例 source | fqn |
|---|---|---|
| 関数内 call | `def foo(): print()` | `foo` |
| ネスト関数内 call | `def outer(): def inner(): print()` | `outer.inner` |
| メソッド内 call | `class Foo: def bar(self): print()` | `Foo.bar` |
| ネストクラス・メソッド | `class A: class B: def m(self): print()` | `A.B.m` |
| async 関数内 call | `async def afoo(): await x()` | `afoo` |
| lambda 内 call | `lambda: print()` | `<lambda>` (lambda 内 call は実用上稀、可視性のため記録) |
| module-level call | `print()` (top-level) | `<module>` |
| comprehension 内 call | `[print(x) for x in y]` (関数内) | enclosing function fqn を継承 (comprehension は scope を切らない扱い) |
| comprehension 内 call (module-level) | `[print(x) for x in y]` (top-level) | `<module>` |
| decorator 引数の call | `@app.route('/')` (関数定義の外側) | enclosing function があればその fqn、なければ `<module>` |

`<module>` / `<lambda>` は **山括弧で識別子と区別**(Python 自体の慣習: `frame.f_code.co_name`
が同様の表記を使う)。

### 4.3 evidence は既存形を維持

`evidence` dict は既存 4 key (`raw_call`, `resolved_call`, `file`, `line`,
`resolution_level`) のまま。callee 名は `resolved_call` に既に保持されているので、
情報損失なし。

下流(constraint evaluator / repair emitter)が `entry.fqn` で集約しつつ、
`evidence.resolved_call` で「具体的に何を呼んだか」 を表示できる。

## 5. CodeState Cache 影響

### 5.1 互換性破壊

CSCI-26 (PR #37) で導入された CodeState cache は、計算済み CodeState を tree id で
keyed して `~/.cache/semantic-ci/codestate/` に保存する。Brief 4c で extractor の出力
shape が変わる(`fqn` の値が変わる)ため、**旧 cache を読み込むと不正な CodeState を
返す**。

### 5.2 対処: `CACHE_FORMAT_VERSION` を bump

`src/semantic_ci_code/cli/code_state_cache.py` の `CACHE_FORMAT_VERSION` を **1 → 2** に
bump。既存 `_load_cache_payload` で version mismatch 時に miss 扱いするロジック(line 190
付近)が動き、旧 cache は自動的に再計算される。

### 5.3 cache key への影響なし

cache key core は `(commit_sha, package_root, package_version, cache_format_version)`。
`package_version` は package の SemVer、`cache_format_version` は内部スキーマ版。本 brief
では `cache_format_version` のみ bump、SemVer は releaser の判断で別途。

## 6. Test migration 戦略

### 6.1 既存 test の影響範囲

`tests/test_python_effect_extractor.py`(1132 行、31 fqn assertion)が直接影響。
影響パターンは 3 種:

| パターン | 旧 assertion | 新 assertion |
|---|---|---|
| 関数内 call の fqn | `assert entry.fqn == "os.remove"` | `assert entry.fqn == "<module>"` and `assert entry.evidence["resolved_call"] == "os.remove"` |
| 集合チェック | `fqns == {"os.remove", "subprocess.run"}` | `resolved_calls == {"os.remove", "subprocess.run"}` (集合は `evidence.resolved_call` から) |
| 関数内 vs module-level の区別 | テストが関数 wrap していない場合は module-level なので fqn=`<module>` | 関数 wrap して `assert entry.fqn == "test_func"` の形に書き直し |

### 6.2 移行方針

- 既存 test source の `def test_*` 内に直接 effect call が書かれている場合: 多くは
  module-level の文字列 source として渡されており、test 内の `def test_*` は extractor
  に渡されていない(extractor が見るのは test fixture 内の source 文字列)。
- fixture source が module-level 文字列なら fqn = `<module>`、function-wrap した
  fixture は fqn = `<wrap_function_name>`。
- 31 assertion を 1 つずつ new semantics に書き換え、必要なら fixture source を function
  wrap する形に修正。
- 副次的に、**「同 enclosing function 内に 2 call → 同 fqn の 2 entry が出る」 を確認する
  新規 test** を追加(per-fqn 集約の前提)。

### 6.3 新規テスト

最低 4 件:

1. **module-level call**: `print()` (top-level) → `entry.fqn == "<module>"`
2. **関数内 call**: `def foo(): print()` → `entry.fqn == "foo"`
3. **メソッド内 call**: `class A:\n    def m(self): print()` → `entry.fqn == "A.m"`
4. **ネスト関数内 call**: `def outer():\n    def inner(): print()` → `entry.fqn == "outer.inner"`
5. **per-fqn 集約**: 同 fqn 内 2 call で entries が 2 件、両方 fqn 一致
6. **lambda**: `lambda: print()` (top-level) → `entry.fqn == "<lambda>"`

## 7. CLI 表示・SARIF / GH Actions annotation への影響

Brief 4b で導入した SARIF と GH Actions annotation は `runs[0].results[].locations[]` に
file:line を出力する設計(planning §4.4)。これらは `evidence.file` / `evidence.line` を
参照しており、`fqn` の値変更には影響されない。

human format(`docs/cli_usage.md`)は constraint id ベースで表示しており、`fqn` を直接
表示していないので影響なし。

## 8. PR split

**1 PR (CSCI-29) で完結**。

- 対象ファイル数 3:
  - `src/semantic_ci_code/effects/python_effect_extractor.py` (主修正)
  - `src/semantic_ci_code/cli/code_state_cache.py` (`CACHE_FORMAT_VERSION` bump)
  - `tests/test_python_effect_extractor.py` (31 assertion migration + 新規 6 件)
- 規模: 主修正 ~80 行 + cache version 1 行 + test 修正 ~150 行 ≈ 230 行
- 半日〜1 日規模、AGENTS.md target 0.5-2 日に収まる

split escalation trigger:
- test migration 中に extractor の `_extract_global_mutations` の挙動も併せて修正したく
  なった場合 → CSCI-29a (call effects only) と CSCI-29b (mutation fqn 統一) に 2 分割を
  提案、Codex が Completion Summary で escalate

## 9. Allowed dependencies

**なし**。stdlib `ast` のみで実装可。

## 10. Open Questions / decisions before implementation

1. **`<module>` vs module name**:
   - 推奨: `<module>` (山括弧、Python 慣習に整合)
   - 理由: extractor が「どのモジュールか」 という情報を持っていない(filename はあるが
     module path への mapping は CSCI-7 module_graph の責務)。`<module>` で「ファイル
     スコープ全体」 を表す方が責務分離としても綺麗
2. **lambda のスコープ表記**:
   - 推奨: `<lambda>`(山括弧)
   - 理由: lambda は無名、`<module>` と同様の synthetic 名で識別。実用上 lambda 内で
     side effect を持つ call は稀
3. **comprehension をスコープとして切るか**:
   - 推奨: **切らない**(enclosing function を継承)
   - 理由: Python 3 の comprehension は確かに新スコープを作るが、effect tracking の観点
     では「外側の関数の責務」 として捉える方が直感的(comprehension 内の `print` は
     外側関数の effect)。ast walk 的にも単純
4. **decorator 引数の call の扱い**:
   - 推奨: enclosing function があればその fqn、なければ `<module>`
   - 理由: decorator 引数は通常 module-level で評価されるため `<module>` が自然
5. **CodeState cache の bump 方針**:
   - 推奨: `CACHE_FORMAT_VERSION: 1 → 2` に bump
   - 理由: 旧 fqn semantics の cached payload を読むと不正な CodeState を返すため、
     強制的に invalidate
6. **既存 `_extract_global_mutations` の `module:` / `global:` / `nonlocal:` prefix**:
   - 推奨: **本 brief では触らない**(scope guard)
   - 理由: mutation は subject(何が変わるか)を表しており、call の agent(誰が呼ぶか)
     とは概念が異なる。一緒に修正すると 1 PR 規模が膨らむ
7. **既存 test の集合 assertion (`fqns == {...}`) の扱い**:
   - 推奨: assertion を `resolved_calls = {e.evidence["resolved_call"] for e in entries}`
     に書き換え
   - 理由: 集合チェックの意図は「どの API が呼ばれたか」 で、これは callee 情報なので
     `resolved_call` に対応

これら 7 件は **本 planning 文書 merge 時点で確定**。Codex が判断停止する事態を避ける。

## 11. 残課題 (Brief 4c 完了後)

- **Brief 4d** (`semantic-ci init` + spec authorship anchoring + soft/info constraint kind)
  — 本 brief と並列発行可、独立 PR
- **Brief 5 planning** — Vibe Coding Adapter + Repair Compiler、Brief 4b/c/d 完了後に着手
- **Brief 6 (TypeScript)** — Brief 5 と並列発行 (§22 設計通り)
- **P2 で `_extract_global_mutations` の fqn 統一を再検討**(本 brief で意図的に scope 外)

## 12. Task Brief (CSCI-29、AGENTS.md format)

````markdown
# Task Brief: CSCI-29 - Effect extractor fqn semantics fix (callee → enclosing function)

## Phase
P1 hot-fix (Brief 4c) — effect extractor の `fqn` 出力を設計 §3.1 schema に
適合させる。`docs/brief_4c_planning.md` 参照。

## Goal
`_extract_call_effects` を AST `NodeVisitor` 化して `EffectEntry.fqn` を
**call の enclosing function/method の qualified name** にする。callee 名は
`evidence.resolved_call` に既存どおり保持。CodeState cache を invalidate
するため `CACHE_FORMAT_VERSION` を bump。`_extract_global_mutations` は
本 brief では触らない。

## Acceptance Criteria
- [ ] `_extract_call_effects` が AST `NodeVisitor` ベースで、FunctionDef /
      AsyncFunctionDef / ClassDef / Lambda の scope stack を追跡する
- [ ] `EffectEntry.fqn` が enclosing function / method の qualified name を持つ
      (`docs/brief_4c_planning.md §4.2` の命名規則どおり)
- [ ] module-level call の fqn は `<module>`
- [ ] lambda 内 call の fqn は `<lambda>` (lambda は scope として切る)
- [ ] comprehension は scope として切らず、enclosing function を継承する
- [ ] `evidence.resolved_call` に callee 名が保持され、既存集合 assertion を
      これで書き換えられる
- [ ] `src/semantic_ci_code/cli/code_state_cache.py` の `CACHE_FORMAT_VERSION`
      を 1 から 2 に bump し、旧 cache を miss 扱いさせる
- [ ] `tests/test_python_effect_extractor.py` の既存 31 fqn assertion を
      新 semantics に migration、planning §6.2 方針に従う
- [ ] 新規 test 6 件追加 (planning §6.3): module-level / 関数内 / メソッド内 /
      ネスト関数 / per-fqn 集約 / lambda
- [ ] `_extract_global_mutations` 関連テストは無修正で pass (scope guard)
- [ ] `ruff check .` / `pytest -q` 全 pass
- [ ] verdict envelope JSON schema は v3 のまま据え置き(`code_state.effects[].fqn`
      の値変更のみ、key 構造は同じ)

## Scope
- IN:
  - `src/semantic_ci_code/effects/python_effect_extractor.py` (`_extract_call_effects` を NodeVisitor 化)
  - `src/semantic_ci_code/cli/code_state_cache.py` (`CACHE_FORMAT_VERSION` を 1→2 に bump)
  - `tests/test_python_effect_extractor.py` (31 既存 assertion + 新規 6 件)
- OUT:
  - `_extract_global_mutations` の修正 (本 brief 範囲外、planning §3 / §10 Q6)
  - effect_db の Level 2 / 3 拡張 (`Path.write_text` 等、§12 P2 予定)
  - constraint evaluator / repair emitter の変更 (extractor 出力修正で自動的に動く想定)
  - JSON envelope schema の bump (`fqn` の値変更のみ、shape は不変)
  - SARIF / GH Actions annotation の output モジュール (Brief 4b で完成済み、`evidence.file`/`line` 参照のため影響なし)

## Allowed Dependencies
なし。stdlib `ast` のみで実装可。

## Implementation Hints
- planning §4.1 の `_CallEffectVisitor` skeleton を参考に実装
- `visit_FunctionDef` / `visit_AsyncFunctionDef` / `visit_ClassDef` / `visit_Lambda` で
  `self._scope_stack.append(node.name)` / `pop()` を行う
- `visit_Call` 内で `_resolve_dotted_name` → `_resolve_call` → `index.get` → entry 追加
  (既存 `_extract_call_effects` のロジックを流用)
- comprehension は `visit_ListComp` 等を override せず default visit に任せる
  (scope を切らない方針、planning §10 Q3)
- `_enclosing_fqn` は `".".join(self._scope_stack) if self._scope_stack else "<module>"`
- 既存 `_extract_global_mutations` には触らない (scope guard)
- cache version bump は `CACHE_FORMAT_VERSION = 2` の 1 行変更
- test migration: planning §6.2 の 3 パターンを 1 つずつ書き換え、`fqns == {...}` は
  `{e.evidence["resolved_call"] for e in entries} == {...}` に
- 新規 test は既存 test と同じ fixture pattern (source 文字列 → `extract_python_effects`)

## Required Outputs
- Branch name: `codex/csci-29-effect-extractor-fqn-fix`
- PR title: `fix(effects): set EffectEntry.fqn to enclosing function (callee → enclosing function)`
- Expected files changed:
  - 修正: `src/semantic_ci_code/effects/python_effect_extractor.py`
  - 修正: `src/semantic_ci_code/cli/code_state_cache.py`
  - 修正: `tests/test_python_effect_extractor.py`
- Required tests:
  - 既存 31 fqn assertion が新 semantics で pass
  - 新規 6 件 (planning §6.3) で per-fqn 集約 / scope handling を検証
  - `pytest -q` で全 test pass
  - `_extract_global_mutations` 系の既存テストが無修正で pass

## Done When
- All acceptance criteria are checked
- `ruff check .` passes
- `pytest -q` passes
- PR body starts with a Completion Summary

## Escalation triggers
- test migration 中に `_extract_global_mutations` の fqn 規約も統一したくなった場合 →
  CSCI-29a (call effects only) と CSCI-29b (mutation fqn) に 2 分割を提案、
  Codex が Completion Summary で escalate
- planning §10 の Open Questions に未確定が見つかった → 実装停止、Claude に escalate
- per-fqn 集約の test が pass しない (extractor 出力構造が下流要求と整合しない) →
  constraint evaluator 側の修正が必要な可能性、Claude に escalate
- effect 抽出パターンに想定外の AST node (e.g., walrus operator inside comprehension の
  enclosing scope 解釈) が発生 → planning §4.2 の命名規則に従って判断、迷ったら escalate
````

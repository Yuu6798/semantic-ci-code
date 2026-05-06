# Brief 7 Planning — Semantic Security Protocol (SSP) v0.1

> Brief 5(Vibe Coding Adapter + Repair Compiler、P2.5 entry)に続く Brief。
> Issue #48(Semgrep を semantic-ci core に深く統合する提案)の audit と
> 設計議論を経て、**core を汚さずに security sensor を束ねる別 protocol** として
> SSP(Semantic Security Protocol)を新設する brief。Brief 6(TypeScript
> extractor)は本 brief 議論の中で **凍結**(P3 以降に再検討)が確定したため、
> 順序は **Brief 5 → Brief 7** となる。

## 位置付け

`docs/code_semantic_ci_design.md §25` の Brief 表で Brief 6 を凍結、Brief 7 を
SSP v0.1 に再定義。SSP は §20.1 layered distribution の 4 層目として
`semantic-ci-suite` と並列に配置(core / suite / SSP / action の 4 層)。
Brief 5 が「PR review tool → AI 生成ループの gate + feedback layer」への
昇格だったのに対し、Brief 7 は「semantic-ci core の adherence-not-correctness
判定の隣で、security sensor の delta を束ねる独立 protocol」を確立する位置付け。

## 1. 救済される未解決項目

| 出典 | 項目 | 本 brief での扱い |
|---|---|---|
| Issue #48 | Semgrep を CodeState に組み込む提案 | **reject**(深い統合はしない)、SSP として core 外で扱う |
| Issue #48 audit(セッション 2026-05-06) | OSS fingerprint 不在 / line-based fp 不安定 / paths.scanned 突合 / SIGTERM 経路 | SSP §3 / §4 に invariant として明示 |
| `CLAUDE.md` Scope guard | 「not a linter / not a SAST gateway」を維持 | core に SAST sensor を入れない、SSP 経由で扱う |
| `design.md §23.3` Adherence-not-Correctness | 「正しさ」判定を core に持ち込まない | SSP は finding 検出を sensor に委譲、delta のみ計算 |
| `design.md §20.1` layered distribution | ~~core / suite / action の 3 層~~ → 本 PR で **4 層に更新済み**(`semantic-ci-ssp` を `semantic-ci-suite` と並列追加) | SSP を 4 層目として追加(suite と並列) |
| `pre_generation_validation_case.md` §23.1 invariant | engine は state の出自を問わない | SSP も Sensor Provenance Invariant として鏡像化 |

## 2. Goals

1. **SSP の protocol 仕様を確立**: `docs/ssp_protocol.md` v0.1 を新設、Q1-Q6 の
   設計判断(本 doc §3)を spec として固定
2. **Sensor Provenance Invariant**: `SensorOutput` の出自(real / staged /
   virtual / contract-test)を engine が問わない invariant を §23.1 と並列で確立
3. **Reference adapter 2 つ**: Python 限定の SemgrepAdapter(SAST)と pip-audit
   Adapter(SCA)を実装、SSP-compliant fingerprint と delta 計算を実証
4. **SSP envelope の独立 JSON schema 化**: SARIF とは並列、`ssp-to-sarif` 一方向
   変換を提供(GH Code Scanning へ流す経路)
5. **CLI surface**: `semantic-ci ssp scan` 系 subcommand 群を core CLI 配下に
   追加、ただし core engine からは独立(suite layer 扱い)
6. **決定論性の維持**: 既存 §14.2 / determinism test pattern を SSP envelope に
   拡張、audit で発見した 5 つの落とし穴を回帰テスト化

## 3. Non-goals(本 brief 範囲外)

- **TypeScript / 多言語対応** — Brief 6 凍結により Python 限定、TS は P3 以降
- **Secrets scanning / IaC scanning** — 範囲を SAST + SCA に限定(Q1 の決定)
- **CodeQL / Bandit adapter** — reference adapter は Semgrep + pip-audit のみ、
  追加 adapter は Brief 7 完了後の別 brief(Brief 8+ deferred 候補)
- **auto-template 化(段階 C)** — `target.yaml` の宣言なしで SSP delta が verdict に
  影響する経路は当面入れない、運用データを集めてから別 brief で判断
- **core への深い統合** — Issue #48 で reject、SSP envelope と core verdict
  envelope は独立(将来 Suite 層で aggregate するかは別議論)
- **Pro / 商用 ruleset 依存** — OSS Semgrep の範囲で動かす、`fingerprint` は自前
  5 要素 fp(本 doc §4.3、`rule_id × module_path × qualified_name ×
  normalized_text × ordinal`)で算出
- **GitHub Marketplace publication** — SSP は当面 `pip install` + workflow run の
  運用、Action 化は P3a に集約(§12)

## 4. SSP 設計の確定事項(議論セッション 2026-05-06 Session 2 由来)

論点 6 つを順に詰めて確定。詳細議論は session memory 参照。

### 4.1 範囲(Q1)

**SAST + SCA**。Secrets / IaC は将来別 protocol として扱う。

- SAST: ソースコード上のパターンマッチ系 finding(Semgrep / Bandit / CodeQL 系)
- SCA: 依存ライブラリの既知 CVE(pip-audit / OSV)
- 両者で finding の identity が異なる(SAST は AST node、SCA は package@version)が、
  共通 `SensorOutput` 抽象で吸収

### 4.2 言語・エコシステム(Q2)

**Python only**。`pip` ecosystem(`requirements.txt` / `poetry.lock` /
`uv.lock`)+ Python source。Brief 6 凍結に伴い TypeScript / npm は P3 以降。

### 4.3 Fingerprint 計算規則(Q3)

**算法骨格を SSP 仕様で固定、言語プロファイルは別添**。

エンコードは **canonical JSON 配列**(`json.dumps(..., ensure_ascii=False,
sort_keys=False, separators=(",", ":"))`)を使い、 **要素間 delimiter `:` 連結
は禁止**(injective でないため衝突源)。

```python
import hashlib, json

def sast_fp(rule_id: str, module_path: str, qualified_name: str,
            normalized_text: str, ordinal: int) -> str:
    payload = json.dumps(
        [rule_id, module_path, qualified_name, normalized_text, ordinal],
        ensure_ascii=False,
        sort_keys=False,            # 配列は順序保存
        separators=(",", ":"),      # 余白なしの canonical 形
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

JSON 配列を使う理由(injective + cross-language portable):

- `normalized_text` には Python 文字列リテラル(`"key: value"` 等)経由で `:`
  が混入し得る。POSIX path / rule_id にも `:` は legal。delimiter 連結は
  `("a:b", "c")` と `("a", "b:c")` を区別できず衝突源になる
- JSON は文字列内の特殊文字を `\"` / `\\` / `\u####` で escape するため、
  array で並べた時点で各要素は再構成可能(injective)
- `separators=(",", ":")` で空白なしの canonical 形に固定、`ensure_ascii=False`
  で非 ASCII 文字(コメント / docstring 由来)の表現が確定的
- 将来 TypeScript profile を起こす際、`JSON.stringify(arr)` で同じ payload を
  再現できる(言語間 fp 互換)

`module_path` は **repo-relative POSIX path**(`os.sep` を `/` に正規化、`.py`
拡張子保持)。audit 不変条件 F-3(path repo-relative normalization)と
連動し、virtual mode (CodeState 直接入力)では sensor provenance 内の
`source_id` に対応する文字列を使う。Python module dotted path
(`pkg.foo`)ではなく path を採るのは、`__init__.py` / `tests/conftest.py`
などパッケージ外ファイルでも一意性が確保されるため。

`qualified_name` は最寄りの `FunctionDef` / `AsyncFunctionDef` / `ClassDef` を
walk up、`<module>.<class>...<func>` 形式。module-level は `<module>` のみ
(同 path 内では module-level は 1 つのスコープなので衝突しない、別 path 間の
衝突は `module_path` 成分が解消する)。

`normalized_text` の正規化規則は **Python profile §X.1**(別添)で規定:
- `ast.unparse()` 経由で AST → text
- 前後 whitespace strip、内部 whitespace 連続 → 単一 space
- comment は `ast.unparse()` 出力に含まれないが、念のため strip

`ordinal_index_within_scope` の割り当て規則(SSP 仕様で固定):

1. すべての raw findings を集めた後、 4-tuple
   `(rule_id, module_path, qualified_name, normalized_text)` で **group**
2. 各 group 内の finding を **source span tuple** `(start_line, start_col,
   end_line, end_col)` で **昇順 sort**(整数比較、tie-break は
   左から右へ)。Semgrep の `start.line` / `start.col` / `end.line` /
   `end.col` field をそのまま使う(1-indexed のままで OK、相対順序のみ意味を持つ)
3. sort 済みリストの **0-indexed 位置**を ordinal とする
4. 完全に同一の source span を持つ重複 finding は **重複排除を ordinal 割当て前に
   実施**(adapter 実装の責務、`ssp_protocol.md §X.2` で reference 実装を提示)
5. virtual mode(CodeState 直接入力)で source span が無い場合は、 sensor
   provenance 内の **stable iteration order** を使い、その順序を CodeState
   schema で要求(§4.4 envelope の `findings_order_invariant` field 参照)

この規則の含意:
- **既知の trade-off**: 同 group 内に新規 finding が挿入されると、後続の ordinal
  が +1 ずれて該当 fp が変わる。これは ordinal の本質的制約であり、 SSP は
  group 衝突 (同 rule × 同 file × 同 function × 同 normalized_text) は
  実用上稀という前提で受け入れる。代替案 (ordinal を完全に削除する設計) は
  別の衝突源を生むため採らない
- **adapter 実装互換性**: Semgrep adapter / pip-audit adapter / 将来の
  TypeScript profile が **同じ raw findings 集合**を受けたら **同じ ordinal**
  を割当てる。adapter ごとの内部 iteration order に依存しない

**SCA は別 fingerprint**(SCA は path / コード内文字列に依らないが、 SAST と同じ
encode 規則(canonical JSON)を採用して仕様を統一する):

```python
def sca_fp(package_name: str, installed_version: str, advisory_id: str) -> str:
    payload = json.dumps(
        [package_name, installed_version, advisory_id],
        ensure_ascii=False, sort_keys=False, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

> **設計改訂履歴**:
> - PR #50 review #1(2026-05-06、Codex P2 指摘)で 4 要素 → 5 要素に拡張。
>   理由: 同 rule_id + 同 normalized_text のマッチが別ファイルで衝突する
>   問題(同名関数 / module-level マッチが特に危険)。`module_path` を 2 番目に
>   挿入することで rule × file × function × text × ordinal の 5 軸で衝突回避
> - PR #50 review #2(2026-05-06、Codex P2 指摘)で `:` delimiter 連結 →
>   canonical JSON 配列に変更。理由: `normalized_text` 内に legal な `:` が
>   混入し得るため delimiter 連結は injective でなく、別 finding が同 fp に衝突する
>   可能性があった。SCA 側も同じ encode 規則に統一
> - PR #50 review #3(2026-05-06、Codex P2 指摘)で `ordinal_index_within_scope`
>   の割り当て規則を pin 固定。理由: 同 4-tuple group 内で複数 findings がある
>   場合、 adapter / Semgrep バージョン差で ordinal が変動すれば fp も変動し、
>   §4.3 が決定的であるべき算法骨格を spec が保証できなくなる。group → source
>   span 昇順 sort → 0-indexed 位置で確定

### 4.4 Envelope 設計 + Sensor Provenance Invariant(Q4)

**B(独立 JSON schema)+ 仮想コード 4 mode 対応**。

```json
{
  "schema_version": "ssp-1",
  "engine": {
    "ssp_version": "0.1",
    "scan_mode": "real|staged|virtual|hybrid",
    "baseline": {"kind": "git-rev|virtual|prebuilt", "ref": "..."},
    "candidate": {"kind": "git-rev|git-tree|virtual|prebuilt", "ref": "..."},
    "sensors": [
      {"id": "semgrep", "version": "1.161.0", "ruleset_hash": "..."},
      {"id": "pip-audit", "version": "2.7.0", "advisory_db_hash": "..."}
    ]
  },
  "deltas_by_sensor": {
    "semgrep": {"added": [...], "removed": [...], "unchanged": [...]},
    "pip-audit": {"added": [...], "removed": [...], "unchanged": [...]}
  },
  "aggregate_verdict": "pass|fail|unknown"
}
```

**Sensor Provenance Invariant**(§23.1 鏡像):

> SSP delta engine は `SensorOutput` を消費する。`SensorOutput` の出自(real
> scan / staged content / virtual fixture / hand-built)を engine は問わない。

これにより 4 mode を 1 仕様で扱える:

| mode | baseline | candidate | 用途 |
|---|---|---|---|
| post-commit CI | main HEAD | PR head | 標準 |
| pre-commit | HEAD | staged content (`git write-tree`) | ローカル gate |
| pre-generation | 現行コード | 予測 / 仮想コード | 生成前検証(Brief 5 連携) |
| contract test | hand-built | hand-built | unit test |

### 4.5 Issue 処理(Q5)

**現状(PR #50 review 後、 2026-05-06)**: Issue #48 は **クローズ済み**
(state_reason=`completed`、 SSP 文脈移動 redirect コメント付き)。 audit
comment は #48 に保存。 SSP v0.1 の tracking は **本 PR (#50) と
`docs/brief_7_planning.md` 自体**で扱い、 専用の SSP v0.1 tracking issue は
**Brief 5 完了直前 / Brief 7 (CSCI-36) 着手時に意図的に起こす**(早期に
立てると stale 化する懸念のため遅延、 §11 着手 checklist 参照)。

> **Brief 7 owner への注記**: 既に open な SSP tracking issue は **存在しない**。
> 検索しても見つからない場合 duplicate を起こさず、 §11 checklist の手順に
> 従って tracking issue を起こすこと。 Q5 当初の決定 (#48 close + 新規
> tracking issue) は維持されているが、 新 issue の作成タイミングは
> 「Brief 7 着手時」 に pin 済み。

### 4.6 命名(Q6)

**SSP(Semantic Security Protocol)を採用**。

- 初出は必ず full name「Semantic Security Protocol (SSP)」
- 以降は SSP
- CLI subcommand は `semantic-ci ssp <subcmd>`
- NIST System Security Plan との衝突は許容、初出 full name で防御

## 5. 2026-05-06 Determinism Audit 結果(SSP 設計の根拠)

Issue #48 audit で確定した事実を Brief 7 内で**回帰テスト化必須**:

| ID | 結果 | SSP への含意 |
|---|---|---|
| A1 同一入力 byte-identity (N=20) | PASS | extractor pipeline で同 input → 同 output 期待値テスト追加 |
| A2 jobs invariance | PASS | Semgrep adapter で `--jobs` 固定不要(audit で確認済み) |
| A3 path / rule_id 正規化 | CONDITIONAL PASS | adapter で **`--no-rewrite-rule-ids` hard-code + path repo-relative 正規化**必須 |
| B1/B2 airgap + telemetry zero | PASS | adapter で `--metrics=off --disable-version-check` hard-code |
| C1 line-based fp 不安定 | **FAIL** | 自前 5 要素 fp 必須(§4.3、`rule_id × module_path × qualified_name × normalized_text × ordinal`)、Semgrep `extra.fingerprint` は OSS で `"requires login"` 返却 |
| E1 paths.scanned 突合 | NOTE | adapter で **expected file list ↔ scanned 突合、欠損 → unknown 扱い** |
| E1 SIGTERM / JSON parse 失敗 | NOTE | adapter で exit code != {0,1} → unknown 経路必須 |
| E2 wall-time variance | PASS(8%) | per-extractor timeout は §18 P2 で別途、SSP 側は **timeout → unknown** |

audit 詳細: Issue #48 コメント。fixtures は `/tmp/sci_audit/`(セッション専用、本
brief 着手時に `experiments/ssp_audit/` 等に永続化検討)。

## 6. CSCI 候補分割(暫定)

実装側 brief を発行する際の参考。詳細は brief 発行時に決定。

| CSCI | スコープ | 想定規模 |
|---|---|---|
| **CSCI-36** | `docs/ssp_protocol.md` v0.1 spec(§1-§5 of spec)+ Python profile §X | docs only、500-700 行 |
| **CSCI-37** | SSP envelope schema(JSON Schema)+ Pydantic models + delta engine core | 600-800 行 + tests |
| **CSCI-38** | SemgrepAdapter(SAST)+ AST-aware fp 実装 + audit 5 落とし穴の回帰テスト | 500-700 行 + tests |
| **CSCI-39** | pip-audit Adapter(SCA)+ lockfile parser + advisory db hash | 400-500 行 + tests |
| **CSCI-40** | `semantic-ci ssp` subcommand 群 + ssp-to-sarif 変換 + e2e fixtures | 400-500 行 + tests |

依存関係: 36 → 37 → (38 ∥ 39) → 40。36 が spec 確定、それ以降は実装。

## 7. Brief 5 → Brief 7 順序の明確化

| 順 | Brief | 内容 | 着手条件 |
|---|---|---|---|
| 1 | **Brief 5**(進行中) | Vibe Coding Adapter + Repair Compiler(P2.5 entry) | CSCI-31 〜 35 を順次発行、planning は PR #44 で merged 済み |
| 2 | **Brief 6** | TypeScript extractor | **凍結**(P3 以降、費用対効果見直し後に再検討) |
| 3 | **Brief 7** | SSP v0.1 | Brief 5 完了後、本 doc を入力に CSCI-36 から発行 |

Brief 5 が 5 PR、Brief 7 が 5 CSCI 想定で並列発行は不可(直列)。Brief 5 中に
Brief 7 spec 議論を進めることは可能(本 planning doc が既にその出発点)。

## 8. Brief 5 中に Brief 7 を阻害しないこと

Brief 5 が以下のいずれかに踏み込んだ場合、Brief 7 で再設計が必要になる:

- ❌ Repair Compiler が Semgrep finding を `RepairPlan` に直接埋め込む
- ❌ Adapter が `target.yaml` に `security_findings` 制約を新規追加する
- ❌ `validate-plan` / `compile-repair` の出力 envelope が SSP envelope と
  schema レベルで衝突する
- ✅ Repair Compiler が SSP envelope を **読み取り専用**で参照し、prompt context
  に注入するのは OK(Brief 5 終了後の小拡張で実現可能)

→ Brief 5 implementation で迷ったら、SSP 関連は **Brief 7 に持ち越す** が安全側。

## 9. SSP doc を書く時の reference 構造(spec doc 草案目次)

`docs/ssp_protocol.md` v0.1 を書く際の暫定見出し:

```
# Semantic Security Protocol (SSP) v0.1

§1. Scope and Non-goals
§2. Definitions (SensorOutput, Finding, SSPDelta, SSPVerdict)
§3. Sensor Contract
§4. Sensor Provenance Invariant   ← §23.1 の鏡像
§5. Fingerprint Specification
   §5.1 SAST fingerprint
   §5.2 SCA fingerprint
   §5.3 Python profile (AST normalization)
§6. Envelope Schema (independent JSON, schema_version "ssp-1")
§7. Aggregation and Verdict
§8. Reference Adapters
   §8.1 SemgrepAdapter
   §8.2 pip-audit Adapter
§9. Determinism Requirements (audit invariants)
§10. CLI Surface (semantic-ci ssp ...)
§11. Relationship to SARIF
§12. Compatibility and Versioning
```

`brief_4_planning.md` と異なり、本 doc は **planning** であって **spec** ではない。
spec 本体は Brief 7 着手時の最初の CSCI(CSCI-36)で `docs/ssp_protocol.md` として書く。

## 10. Risks / Open Questions

### R1. SSP と core の責任境界が将来曖昧化する

`§20.1` で SSP を suite と並列の 4 層目に置く設計だが、**実装上 `semantic-ci ssp`
subcommand を core CLI に同居させる**ため、ユーザから見ると一体化して見える。
core engine と SSP engine の **テスト / リリース / バージョニングを分けるか**は
Brief 7 中に判断必要。

### R2. ruleset 配布戦略未確定

Semgrep ruleset を repo に vendoring するか、Semgrep registry の `p/python` を
オンライン取得するかは Brief 7 着手時に決める。**vendoring 推奨**(audit B1/B2 で
airgap 完走確認済みの前提を活かす)。

### R3. SCA advisory database の更新頻度

pip-audit は OSV / PyPI advisory を fetch する。**baseline と candidate で同じ
db snapshot を使う**仕組みが必要(env var ピン or local cache)。これも Brief 7 着手時。

### R4. Suite 層との将来的な aggregate

`semantic-ci-suite` が将来 core verdict + SSP verdict を**同一 envelope で
集約**する案がある(§20.3 / §20.4)。Brief 7 では SSP envelope 単独で完結させ、
集約は別 brief(suite Brief)で扱う。

### R5. 命名衝突への runtime 対応

NIST System Security Plan との衝突は accept したが、READMEs / search engine 経由で
ユーザが混乱する可能性。SSP doc 冒頭に **Why this name?** セクション(NIST SSP との
区別)を 1 段落書くこと。

## 11. 次セッションでの着手 checklist

Brief 5 完了後、Brief 7 を始める際に:

- [ ] 本 planning doc を読み返す(Q1-Q6 の確定 + audit invariants)
- [ ] **SSP v0.1 tracking issue を新規起票**(現時点では存在しない、 Q5 §4.5
  参照)。 起票時のテンプレ:
  - title: `Brief 7: Semantic Security Protocol (SSP) v0.1 — implementation tracking`
  - body 冒頭で Issue #48(closed)と PR #50(merged 想定)を ref、
    `docs/brief_7_planning.md` を spec source として明示
  - CSCI-36〜40 を sub-task として列挙、 §6 の候補分割表を貼る
- [ ] CSCI-36 Task Brief を発行(`docs/ssp_protocol.md` v0.1 spec 起こし)、
  上記 tracking issue 番号を Task Brief 冒頭で ref
- [ ] 旧 audit fixtures(`/tmp/sci_audit/`)を `experiments/ssp_audit/` に永続化
  検討
- [ ] Issue #48 の audit comment を spec doc §9(Determinism Requirements)から
  ref で参照
- [x] §20.1 の layered distribution に SSP 行を追加 — **本 PR(#50) review で対応済み**
  (Codex P3 指摘、`semantic-ci-ssp` を `semantic-ci-suite` と並列の 4 層目として追加)
- [ ] Suite 層との関係(R4)について 1 段落 doc に書く

## 12. References

- Issue #48: 元提案(Semgrep を CodeState 組み込み)+ determinism audit コメント
- `.claude/memory/2026-05-06.md` Session 2: 本 planning の議論経緯
- `docs/code_semantic_ci_design.md` §20.1 layered distribution / §23.1
  engine state provenance / §23.3 adherence-not-correctness
- `docs/brief_5_planning.md`: 構造の参考(Brief 5 は Repair Compiler + Adapter、
  Brief 7 は SSP で対比的)
- `docs/pre_generation_validation_case.md`: §23.1 の実証、SSP の Sensor
  Provenance Invariant の前例

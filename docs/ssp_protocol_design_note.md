# Forward Design Note: Brief 7 / SSP v0.1 (CSCI-36 着手時必読)

Status: **DESIGN NOTE (Brief 7 implementer 用 一次資料)**。 2026-05-21
Session 2 末尾の Phase 4 (`docs/doc_refactor_planning.md`) で
`AGENTS.md` inline から分離して本 doc に移送。 AGENTS.md は本 doc への
pointer のみ残置。

以下は session 2026-05-07 で user から提供された Brief 7 (Semantic
Security Protocol v0.1) の設計申し送り。CSCI-36 Task Brief を起草・実装
する際に **逐語で参照すること**。 `docs/brief_7_planning.md` は planning
であり spec ではない(申し送り #1, #2 を参照)。本 doc は Claude × user の
合意により main 直 commit で永続化された一次資料 (通常の
`.claude/memory/` 例外運用と同等の扱い)。

## 現状認識

Brief 5 までで semantic-ci core / Repair Compiler / Adapter CLI は一通り
完走した。 semantic-ci は「意図 target.yaml と実コード delta の整合性を
見る core」と、「判定結果を AI 開発ツールに渡す adapter layer」まで到達
している。

Brief 7 はここからの **隣接 protocol 拡張**であり、 semantic-ci core に
SAST/SCA を混ぜる話ではない。 SSP は security sensor の finding delta を
扱う別 protocol として設計する。

## 最重要方針

SSP は semantic-ci core を太らせない。

```text
semantic-ci core  = intent / delta adherence
Repair Compiler   = AI 開発ツールへの guidance rendering
SSP               = security sensor delta protocol
suite/action      = core + SSP を束ねる運用層
```

core verdict envelope と SSP envelope は分離すること。 統合表示や総合
gate は suite/action layer の責務に送る。

## 未解決・注意点

### 1. docs/brief_7_planning.md の文字化け

ローカル表示で `docs/brief_7_planning.md` がかなり文字化けしている。
CSCI-36 ではまず、 人間がレビュー可能な UTF-8 の `docs/ssp_protocol.md`
として清書すること。 planning doc をそのまま spec として扱わない。

(注: 2026-05-07 verify では file content 自体は valid UTF-8。 表示破損は
local terminal / editor encoding 起因。 それでも spec / planning の分離
方針は採用する。)

### 2. CSCI-36 は docs/spec only 推奨

いきなり SemgrepAdapter / pip-audit 実装に入らない。 まず SSP v0.1 spec
を固定する。

CSCI-36 の主成果物:

- `docs/ssp_protocol.md`
- SSP scope / non-goals
- SensorOutput / Finding / SSPDelta / SSPVerdict 定義
- Sensor Provenance Invariant
- fingerprint spec
- envelope schema
- determinism requirements
- SARIF との関係
- versioning policy

### 3. Sensor Provenance Invariant を最優先で固定

SSP engine は `SensorOutput` の出自を問わない。

```text
real scan
staged content
virtual fixture
hand-built contract test
```

これらを同じ `SensorOutput` として扱うこと。 これは semantic-ci core の
「CodeState 出自不問」 と同じ思想。 ここを壊すと SSP がただの CLI wrapper
になる。

### 4. fingerprint 設計が最大リスク

Semgrep の line-based fingerprint や OSS `extra.fingerprint` に依存しない
こと。

SAST fingerprint は少なくとも以下を含める方針:

- `rule_id`
- `module_path`
- `qualified_name`
- `normalized_text`
- `ordinal_index_within_scope`

delimiter join ではなく canonical JSON array を SHA-256 する。 `:` join
は collision risk があるため避ける。

未解決:

- `ordinal_index_within_scope` の安定性
- `normalized_text` の AST unparse 方針
- module-level / lambda / nested function の qualified_name 規則
- finding が同一 normalized_text で複数出る場合の扱い

### 5. SSP scope は SAST + SCA に限定

Brief 7 v0.1 では以下に絞る。

```text
SAST: SemgrepAdapter
SCA: pip-audit Adapter
```

入れないもの:

- secrets scanning
- IaC scanning
- CodeQL
- Bandit
- GitHub Marketplace publication
- TypeScript / npm
- SARIF first の設計
- core CodeState への Semgrep finding 統合

scope creep を避けること。

### 6. SSP envelope は独立 schema

verdict envelope / compile envelope / validate-plan envelope とは別。
例:

```json
{
  "schema_version": "ssp-1",
  "engine": {
    "ssp_version": "0.1",
    "scan_mode": "real|staged|virtual|hybrid",
    "baseline": {},
    "candidate": {},
    "sensors": []
  },
  "deltas_by_sensor": {},
  "aggregate_verdict": "pass|fail|unknown"
}
```

`semantic-ci check` の JSON schema を bump して SSP を混ぜない。

### 7. SARIF は出力先であって内部形式ではない

SSP 内部形式を SARIF に寄せすぎない。 SARIF は GitHub Code Scanning /
external tooling 向けの変換先。 `ssp-to-sarif` は CSCI-40 以降でよい。

### 8. adapter 実装前に unknown/error semantics を決める

Semgrep / pip-audit 実行では失敗パターンが多い。

決めるべきこと:

- Semgrep exit code `0/1` は正常 scan
- JSON parse failure
- timeout
- SIGTERM
- ruleset unavailable
- scanned path mismatch
- advisory DB unavailable
- pip-audit network dependency

これらを engine error にするのか、 SSP `unknown` にするのかを spec で
固定すること。 semantic-ci 的には、 sensor failure は多くの場合 `unknown`
として envelope に出す方がよい。

### 9. deterministic audit を spec に入れる

少なくとも以下を回帰テスト化する設計にする。

- 同一 input で byte-identical
- `PYTHONHASHSEED` 差で byte-identical
- path separator 差の正規化
- Semgrep `--jobs` 差で同一
- ruleset id rewrite 無効化
- metrics / version check disabled
- line number 変動で fingerprint が過剰に揺れない
- sensor failure が deterministic に unknown へ落ちる

### 10. CLI surface は後段

`semantic-ci ssp ...` は CSCI-40 あたりでよい。 CSCI-36/37 では model /
spec / pure delta engine を先に作る。 CLI 先行にすると protocol が固まる
前に UX に引っ張られる。

推奨順:

```text
CSCI-36: docs/ssp_protocol.md v0.1
CSCI-37: Pydantic models + delta engine
CSCI-38: SemgrepAdapter
CSCI-39: pip-audit Adapter
CSCI-40: semantic-ci ssp CLI + SARIF bridge
```

## Brief 5 からの学びとして反映すべきこと

### target/scope 設計の教訓

semantic-ci core では `tests/cli` を package root にすると helper 移動が
API change になった。 SSP でも scan scope を曖昧にすると、 想定外の
finding delta が出る。 SSP spec でも scan root / include / exclude /
repo-relative path normalization を明確化すること。

### adapter layer の教訓

Repair Compiler で adapter ごとの表現差が semantic drift を露出した。
SSP でも JSON / SARIF / GH annotation / human output の間で意味がズレない
よう、 内部 envelope を先に固定すること。

### includes_any 問題の教訓

`includes_any` を required item として flatten すると、 AI が「全部必要」
と誤解した。 SSP でも「alternative」「required」「advisory」「unknown」
を混同しないこと。 security finding の severity / confidence /
reachability / fixability を単純 flatten しない。

## 設計AIへの推奨判断

Brief 7 は進めてよい。 ただし「semantic-ci にセキュリティ機能を足す」と
表現しない方がよい。

正しい framing:

```text
Semantic Security Protocol (SSP) is a sibling protocol for deterministic
security sensor deltas. It does not change semantic-ci core verdict semantics.
```

CSCI-36 は implementation ではなく spec 固定に徹すること。 ここで scope /
fingerprint / provenance / unknown semantics を固めるのが最重要。

## Cross-Reference

- `AGENTS.md` § Forward Design Note pointer — 本 doc への単一 entry point
- `docs/brief_7_planning.md` — planning doc (本 design note の前段、 spec
  ではない)
- `docs/code_semantic_ci_design.md` §20.1 — 4 層 layered distribution
  (semantic-ci core / Repair Compiler / SSP / suite/action) の architectural
  context
- `docs/code_semantic_ci_design.md` §23.1 — CodeState provenance neutrality
  (SSP の Sensor Provenance Invariant の鏡像となる core 側 invariant)
- `CLAUDE.md` § Required Reading Before Editing Tier C — 「`AGENTS.md`
  Forward Design Note (Brief 7 / SSP) only when touching Brief 7 work」
  の pointer は本 doc に redirect される (Phase 4 移送後)

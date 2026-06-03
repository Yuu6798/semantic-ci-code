# LLM Security Sensor Planning — Non-Deterministic Scout Layer (Phase H candidate)

> Phase G (SSP core integration, G-1〜G-4b merged / G-5 残) が用意した
> SensorState・canonical_id・suite evaluator・suppression の機構の上に、
> **非決定論センサー (LLM セキュリティオラクル)** を 1 種類の sensor adapter
> として接続する設計 planning。Codex Security を first concrete adapter に置き、
> 設計は特定ベンダーに依存しない LLM 一般のアダプタープロトコルとして起こす。
>
> **本 planning は Phase G-5 (CSCI-49) 完走を前提**とする (SensorState /
> SecurityDelta / suite evaluator / `security:` namespace / suppression を
> 全面再利用するため)。STATUS.md 次の発行順序への投入は Phase G 完走後に判断。

## 0. 経緯と問題認識

### 0.1 出発点 — Phase G の deterministic sensor は完成済

Phase G は semgrep (SAST) / pip-audit (SCA) という **決定論的センサー** を
core に縦接続した:

- `sensor/models.py`: SecurityFinding / SensorState / SensorProvenance /
  PerSensorDelta / SecurityDelta
- canonical_id = identity tuple の JSON array hash (injective encoding)
- suite evaluator で code_delta + security_delta → suite_verdict
  (`unknown > fail > repair > pass`)
- per-sensor provenance で drift 検出 (`provenance_changed → unknown`)
- `security:` namespace + suppression (期限・owner 必須)

semgrep / pip-audit は **(version, ruleset_hash) を固定すれば同一コードに
同一出力を返す** ため、Phase G の drift モデル (provenance 比較) で十分に
扱えている。

### 0.2 動機 — LLM セキュリティオラクルの射程

semgrep / pip-audit はパターンマッチと既知 CVE 照合が射程で、
**認可バイパス・ロジック脆弱性・複数ホップの taint・「不在」の脆弱性
(missing authz/validation)** を捉えられない (phase_g_planning §0.1 の限界 2 と
同根)。LLM セキュリティオラクル (Codex Security / Claude security review /
他モデル) は攻撃者視点でこれらを炙り出せる。これを Phase G の sensor 機構に
3 本目以降のセンサーとして接続したい。

### 0.3 中心的緊張 — 非決定論センサー × 決定論 gate

LLM は **入力固定でも出力が揺れる** (同一コード・同一モデル・同一プロンプトで
finding 集合が変わりうる) 点が、semgrep の version drift とは質的に異なる。
素朴に「baseline を LLM scan / candidate を LLM scan して差分」を取ると、
`delta = candidate − baseline` に **新規導入された脆弱性ではなく LLM の
recall ノイズ** が混入する。これは Phase G の自然キー集合演算が前提する
「センサーはコード状態の関数」という仮定を破る。

### 0.4 設計の核 (壁打ち蒸留)

本 planning は 2026-06-03 session の 5+ round 壁打ちで以下に収束した
(会話ログは session wrap-up 時に当日の `.claude/memory/` dated log へ
externalize される。本 planning 起草時点での一次記録は下表 + §1 各 D 本文で
あり、既存の `2026-06-03.md` は Phase G G-3〜G-4b の wrap-up のみで本議論は
未収録)。最重要の転換は **「LLM は judge では
なく scout」** — LLM はジャッジせず候補を炙り出すだけで、合否を出すのは
あくまで決定論的な宣言制約 (target.yaml) である。この framing が
core scope guard「not an LLM-as-judge service」との衝突を解消する。

| 論点 | 確定 | 由来 |
|---|---|---|
| LLM の位置付け | **scout (偵察)、not judge**。on-demand / optional / 非常駐 | D1 |
| 決定論 | LLM は core の外で実行、frozen SensorState を ingest (Phase G 再利用) | D2 |
| §23.1 | weaken しない (verdict は記録済み state から再現)。新 wrinkle は D4 で吸収 | D3 |
| 非決定論ノイズ | one-run + 決定論的 re-projection を **LLM sensor では必須**化 | D4 |
| 一般化 | LLM-general Adapter Protocol。Codex Security = first concrete | D5 |
| anchor | Phase G canonical_id 空間へ射影。**具体レシピは暫定 (実装時調整)** | D6 |
| 精度方針 | **誤検知 > 見逃し** (high recall / fine-grained / rename re-projection は code delta 拡張が前提) | D7 |
| 昇格 | 自動昇格なし。target.yaml authoring freeze が昇格ゲート。沈黙 = 容認 | D8 |
| 監査 / waiver | provenance に informed-consent 記録 (verdict 非参照)、waiver = advisory mute | D9 |

## 1. Core 設計判断

### 1.1 D1: LLM は scout であって judge ではない

**決定: LLM センサーは常駐 gate ではなく、呼んだときだけ走る偵察。verdict を
直接 seat しない。**

- ジャッジ (常駐して合否を出す番人) にすると、外部 LLM の不安定さ・コスト・
  レート制限が毎回 CI を詰まらせる or vacuous PASS を誘発する
- scout (呼んだときだけ偵察して候補を報告) にすれば、LLM が居なくても gate は
  通常通り動く。LLM 出力は **Advisor surface に流れ、verdict には直接効かない**
- scout の真の役割は「作者の沈黙を *無知の沈黙* から *承知の上の沈黙* へ変える」
  こと (D8 と対)

これにより scope guard「not an LLM-as-judge service」との衝突が消える。
LLM はジャッジしない。合否を出すのは決定論的な宣言制約 (target.yaml)。

**実装規律 — verdict 分離 (PR #132 review P2 由来)**: D1 を実装で保証するには、
LLM finding を Phase G の verdict 経路 (`compute_security_delta` →
`evaluate_security_detail` → `combine_verdict`) に渡してはならない。現行 suite は
failing severity の added `SecurityFinding` を自動的に fail に変換するため、LLM
finding を通常の verdict-bearing candidate `SensorState` に frozen すると、
scope guard に反して scout が verdict を直接 seat してしまう。よって:

- suite evaluator に渡す **verdict-bearing SensorState は deterministic sensor
  (semgrep / pip-audit) の finding のみ**を含む
- LLM 由来 finding は **advisory-only な別チャネル (advisory SensorState /
  surface、§2.4)** に分離し、verdict 計算に入れない
- LLM finding が verdict に効くのは D8 の authoring freeze 後のみ (target.yaml に
  宣言され deterministic な制約へ転写された時点。LLM が seat するのではない)

この分離は H-1 の AC とし、failing-severity の LLM finding が存在しても
`suite_verdict` が変化しないことを architecture test で enforce する。Q1 (§2.2)
の category 選択 (相乗り vs `LLMSecurityFinding` 新設) はこの分離の二次手段で
あり、**verdict 除外の一次保証はチャネル分離**である。

### 1.2 D2: 決定論の保全 — LLM は core の外、frozen SensorState を ingest

**決定: LLM scan の実行は adapter 層に閉じ込め、core/suite は Phase G の
SensorState schema のみを知る。**

Phase G が既に確立した「scanner 実行は adapter 責務、core は SensorState の
schema だけ知る」境界 (phase_g_planning §5 Scope Guard) をそのまま継承する。
LLM finding は adapter 層で SecurityFinding 系 schema (§2.2) に翻訳され、
`SensorState` として frozen される。ただし §1.1 の verdict 分離規律により、
この **LLM SensorState は verdict-bearing な candidate SensorState とは別の
advisory チャネル**に置く。frozen state を食う点で評価層は決定論的だが、
verdict を seat するのは deterministic sensor の SensorState のみで、LLM 由来
state は verdict 計算に入らない。

これは §23.1 input neutrality の鏡像: SensorState は hand-built / 仮想入力でも
構築可能でなければならず (phase_g AC)、LLM 由来 state も「記録された観測」として
同じ経路を通る。

### 1.3 D3: §23.1 / Sensor Provenance Invariant への影響分析

**決定: §23.1 / Sensor Provenance Invariant は weaken しない。ただし新しい
非決定論クラスを D4 で明示的に吸収する。**

CLAUDE.md のルール「neutrality を弱める feature は §23.1 違反として brief で
flag せよ」に従い、ここで明示分析する:

- SSP / Phase G の不変条件は「verdict は **記録された SensorOutput から**
  再現可能」(Sensor Provenance Invariant) であり、最初から「コードから再現」
  ではない。これは外部・ノイズあるセンサーを受け入れるために**意図的に
  センサー側に置いた譲歩**である
- LLM scan の非決定論は **記録 artifact の生成段階** に隔離される。frozen
  SensorState 上の verdict は決定論的 → **不変条件は破れない**
- **新しい wrinkle**: semgrep は (version, ruleset) 固定で再現するが、LLM は
  入力固定でも再現しない。よって LLM sensor の SensorState は「再生成しても
  一致しない frozen artifact」として扱う必要がある (D4)。provenance には
  model_id / prompt_hash / 生成 timestamp を **監査用に** 記録するが、これらは
  「再現可能性の主張」には使わない (verdict 非参照)

結論: §23.1 violation には**該当しない**。LLM sensor は semgrep と同じ
「core の外のセンサー」枠に収まり、追加の非決定論は D4 の re-projection 規律で
構造的に封じる。

### 1.4 D4: 非決定論ノイズの封じ込め — one-run + 決定論的 re-projection

**決定: LLM sensor では「2 回の独立 scan の差分」を禁止し、「candidate に 1 回
scan → 各 anchor を baseline コードへ決定論的に再投影」を必須とする。**

非決定論ノイズの非対称性 (baseline 側 recall miss は "added" を水増し、
candidate 側 miss は "removed" を捏造する) を構造的に断つ。

```
禁止 (unsound):
  baseline_findings = LLM_scan(baseline_code)   # 揺れる
  candidate_findings = LLM_scan(candidate_code) # 揺れる (独立ノイズ)
  added = candidate_findings − baseline_findings  # ノイズが added に混入

必須 (sound):
  candidate_findings = LLM_scan(candidate_code)         # 1 回だけ
  for f in candidate_findings:
      anchor = project_to_canonical(f)                  # D6
      present_in_baseline = anchor_exists(anchor, baseline_code)  # 決定論的
  # baseline 側の存在確認は LLM 再実行ではなくコード構造の決定論的照合
```

semgrep のような決定論センサーでは re-projection は任意 (どちらでも結果同じ)
だが、**LLM sensor では必須**。adapter Protocol (§2.1) はこの規律を型・契約で
強制する。

### 1.5 D5: LLM-general Adapter Protocol (Codex Security = first concrete)

**決定: アダプターは特定ベンダーに依存しない「LLM セキュリティセンサー一般を
anchor 射影で SensorState に翻訳する Protocol」として spec る。Codex Security は
その最初の concrete 実装 (reference adapter)。**

Brief 5 (Repair Compiler) の「Adapter Protocol + 具象 adapter 3 種」構造を再利用。
provenance-neutrality (sensor が誰でも後段は不変) により、同一 anchor 空間に
潰れる限り Codex Security / Claude security review / 他モデル / **複数モデルの
アンサンブル** が交換可能に接続できる。

副産物 (一般化固有の利得):

- **クロスモデル集約は「自動」では成立しない — 明示ステップを要求する**:
  Phase G の `identity_components` は `sensor_id` を含む
  (`SASTSecurityFinding._identity_components_match_sast_fields` 等) ため、
  異なる LLM adapter は同じ脆弱性を見つけても **別の canonical_id** を生む。
  逆に sensor_id を正規化して同一 ID に寄せると、`SensorState`
  の一意性 validator (`_validate_state_invariants`) は重複 canonical_id を
  **併合せず reject** する。したがってクロスモデル集約は anchor 一致だけでは
  起きず、以下のいずれかを **必須**とする (H-5 / Q4 で確定):
  - (a) **SensorState 構築前の明示的 dedup/集約ステップ** (複数 adapter 出力を
    1 つの正規化された finding 集合へ束ねてから SensorState に渡す)、または
  - (b) **ensemble を単一 sensor identity (1 つの sensor_id) として束ねる設計**
    (個々のモデルは ensemble adapter の内部実装に隠れる)
  どちらでも recall は N モデル分広がるが、集約は型・契約で明示する。
- **oracle / verifier 分離**: LLM = oracle (広く探す、再現不能でよい)、
  suite = verifier (決定論的、監査可能)。gate の健全性は oracle の質に依存しない

### 1.6 D6: anchor projection (Phase G canonical_id 空間へ) — 暫定

**決定: LLM finding を Phase G の canonical_id / FQN 空間へ射影する。ただし
anchor の具体構成レシピは *暫定* とし、実装時に適宜組み替える。**

LLM finding (自由記述の攻撃経路) を、点に帰着する anchor へ正規化する。
これは Phase G が SAST finding に対してやっている `(rule_id, module_path,
qualified_name, normalized_text, ordinal)` 翻訳 (phase_g §1.2) と同型の操作。

暫定方針 (実装で再評価):

- sink に帰着する finding (injection / IDOR 等) → sink の qualified_name +
  finding class を anchor に
- 非局所な攻撃経路 → (source, sink) 端点対を anchor に
- **不在の脆弱性** (missing authz/validation) → 指す AST ノードが無いため、
  「チェックが在るべき site (endpoint) + 欠落プロパティタグ」の対を anchor に
  (= `(site, expected_property)` という canonical 語彙の拡張)

この語彙設計は実務上の最適点が実装まで確定しないため **暫定固定**とし、
brief AC では「anchor 構成を後から組み替えられる差し替え可能な
`project_to_canonical()` として実装する」ことを要求する (identity algorithm
version prefix `vN:` により再構成時の hash 変化は Phase G の機構で吸収される)。

### 1.7 D7: 精度方針 — 誤検知 > 見逃し

**決定: トレードオフがある場合は誤検知 (false positive) 側に倒す。「炙り出せば
検証できるが、見つからなければ検証すらできない」。**

3 箇所に適用:

1. **オラクルのチューニング = 高 recall**: フィルタで絞らず広く拾う
2. **anchor 同一判定 = 細粒度寄り**: 迷ったら別物として両方出す (併合しすぎは
   別の穴を隠す = 見逃しを生む)
3. **gate ではなく surface**: 高 recall の代償 (ノイズ) は、scout 出力を
   Advisor チャネル (止めない) に置くことで吸収する (D1)

細粒度 anchor の代償は rename で誤検知が増えることである (rename 前後で
anchor の `qualified_name` / `module_path` がズレ、現存する脆弱性が "added" に
見える)。これを相殺するには **old_path → new_path の rename マップが code delta
に必要**だが、現状の core はこれを露出していない:

- `cli/git_diff.py` の `NumstatEntry.old_path` は git numstat の rename 元パスを
  parse 済だが、`cli/delta_overlay.py` は集約値 (`files_touched` / `loc_delta`)
  しか overlay せず、old_path → new_path 対応を捨てている
- `delta/code_state_delta.py` の `module_graph_delta` は import edge の集合差分の
  みで rename を追跡しない

したがって rename re-projection は「既存 core が rename 追跡を持つ」前提では
成立せず、**code delta に rename マップを露出させる前提作業を H-2 の scope に
含める** (§3 H-2)。この前提が入って初めて「誤検知に倒しつつ、一番うざい純粋
rename ノイズだけは構造的に消す」が実現する。

### 1.8 D8: 昇格は target.yaml authoring freeze のみ — 沈黙 = 容認

**決定: scout 候補の制約化に自動昇格を設けない。target.yaml に起こした時点
(human / AI 入力を問わず authoring 経路) で制約化。宣言が無ければ作者の容認
(意図的握りつぶし = 仕様どおり) とみなす。**

- 昇格ゲートは **新規不要**: Brief 8 authoring surface の freeze 点 +
  Phase G `security:` namespace をそのまま再利用。scout は Advisor/Authoring
  surface に候補を出す → 人 or AI が target.yaml に書く → freeze で declared
  intent に固定 → 以降は決定論的 verdict が所有
- **沈黙 = 容認は vacuous PASS と別物**: §23.3 に従い、ツールは intent
  validator / interpreter ではない。宣言が無い = 宣言された (非)意図として
  額面通り受ける。これは「作者が本当はチェックしたかったはず」を推測しない
  core 哲学そのもの
- **保証レベルは作者が自己選択**: 保証が欲しければ target.yaml で宣言する
  (→ 報告書が無ければ Phase G の `provenance status != complete → unknown`
  経路で止まる)。宣言しなければ作者がリスクを引き受ける

AI 生成の target.yaml も許容される (Brief 8 の生成経路 3 通りの一部)。
誰が生成しても freeze 後は declared intent として決定論的に扱われる不変条件は
変わらない。

### 1.9 D9: informed-consent の provenance 記録 + waiver = advisory mute

**決定: 「scout が炙り出した / 宣言した / 見た上で容認した」を provenance
チャネルに記録する (verdict 非参照)。waiver は verdict 機構ではなく advisory
ミュート (低 stakes) に格下げする。**

- **監査**: verdict は (宣言の有無で) PASS でも、「scout を走らせて N 件炙り
  出し、M 件を宣言、K 件を容認」を provenance に記録する。これで「この PASS は
  無知の沈黙か承知の容認か」が後から追える。provenance surface は evaluator
  不可参照 (Phase G / §23.3 のルール) なので verdict には効かない
- **surface の 2 枚分割**:

  | 置き場 | 意味 | verdict | 由来 |
  |---|---|---|---|
  | target.yaml `security:` | 「これを gate する」(宣言制約) | 効く | Phase G |
  | advisory mute ledger | 「見た / 容認した / もう鳴くな」 | 効かない | 本 Phase 新設 |

- scout は止めない (advisory) ので、同じ候補が毎回出ても gate 失敗ではなく
  ただのノイズ。よって waiver は「verdict を曲げる仕組み」ではなく
  「scout をミュートする UX」。ledger のキー安定性は D6/D7 の anchor 方針
  (細粒度 + rename re-projection) を流用する

## 2. 新設 schema / protocol

> 全て Phase G の `sensor/` 機構の上に載る。CodeState / SensorState の
> 既存 schema は変更しない (additive)。以下は設計骨子で、確定形は各 CSCI brief
> の AC で固める。

### 2.1 LLMSensorAdapter Protocol

```python
# src/semantic_ci_code/sensor/adapters/llm/protocol.py (新設、骨子)
from typing import Protocol

class LLMSensorAdapter(Protocol):
    sensor_id: str          # "codex-security" | "claude-security" | ...

    def scan_candidate(self, candidate_code: CodeView) -> tuple[RawLLMFinding, ...]:
        """candidate に 1 回だけ scan を当てる (D4: 2-run 差分は禁止)。"""

    def project_to_canonical(self, finding: RawLLMFinding) -> SecurityFinding:
        """LLM finding を Phase G canonical_id 空間へ射影 (D6, 差し替え可能)。"""

    def provenance(self) -> SensorProvenance:
        """model_id / prompt_hash / timestamp を監査用に記録 (D3)。
        status != complete の場合は findings を所有しない (Phase G 継承)。"""
```

re-projection (各 anchor の baseline 存在確認、D4) は adapter ではなく
sensor delta 層が決定論的に行う (LLM 再実行を介在させない契約)。

### 2.2 LLM finding の category

`SASTSecurityFinding` に相乗りするか、`LLMSecurityFinding` 新 category を
discriminated union に足すかは brief で確定する (Open Question Q1)。後者なら
`(site, expected_property)` 型の不在 anchor を表現しやすい。いずれも
canonical_id / identity_components / version prefix の Phase G 規律
(phase_g §1.2/§1.3) を継承する。

### 2.3 SensorProvenance の LLM 拡張

```python
# 非再現 sensor 用の追加フィールド (監査専用、verdict 非参照)
model_id: str | None            # "codex-security-2026-03" 等
prompt_hash: str | None         # 投入プロンプトの hash (監査追跡用)
non_reproducible: bool = False  # True: 再生成で一致しない frozen artifact
```

`non_reproducible=True` の sensor は drift 判定 (provenance 比較) の意味論が
deterministic sensor と異なる (再 scan しても一致しないため version 比較は
無意味)。よって LLM sensor の baseline 照合は D4 の re-projection に一本化する。

### 2.4 advisory mute ledger

`security:` namespace とは別の advisory 台帳 (verdict 非参照)。scout 候補の
ミュート記録のみを持つ。スキーマは Phase G `Suppression` を踏襲しつつ
「verdict に効かない」点が決定的に異なる (gate 用の suppression と混同しない)。

## 3. PR 分割案 (CSCI-50〜、Phase G-5 完走後)

### H-1: LLMSensorAdapter Protocol + advisory channel 分離 (CSCI-50)
- `sensor/adapters/llm/protocol.py` + `SensorProvenance` 拡張 (§2.3)
- `LLMSecurityFinding` category 採否を確定 (§2.2 / Q1)
- **verdict 分離 (§1.1 規律)**: LLM 由来 SensorState を verdict-bearing な
  candidate SensorState から切り離し、suite evaluator の verdict 経路
  (`compute_security_delta` → `combine_verdict`) に渡さない advisory チャネルへ
  routing する
- **AC 1**: hand-built RawLLMFinding → SecurityFinding 射影が決定論的、advisory
  SensorState に frozen 可能 (§23.1 鏡像)
- **AC 2 (verdict 分離)**: failing-severity の LLM finding を advisory チャネルに
  与えても `suite_verdict` が変化しないことを architecture test で enforce
  (deterministic sensor の同 severity finding は従来通り verdict を動かすことも
  同時に固定し、分離が deterministic 経路を壊していないことを確認)

### H-2: anchor projection + 決定論的 re-projection (CSCI-51)
- `project_to_canonical()` の暫定実装 (D6、差し替え可能な構造)
- sensor delta 層に one-run + baseline 再投影 (D4) を実装
- **前提作業 (本 H-2 scope 内)**: code delta に old_path → new_path の rename
  マップを露出させる (D7)。`NumstatEntry.old_path` は parse 済だが
  `delta_overlay.py` / `code_state_delta.py` が捨てているため、まず rename マップ
  を delta に乗せる必要がある
- 上記 rename マップに rename re-projection を接続 (D7)
- **AC**: 2-run 差分を取らないことを architecture test で enforce、
  rename マップ実装後、rename した baseline で同一脆弱性が "added" に出ない

### H-3: Codex Security reference adapter (CSCI-52)
- `sensor/adapters/llm/codex_security.py` (first concrete, §1.5)
- on-demand 実行 (D1)、fixture mode (記録済み出力の ingest) 必須
- **AC**: Codex Security 出力 (or fixture) が SensorState に正規化される、
  LLM 不在でも fixture 経路で CI 成立

### H-4: advisory surface + mute ledger + informed-consent provenance (CSCI-53)
- scout 候補を Advisor チャネルに出力 (止めない、D1/D7)
- advisory mute ledger (§2.4)
- provenance に「炙り出し / 宣言 / 容認」記録 (D9)
- **AC**: 宣言なし = PASS のまま provenance に容認痕跡、mute 済み候補は再 surface
  されない

### H-5: target.yaml 昇格経路ドキュメント + クロスモデル集約 (CSCI-54)
- scout → authoring freeze → 制約化の経路を `docs/` に明文化 (D8)
- 複数 LLM adapter のクロスモデル集約を **明示ステップ**として実装 (§1.5 / Q4):
  (a) pre-SensorState dedup/集約、または (b) ensemble sensor identity
  (単一 sensor_id) のいずれかを選択
- **AC**: 2 つの LLM adapter が同一脆弱性を報告したとき、選択した集約方式で
  1 件に束ねられ、`SensorState` の一意性 validator を通過する regression test。
  **sensor_id を保持したまま同一 canonical_id を期待してはならない** (Phase G の
  `_validate_state_invariants` が重複を reject するため。§1.5 参照)

## 4. 移行戦略 / Phase G との関係

- 本 Phase は Phase G-5 完走後に着手 (SensorState / suite evaluator /
  `security:` namespace / suppression を全面前提)
- deterministic sensor (semgrep / pip-audit) の挙動は不変。LLM sensor は
  並列の追加センサーとして共存し、`SensorState.provenance_by_sensor` に
  独立 entry を持つ (per-sensor drift / verdict は Phase G 機構をそのまま使う)
- `non_reproducible` provenance は additive。既存 deterministic sensor の
  provenance は `non_reproducible=False` (default) で不変

## 5. Scope Guard

- core evaluator (`evaluator/`) は変更しない。LLM 由来 finding は **advisory
  チャネルに分離**し、suite の verdict 経路 (`compute_security_delta` →
  `combine_verdict`) には渡さない (§1.1 verdict 分離規律)
- CodeState / SensorState の既存 schema は変更しない (additive のみ)
- LLM scan 実行は adapter 層の責務。core/suite は SensorState schema のみ知る
- **LLM は scout であって judge ではない** (D1): verdict を seat するのは
  決定論的宣言制約。これにより「not an LLM-as-judge service」を侵さない
- §23.1 input neutrality は維持 (D3 分析): SensorState は hand-built /
  fixture でも構築可能、非決定論は記録 artifact 生成段階に隔離
- 決定論性: 評価層は frozen SensorState のみを食う。LLM の非決定論は
  D4 (one-run + 決定論的 re-projection) で構造的に封じる

## 6. Open Questions

- **Q1**: LLM finding は `SASTSecurityFinding` 相乗りか `LLMSecurityFinding`
  新 category か (§2.2)。不在 anchor `(site, property)` の表現しやすさで判断
- **Q2**: re-projection の「anchor が baseline コードに存在するか」の決定論的
  判定を、どの core 機構 (api_surface / module_graph / 新規) で実装するか
- **Q3**: advisory mute ledger は target.yaml に同居 (別 namespace) か、
  別ファイル (`.semantic-ci/advisory_mutes.yaml`) か (Phase G D6 の案 A/B と同型)
- **Q4**: クロスモデルアンサンブルで provenance をどう集約するか
  (model ごとに別 sensor_id か、ensemble を 1 sensor_id 扱いか)
- **Q5**: anchor 暫定レシピ (D6) の確定タイミング — どの実 finding 集合で
  実装時較正するか (dogfooding pass が必要か)

## 7. Required Reading (本 Phase brief 起草時)

1. 本 planning doc 全体
2. `docs/phase_g_planning.md` — SensorState / canonical_id / suite evaluator /
   suppression の前提機構 (特に §1.2/§1.3/§2.1)
3. `docs/code_semantic_ci_design.md §23` — engine contract / §23.1 input
   neutrality / §23.3 responsibility boundary (scope guard の根拠)
4. `docs/ssp_protocol.md` — Sensor Provenance Invariant の normative 定義
5. `docs/target_authoring_surface.md` — authoring freeze (D8 昇格ゲートの前提)
6. `src/semantic_ci_code/sensor/` — Phase G 実装 (相乗り先)
7. 本 planning doc 自身 (§0.4 D1-D9 蒸留表 + §1 各 D 本文) — 設計判断の一次
   記録。壁打ち会話ログは wrap-up 時に当日の `.claude/memory/` dated log へ
   externalize される (起草時点では未 externalize。`2026-06-03.md` は Phase G
   wrap-up のみで本議論は含まないため、この doc を読むこと)

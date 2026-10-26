# Nyxis 調査 & 認可カバレッジ / 制約スコープ設計 (authz coverage planning)

Status: **PLANNING (open)** — 2026-10-26 起草。実装 brief は未発行。

外部フレームワーク **Nyxis** (Lean 4 で認可安全性を形式証明したバックエンド
フレームワーク、2026-10-26 公開) を semantic-ci に導入・統合する価値があるかを
調べた記録と、その調査で見つかった semantic-ci 側の改善余地の設計。

---

## 0. 要約

| 問い | 判定 |
|---|---|
| Nyxis をそのまま取り込む (依存 / sensor / adapter) | **見送り** (§3.1 R1〜R4) |
| Nyxis の設計思想を semantic-ci に持ち込む | **採用 (3 点)** (§3.2) |
| 調査中に見つかった既存の不具合 | **F1: constraint-level `scope:` が評価されていない (再現済み)** (§4) |

一言でいうと、Nyxis は「宣言 (Cedar policy) → AI が書いたコード → 宣言を超えない
ことを証明」という、semantic-ci の `Declared intent → Observed state → Verdict` と
**同じ形のパターン**を、制約をかけて健全性 (soundness) を得る方向で実装している。
コードを取り込む価値は低い。一方で、比べてみると semantic-ci 側の穴が 3 つ見えた:

1. **F1** — 制約の `scope:` が表示されるだけで評価されていない
2. **F2** — 認可ガードは「消したら検出」だけで、「新しいエンドポイントに付け忘れ」は検出できない
3. **F3** — 「PASS が何を保証し、何を仮定しているか」を一か所にまとめた文書がない

---

## 1. Nyxis 調査 (事実)

一次資料: `NyxFoundation/nyxis` の README.ja.md / ASSUMPTIONS.ja.md
(commit `785c11a`、2026-10-26)。リリースは v0.1.0 / v0.1.1 で、どちらも
2026-10-26 にタグ付け。独立した監査や利用報告は見つからなかった。

- **構成**: 開発者が書いて承認するのは Cedar のスキーマとポリシーだけ。ハンドラは
  `Nyxis.Handler` 型で書き、ハンドラが持てる効果は「認可層へのアクション呼び出し」
  だけ。IO や DB に直接触る手段はない (制約をかけて健全性を得る設計)。
- **定理**: `Nyxis.Runtime.authorization_safety` — 任意の App・初期状態・認証済み
  要求列について、発行される DB 操作 / 外部効果 / ハンドラに渡る値が、承認済み
  ポリシーが permit した範囲に収まる (ASSUMPTIONS「定理が述べること」(1)〜(9))。
  `lake build` のたびに Lean カーネルが検査し、公理は `propext` /
  `Classical.choice` / `Quot.sound` だけ。
- **前提にしている仮定 (ASSUMPTIONS)**:
  - A1 証明の外で動くコード — HTTP 復号、JWT 署名検証、libpq/SQL の意味論、
    curl、判定材料の SELECT 結果が「現在の行」であること、ツールチェーン / FFI
  - A2 クラウドと実行環境 — Supabase Auth / PostgreSQL / Storage / SMTP / TLS / 時計・乱数
  - A3 開発者が正しく使うこと — **デプロイする Cedar 正本 = 人間が承認したもの**。
    「承認していないポリシーがデプロイされれば、証明は成り立ったまま、意図しない
    権限が『正当』になる」と本文が明記している。
- **範囲**: 定理は**純粋モデル**上の性質で、つなぎのコードの多くは未証明 (A1)。
  「情報漏洩が起きないことの数学的保証」は、正確には「**承認済みポリシーに対する
  認可安全性の、モデル上の保証**」である。

---

## 2. 構造比較

| 軸 | Nyxis | semantic-ci |
|---|---|---|
| 宣言 (人間が承認) | Cedar スキーマ + ポリシー | `target.yaml` |
| AI に任せる部分 | ハンドラ | コード変更 (PR / 生成) |
| 保証の種類 | **健全性** — 型でハンドラの効果を制限し、全経路を証明 | **adherence** — 任意の Python から観測した状態が宣言を満たすか |
| 量化の範囲 | 全要求列 (∀) | 宣言された制約 × (baseline, candidate) |
| 観測の確からしさ | 証明済み (モデル上) | AST 静的抽出 (ヒューリスティック) |
| 宣言そのものが正しいか | **範囲外 (A3)** | **範囲外 (§23.3)** |
| 言語 | Lean 4 (+ Cedar) | Python |

**同じ形をしている点**: どちらも「宣言が正しいこと」は保証の外に置き、人間の承認に
任せている。Nyxis A3 と design §23.3 (Adherence, not Correctness) は、ほぼ同じ立場
を独立にとっている。

**違う点**: Nyxis は**書けるコードを制限する**ことで ∀ (全経路) の保証を得る。
semantic-ci は**任意のコードを観測する**ので、得られるのは「宣言した観点について
観測の範囲内で adhere している」までである。この差は欠点ではなく役割の違いだが、
semantic-ci は観測できる範囲を利用者に明示する責任がある (→ F3)。

---

## 3. 統合判定

### 3.1 直接統合 — 見送り

- **R1 対象の不一致**: Nyxis のアプリは Lean で書かれ、semantic-ci の extractor は
  Python 専用 (design §22 multi-language phasing)。Nyxis の利用者のコードを
  semantic-ci は観測できない。
- **R2 足すものがない**: Nyxis の検査は「`lake build` が exit 0 + 公理チェック」で、
  普通の CI ジョブで足りる。SSP sensor として包んでも、SSP は finding を指紋で
  差分化する protocol (`docs/ssp_protocol.md`) であり、真偽 1 個の証明結果を
  載せても意味のあるズレ (ΔE) は生まれない。
- **R3 成熟度と外部依存**: v0.1.1・公開当日・Supabase 前提。Coding Conventions の
  「明示 brief なしに vendor coupling を入れない」に当たる。
- **R4 Nyxis の残る穴は別の手段で塞げる**: Nyxis 利用者にとって一番効く補強は A3
  (承認していないポリシー変更) の検出だが、それは `*.cedar` への CODEOWNERS +
  branch protection で塞げる。semantic-ci で同じことをやるには Cedar extractor
  という新しい対象が必要になり、費用に見合わない。

**再検討の条件**: (a) semantic-ci が Python 以外の対象を扱うようになったとき、
または (b) 「ポリシー差分が権限を広げたか」の semantic diff の需要がはっきりした
とき。どちらも別の planning を起こす。

### 3.2 設計思想の輸入 — 採用 3 点

| # | Nyxis の考え方 | semantic-ci への翻訳 | 対応 |
|---|---|---|---|
| I-1 | ハンドラは認可層を通らないと効果を持てない (範囲を限定した保証) | 制約を**モジュール範囲に限定**して評価できるようにする | F1 → D-1 `select:` |
| I-2 | 「全要求列」で量化する (付け忘れも違反) | 「**ガードの付いていないルートが増えない**」を宣言できるようにする | F2 → D-2 recipe |
| I-3 | ASSUMPTIONS.md (仮定 / 破られると / 守り方 / 検査 の 4 点) | 「PASS が意味すること」の文書を作る | F3 → D-4 doc |

---

## 4. Findings (semantic-ci 側)

### F1 — constraint-level `scope:` が評価されていない (確認済み)

- `_BaseConstraint.scope: JsonValue` (`framework/constraint_types.py:64`) は
  compile を通って `CompiledConstraint.scope` に入り、JSON / human 出力と repair
  adapter (`repair_compiler/adapters/{markdown,codex}.py`) には**表示される**。
  しかし `evaluator/` では一度も参照されていない。
- design §4.5 のサンプル `no_new_io_in_models` (`scope: src.models.*`) は、
  書かれたとおりには動かない。
- **再現** (hand-built `CodeState`、上のサンプルをそのまま使用): baseline =
  空、candidate = `src.api.users.fetch` に `net` effect を 1 件 (scope **の外**)。
  → 判定は `no_new_io_in_models: violated`。`target-doctor` も
  「no advisories detected」で何も言わない。
- **ズレる向きは operator によって違う**:
  - 全称型 (`no_new_items` / `excludes_all` / `subset_of` …): scope の外の
    項目まで拾うので **誤 FAIL**
  - 存在型 (`includes_any` / `includes_all` / `superset_of` …): scope の外の
    項目で条件が満たされてしまうので **誤 PASS** (vacuous PASS の一種)
- **さらに Advisor 面でもズレる**: repair 指示には「Scope: src.models.*」と
  表示されるので、修正する側 (人 / AI) は範囲が限定されていると信じてしまう。
  §23.3.2 の「Advisor は宣言の意味を保ったまま render する」に対して、render
  した内容と Validator が実際に評価した内容が食い違っている。
- **系統**: `extension_survey_planning.md` S1 (ghost-facet = extractor が
  ないのに書ける facet) の兄弟で、**ghost-field** (評価器が読まないのに書ける
  フィールド) にあたる。S1 / CSCI-57 は path を対象にしており、フィールドは
  範囲に入っていない。

### F2 — 認可ガードは「削除」しか検出できない

- `security:preserve-auth-guards` (`cli/init_recipes/security_preserve_auth_guards.py`)
  は `decorators_delta.removed` に `excludes_all` をかけるだけ。
  **baseline にあったガードの削除**しか捕まえられない。
- AI が書いたコードでいちばんよく起きる認可不備 — **新しいエンドポイントにガードを
  付け忘れる** (OWASP A01 の典型例で、Nyxis もこれを動機にしている) — は、
  今の DSL では書けない。集合 operator は対象全体と `expected` を比べるだけで、
  「この decorator を持つ項目は、あの decorator も持つ」という**項目ごとの条件**
  を表現する手段がない。
- 既存の関数に route decorator が新しく付いた場合 (`decorators_delta.added`) も
  検出できない。

### F3 — 保証範囲と前提の仮定を一か所にまとめた文書がない

- 保証の境界は §23 (contract)、`target_yaml_guide.md` の Hazard 1〜5、
  `dogfooding_findings_tracker.md`、`ssp_protocol.md` に散らばっている。
  「semantic-ci の PASS は何を意味し、何を仮定しているか」に一か所で答える
  文書がない。
- 過去の実例: 2026-06-07 dogfood で SAST の効果を言い過ぎて、後で訂正した
  (fed1b87)。Nyxis の ASSUMPTIONS 形式は、こうした言い過ぎを構造的に防ぐ。

---

## 5. 設計

### 5.1 D-1 `select:` — 型付きの項目セレクタ (F1 / I-1)

operator を評価する**前に**、対象の集まり (baseline 側・candidate 側・delta 側の
すべて) を項目ごとの条件で絞り込む。(CodeState, constraint) の純粋関数なので、
§23.1 (入力の出自を問わない) と hand-built state をそのまま保てる。

```yaml
- id: no_new_io_in_models
  kind: delta
  target: effects
  operator: no_new_items
  select:
    fqn_prefix: ["src.models."]          # いずれかに前方一致 (any-of)
    exclude_fqn: ["src.models.legacy.x"] # 完全一致で除外
  severity: hard
  unknown_policy: fail
```

| key | 意味 | 使える target |
|---|---|---|
| `fqn_prefix` | 項目の `fqn` がいずれかに前方一致 | `fqn` を持つすべての path (api_surface*, effects, effect_changes.*, decorators_delta.*, complexity, control_flow …) |
| `exclude_fqn` | 完全一致の除外リスト (公開エンドポイントの allowlist など) | 同上 |
| `has_decorator_any` | 項目の decorator のどれかが match (`{decorator}` / `{decorator_leaf}`) | `api_surface` / `api_surface_public` / `api_surface_delta.*` |
| `lacks_decorator_all` | 項目の decorator がどれも match しない | 同上 |
| `project` | `fqn` を指定すると、絞り込んだ項目を `{fqn}` だけに落とす (同一性を fqn で判定) | 同上 |

ピン:

- **前方一致のみ**。glob / regex は入れない (`*` の解釈の揺れと、正規表現の評価
  差を持ち込まないため)。
- target と key の組み合わせは compile 時に検査し、不正なら `CompileError`
  (authoring 起因)。`match_schema.py` の path ごとの schema と同じ仕組みを使う。
- `project: fqn` は ratchet (`no_new_items` を baseline と比べる用途) に必要。
  項目全体で比べると、もともとあった違反項目の signature が変わっただけで
  「新しい項目」扱いになり、誤 FAIL が出る。
- 0 件にしか当たらない select は vacuous PASS の温床になる。D4 / D6 と同じ
  diff-aware の advisory 候補 (Q4)。
- **互換性**: `target.yaml` の入力に任意フィールドを足すだけで、verdict envelope
  (`schema_version="6"`) の形は変えない想定。`target_svp.schema.json` が
  additive に変わる扱いでよいかは、`docs/json_schema.md` の互換性ポリシーと
  照らして brief で確定する (Q5)。compiled target の hash には select が入る。

### 5.2 既存の `scope:` の扱い (F1)

| 案 | 内容 | 評価 |
|---|---|---|
| (a) `scope` を実際に効かせる | 文字列を前方一致として評価する | 既存フィールドの意味が黙って変わり、すでに書かれた target の判定結果が変わる。監査しにくい |
| **(b) advisory + 非推奨化** | `scope` を書いた制約に ADVISORY を出し (「scope は評価されない、`select:` を使う」)、design §4.5 のサンプルを直す | **推奨**。判定結果は変わらず、ズレが見えるようになる。CSCI-57 (ghost-facet advisory) と同じ `advisory-3` bump に相乗りできる |
| (c) compile error にする | `scope` を拒否する | 既存の target が壊れる。`init` が `{"files": [], "modules": []}` を出している (`cli/init_command.py:220` — これは `change.scope` 側で別物だが、名前が紛らわしい) こととの整合も要る |

推奨は **(b) をすぐ → D-1 を後で**。`select:` が入った後、`scope` の除去は
v0.1.0 の後に別途判断する。

### 5.3 D-2 recipe `security:require-route-guards` (F2 / I-2)

```yaml
- id: security:require-route-guards
  kind: state
  target: api_surface
  select:
    has_decorator_any:
      - {decorator_leaf: route}
      - {decorator_leaf: get}
      - {decorator_leaf: post}
      - {decorator_leaf: put}
      - {decorator_leaf: patch}
      - {decorator_leaf: delete}
      - {decorator_leaf: api_view}
    lacks_decorator_all:          # AUTH_GUARD_DECORATORS を preserve recipe と共有
      - {decorator_leaf: login_required}
      - {decorator_leaf: requires_auth}
      - {decorator_leaf: permission_required}
    project: fqn
  operator: no_new_items           # ratchet: 「ガードなしルート」が baseline より増えない
  severity: hard
  unknown_policy: fail
```

- **既定は ratchet** (`no_new_items`、baseline と比較): 既存コードベースにある
  ガードなしルートで一斉に FAIL させず、増えた分だけを捕まえる。
- **strict 版** (Nyxis 流の ∀): `operator: equals` + `expected: []`。公開して
  よいエンドポイントは `exclude_fqn` に宣言する。
- 捕まえられるもの: (i) ガードなしで新しく追加したルート、(ii) 既存の関数に
  route decorator が付いた場合、(iii) ガードの削除 (preserve recipe と重なるが、
  target が違うので D3 の重複には当たらない)。
- `@app.get("/x")` は extractor で `"app.get"` (leaf `get`) になる
  (`api_surface/python_api_extractor.py::_decorator_name`)。leaf `get` は
  `@cache.get` のような route 以外にも当たりうる。recipe の既定は leaf で、
  `--from-*` で `{decorator: app.get}` のような完全名に絞れるようにする。

**見えないもの** (`target_yaml_guide.md` に Hazard 6 として明記する):

| パターン | 結果 | 向き |
|---|---|---|
| FastAPI の `Depends()` (signature) / router 単位の `dependencies=` | ガードなしに見える | 誤 FAIL |
| middleware による認証 | ガードなしに見える | 誤 FAIL |
| 関数内のチェック `if not user.is_authenticated` (G-6 の deferral と同じ) | ガードなしに見える | 誤 FAIL |
| Django CBV の `LoginRequiredMixin` | decorator ではないので見えない | 誤 FAIL |
| `app.add_url_rule` / `urls.py` によるルート登録 | **ルート自体が見えない** | **誤 PASS** |
| unguarded ルートの rename | ratchet で新しい項目に見える | 誤 FAIL (renames overlay を state 側の比較に効かせるか → Q6) |

- **§23.3 の線引き**: この recipe が確かめるのは「宣言したガードが付いているか」
  だけで、**ガードのロジックが正しいか、ポリシーが妥当か**は範囲外。Nyxis A3 と
  同じ立場。
- **scope guard「This is not a linter」との緊張**: 単体で見ると lint ルールに
  似ている。だが (1) target author が選んで宣言する (recipe は既定値であって
  真実ではない)、(2) baseline との差分で判定する、という 2 点で既存の
  `security:deny-dangerous-effects` と同じ位置づけになる。brief にもこの論拠を
  書く。

### 5.4 D-3 recipe `security:confine-handler-effects` (I-1、後回し)

Nyxis の「ハンドラは認可層を通らないと効果を持てない」を Python で近似する:
`target: effects` + `select: {fqn_prefix: ["app.handlers."]}` + `excludes_all`
(`net` / `fs` / `io` / `process`)。

- 制約: `effect_db_python.yaml` には DB ドライバ / ORM (sqlite3 / psycopg /
  sqlalchemy) の signature がない (grep で確認済み)。ORM 経由の DB アクセスは
  effects に出てこないので、`module_graph` / `imports` 側の制約
  (「`app.handlers.*` が `app.db` を新しく import しない」) と組み合わせる必要が
  ある。このため優先度を下げ、D-1 / D-2 の後に設計を足す。

### 5.5 D-4 `docs/assurance_boundary.md` (F3 / I-3)

Nyxis の ASSUMPTIONS と同じ **4 点形式** (仮定 / 破られると何が起きるか /
利用者の守り方 / それを支える検査) で、semantic-ci の PASS の意味を書き下す。

- 冒頭で定義する: **PASS = 「宣言された制約について、抽出された観測状態が
  それを満たす」**。「コードが安全である」ではない。
- 項目案:
  - S-A1 extractor の忠実度 (AST 静的解析、decorator は名前だけ、動的
    dispatch は見えない、nested def (D6)、effect_db は有限リスト) — 検査:
    `tests/` の extractor contract、ADVISORY-D6 / D7
  - S-A2 宣言した intent の正しさ (§23.3。recipe は既定値であって真実ではない)
    — 検査: target-doctor (形式だけ。正しさは検査しない)
  - S-A3 入力の出自 (source selection、hand-built state は与えられたとおりに
    信頼、§23.1) — 検査: source-selection の architecture test
  - S-A4 sensor の出力 (scanner の正しさ、Semgrep registry に届くか — F6 は未検証)
    — 検査: SSP fixture mode / positive control
  - S-A5 ツールチェーン (Python / pydantic / PyYAML / `uv.lock`)
- docs だけで済むので、Wave 1 の W1-a (docs 整合 sweep) と並べて出せる。

---

## 6. Task plan (仮 ID — CSCI-62 以降を brief 発行時に確定)

| ID (仮) | 内容 | surface | 実行担当 | 規模 | 前提 |
|---|---|---|---|---|---|
| AZ-0 | D-4 `assurance_boundary.md` + design §4.5 サンプル修正 + F1 の注記 | docs | Sonnet | 0.5 日 | なし (Wave 1 と並走可) |
| AZ-1 | F1 の advisory (ADVISORY-S2 仮: 「constraint `scope` は評価されない」) | Authoring / Advisor | Opus | 0.5 日 | **CSCI-57 に相乗り** (同じ advisory-3 bump) |
| AZ-2 | D-1 `select:` (compile + evaluator + target schema + tests。hand-built `CodeState` のケース必須 = Engine Contract) | **Validator** | Opus | 1.5〜2 日 | AZ-1 |
| AZ-3 | D-2 recipe + `target_catalog` + guide Hazard 6 + dogfood (fail / pass の両方を実演) | Authoring | Sonnet | 1 日 | AZ-2 |
| AZ-4 | D-3 confine-handler-effects | Authoring | — | 未見積 | AZ-2、module_graph の調査 |

**順序**: 主軸は引き続き **E-3 (X-2 pilot)**。AZ-0 / AZ-1 は Wave 1 / Wave 2 に
並べられる (費用が小さく、既存の誤動作を見えるようにするだけ)。AZ-2 / AZ-3 は
Validator 面に機能を足すので、2026-06-10 S3 の「上物より外部検証を先に」
(gold-plating リスク) と比べる必要がある。ただし AZ-2 は**すでに書けてしまう
フィールドの誤動作を直すもの**であり、純粋な上物とは違う。どこに置くかは user が
判断する (Q2)。

---

## 7. 不変条件チェック

| 不変条件 | D-1 / D-2 / D-4 への影響 |
|---|---|
| §23.1 入力の出自を問わない | 維持 — select は CodeState 項目の純粋関数。git を必要としない |
| §23.3 Adherence, not Correctness | 維持 — ガードの有無を見るだけで、正しさは見ない (§5.3) |
| 決定論 | 維持 — 前方一致 / 完全一致のみ。regex なし |
| 新しい依存 / LLM / ネットワーク | なし |
| verdict envelope の schema | 変更なし (想定)。target schema は additive (Q5) |
| scope guard「not a linter」 | 緊張あり、論拠は §5.3 |

---

## 8. Open Questions (user 判断)

- **Q1** 既存の `scope` の扱い: (b) advisory + 非推奨化 (推奨) / (a) 実際に効かせる / (c) error
- **Q2** AZ-2 / AZ-3 を X-2 本実験の前に置くか後に置くか
- **Q3** recipe の既定: ratchet (推奨) / strict
- **Q4** 0 件にしか当たらない select の advisory を D4 型の diff-aware で出すか
- **Q5** `select:` の追加を target schema の additive 変更として扱えるか (`json_schema.md` の互換性ポリシーで確認)
- **Q6** renames overlay (H-2a) を、state 側の baseline 比較 (`no_new_items`) にも効かせるか

---

## 9. 出典

- Nyxis repository: <https://github.com/NyxFoundation/nyxis> (README.ja.md / ASSUMPTIONS.ja.md @ `785c11a`)
- Nyxis release v0.1.0 / v0.1.1: <https://github.com/NyxFoundation/nyxis/releases>
- 内部: `docs/code_semantic_ci_design.md` §4.5 / §22 / §23、`docs/phase_g_planning.md` G-6、
  `docs/extension_survey_planning.md` S1 / CSCI-57

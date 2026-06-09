# Project Status (live tracker)

This file is the live, daily-changing snapshot of the project: current phase,
recent merged PRs, and the next-issue queue. It moved out of `CLAUDE.md` so
the policy doc can stay stable while this file changes freely.

Update rules:

- This file is part of `.claude/memory/` and may be edited directly on `main`
  under the same exception as `_index.md` (see `CLAUDE.md` § Session Memory,
  Git exception).
- After each merged PR or session wrap-up, refresh **直近 merged** and
  **次の発行順序** here, and append a 1-line entry to `_index.md`.
- Other docs that need to point at the live tracker should reference
  `.claude/memory/STATUS.md` 次の発行順序 (not `CLAUDE.md`).
- If a CSCI / Brief / D# item is closed, leave it in 直近 merged for the
  current phase, and remove the corresponding entry from 次の発行順序.

For the canonical phase definitions, the Brief-by-Brief plan, and the design
spec, see `docs/code_semantic_ci_design.md` §12 / §25. For the per-session
historical record, see `_index.md` and `YYYY-MM-DD.md`.

---

## Phase

Brief 1〜8 + Brief 7 (SSP v0.1) + ResultStatus split + source-selection + doc refactor + **Phase G (SSP core integration、CSCI-45〜49) 全完走** + **Phase H (LLM security scout layer) 始動**。Phase G は SSP v0.1 を core の縦接続に再構築 (CodeState と並列の SensorState、suite evaluator で code+security 統合 verdict、SAST finding を FQN 空間に canonical_id 化、per-sensor provenance で drift 検出)、最終 G-5/CSCI-49 は config-free `decorators_delta` + `security:preserve-auth-guards` recipe で realize 済。2026-06-09 に **Phase H が gate 解除後始動**: 「LLM は scout であって judge ではない」(D1) を中心に、非決定論 LLM センサーを Phase G の sensor 機構に advisory-only で接続する設計を 3 スライス landing — H-1/CSCI-50 (PR #142、`LLMSecurityFinding` + `project_to_canonical` + `LLMSensorProvenance` + `compute_security_delta` の verdict reject guard) / H-2a/CSCI-51 (PR #143、`CodeStateDelta.renames` + `RenameEntry` CLI overlay) / H-2b/CSCI-51b (PR #144、`sensor/advisory.py` = baseline `CodeState` のみ ingest する deterministic one-run re-projection、absence anchor は固定表 decorator 判定・presence/未知 class/site 解決不能は D7 fallback で added、`AdvisoryReprojection` を verdict から型+import 二重隔離)。Phase H 残は H-3 (Codex Security concrete adapter + fixture mode) / H-4 (advisory surface + mute ledger + CLI 配線 + informed-consent) / H-5。並行して 2026-06-08 に pre-release credibility トラック (PR #136/#138 + repo desc/topics) 完走、tag は切らず experimental 明示の方針。次は Phase H 継続 (H-3 着手) / D-class closure (D6/D7/D8、exit criteria 前進) / Phase X (ecosystem cross-repo、別 session) のいずれか。

## 直近 merged

### 2026-06-09 (Session 2) — CLAUDE.md 圧縮 + 300 行 cap を discipline test 化 (PR #145)

記事 (とんのかつ氏「2 層メモリ + 自己改善ループ」) と本 repo 機構の機能比較から
派生し、「CLAUDE.md が肥大化原則を超過 (483 行) している実害」を repo 自身の記録で
実証 → user 指示で 2 修正を実装・merge。phase 進行には非影響の infra 改善。

- **圧縮**: CLAUDE.md 483 → 290 行 (ルール削除ゼロ)。src/tests ツリー →
  `docs/repository_layout.md` 新設、125 行 Session Memory 手順 → wrap-up skill
  (source-of-truth を CLAUDE.md から skill へ反転、archive-TTL/summary/anti-pattern
  を Appendix 化で情報損失ゼロ)。重複参照ブロックも圧縮。
- **discipline test**: `tests/discipline/test_claude_md_line_cap.py` (CLAUDE.md ≤ 300、
  超過検出の負例込み)。`tests/discipline/` 配置で wrap-up step 8 gate に自動編入 →
  終了プロトコルが cap 超過で fail するように。

**設計判断のハイライト**:

1. **実害は repo 自己記録で実証**: `doc_refactor_planning.md` の ≤200 目標 (起案 320)
   に対し CLAUDE.md だけが 483 にリグレッション。トークン固定費は 1M Opus で誤差だが、
   遵守劣化は documented recurring failure mode + 散文ルールの test 強制格上げ履歴で裏づけ。
2. **閾値は CLAUDE.md のみ ≤300** (AskUserQuestion 確定): STATUS.md 336 行ゆえ一律不可。
3. **layout doc を「構造マップ・filesystem 正典」に再定義**: 「Full per-module tree」の
   過剰約束が「hidden module X」型 review を無限誘発した根本原因を断つ。

**修正・訂正**:

1. **divergence 修正方向の論理矛盾** (Codex P2、私の混入バグ): 「skill wins」直後に
   「fix the skill」→ 正典上書き指示。「fix this pointer/summary」に訂正。
2. **移設ツリーが数世代 stale** (Codex P2 ×3): commands 6/10・authoring/sensor/suite
   欠落・nested subpackage 全欠落を filesystem diff が空になるまで補完。本 PR が解こうと
   した「always-loaded doc に詳細を抱えると腐る」問題の実例 (4 commit で消化、全 thread resolved)。

### 2026-06-09 — Phase H 始動: LLM security scout layer H-1〜H-2b (PR #142 + #143 + #144)

Phase G-5 完走で gate 解除された **Phase H (LLM security scout layer)** が始動。
「LLM は scout であって judge ではない」(D1) を中心に、非決定論 LLM センサーを
Phase G の sensor 機構へ **advisory-only** (verdict 非参与) で接続する 3 スライス
を landing。本 session の主眼は H-2b の設計確定 + PR #144 review。

- **PR #142** (CSCI-50 / H-1): LLM advisory finding protocol。`LLMSecurityFinding`
  (9 要素 identity) + `project_to_canonical(finding, *, sensor_id)` +
  `LLMSensorProvenance` (model_id/prompt_hash 必須・`non_reproducible=Literal[True]`)
  + `compute_security_delta` の LLM finding reject guard。
- **PR #143** (CSCI-51 / H-2a): `CodeStateDelta.renames` + `RenameEntry` を git
  numstat から CLI overlay で露出 (rename re-projection の前提データ)。
- **PR #144** (CSCI-51b / H-2b): `sensor/advisory.py` =
  `compute_advisory_reprojection(candidate_findings, baseline_code, *, renames)`
  + `AdvisoryReprojection`。**baseline は `CodeState` のみ ingest** (2-run LLM diff
  を型で不可能化、D4)。absence anchor は固定表 (`missing-authz` →
  decorator allowlist) で baseline guard 有無を判定、presence / 未知 class /
  site 解決不能は **D7 fallback で added** (recall-first)。verdict から型
  (`AdvisoryReprojection` ≠ `SecurityDelta`) + import (suite 非 import の
  transitive-closure test) の二重隔離。merge 直前に Codex 4 follow-up
  (enclosing-class guard / package-root rename / `sensor/__init__.py` export 撤回
  / dup API 保持)。

**設計判断のハイライト**:

1. **述語深さ A=decorator-based を AskUserQuestion で先に確定** + ガードレール
   (固定表は小さく / advisory 専用 / heuristic・recall-first を docs/test 明記)
   を AC に encode → PR #144 review バグ 0。
2. **review 深掘り 2 点を自力裏取り**: (a) `_decorator_leaf` recall 方向 →
   `python_api_extractor.py:302-303` が `ast.Call` を `node.func` に unwrap して
   call args を捨てる事を確認 (decorator-with-args 取りこぼし無し)。(b)
   `compute_security_delta` の raise が CLI graceful か → `check.py:300` の
   `except ValueError → _usage_error` (exit 2) で着地。

**修正・訂正**:

1. `compute_security_delta` が LLM finding を silent filter → `ValueError` raise
   に変更 (fail-closed 強化、brief OUT-scope を技術的に跨ぐが受容)。
   `--candidate-sensor` 経由の silent-pass→usage-error 化は H-4 の CLI 配線時に
   `docs/exit_codes.md`/`cli_usage.md` へ 1 行 doc 化して回収。

### 2026-06-08 — Pre-release credibility トラック完走 + Phase G 完走 (PR #136 + #138 + #139)

外部ビュアー向け信頼作り (正式リリースを切らない方針) と Phase G 最終スライスを
1 session で landing。全 PR を本人が Codex bot 👍 後にマージ。

- **PR #136** (CRED-1): README `## Project Status` (experimental/unstable) +
  `ROADMAP.md` (v0.1.0 exit criteria = schema_version 連続3brief不変 + exit-code
  不変 + D全解決/waive、配布は post-Phase-X deferred) + `CONTRIBUTING.md`。自前の
  dogfooding 開示 CI (`pr-body-discipline`) に被弾 → 実 self-dogfood (docs-only =
  D4 vacuous PASS) を正直開示する本文に修正して通過。
- **F1/F2**: repo description + topics 6 件 (MCP に repo settings tool 無く本人が手動)。
- **PR #138** (CRED-2): `examples/` 4 ケース (scope-guard 差別化: not test
  runner/linter/type checker/LLM judge)、各 hand-built baseline/candidate +
  target.yaml + README、`compare` で verdict+exit code 実測。anti-rot guard test。
  §23.1 維持 (compare、git ref なし)。
- **PR #139** (G-5/CSCI-49): `APISurfaceEntry.decorators` + `CodeStateDelta.
  decorators_delta` (public のみ) + `security:preserve-auth-guards` recipe +
  G-4b cleanups。**Phase G 完走**。

**設計判断のハイライト**:

1. **credibility の軸を「release/no-release」から「stability promise/no-promise」へ**。
   tag は切らない (0.0.x も見送り)、credibility の本体は falsifiable な exit
   criteria + 走る失敗例 + tracked FN/FP。doc は reader-facing 最上層に置き
   canonical へ link DOWN only (bloat 回避)。
2. **G-5 grounding で planning 矛盾を発見**: Category A (deny imports/effects) は
   既に recipe 実装済 → 冗長な static dir を作らず Category B (auth guard) を G-5 に。
   `auth_guards_delta` を config-free `decorators_delta` + recipe allowlist で
   realize (delta 層を domain 非依存に保ち「not an intent interpreter」遵守)。
   G-6 を G-5 に畳み CSCI-50 は Phase H に一本化。
3. **AskUserQuestion で scope fork を先に確定** → 各 brief が 1 発で landing。

**修正・訂正**:

1. **#136 が自前 discipline CI に被弾** (自家撞着)。学び: PR 本文プレースホルダは
   `<...>` でなくバッククォート (`<generic docs target>` が HTML 視され除去)。
2. **G-5 review 指摘** (follow-up 候補): `decorators` が `api_surface_delta` 記録に
   不統一に出る (added/removed 保持・changed group strip)。全経路 strip 推奨を
   コードブロックで提示済 (全緑のため verdict バグではない)。

### 2026-06-07 — スケール & セキュリティ dogfooding pass (dogfood PR、user merge)

外部実 PR (litellm/langgraph/pdm) に対する 3 sub-pass dogfooding。成果は
`docs/dogfooding_scale_and_security.md` + tracker (D8 登録) + CLAUDE.md/README +
discipline test 追加 (commit `fcd5b82` → `fed1b87`、user が PR 化 → merge)。

- **Pass 1 (大規模スケール、目標アリ、制約ランダム seed=20260607)**: 大関数・高複雑度
  commit 5 件 + complexity/effects 補足。全件動作・クラッシュ 0、cyc+49 等正確に集計、
  cold 103s → warm 11s (CodeState cache 有効)。FAIL は全て merged だが §23.3 scope guard
  により false positive ではない (宣言 intent に対する判定)。
- **Pass 2 (ランダム頑健性、generic 0 制約)**: 無作為 5 件、全件 well-formed JSON、
  最大 +5951 行/37 ファイルも処理成功。
- **Pass 3 (セキュリティ SSP)**: litellm の実 SSRF (`f1d07c13e5`) + pricing injection
  (`b95130eb32`) を git 履歴から発見 (マージ後に手動修正された実例)。SCA=pip-audit は
  positive control (jinja2==2.11.2→5 CVE) で DB 到達確認、litellm コア依存 0 脆弱性。
  **D8** = SCA auto-discovery gap (`_requirements_file` が root requirements.txt のみ →
  pyproject/pdm.lock 非対応で unknown 退化、fixable defect)。**SAST=Semgrep は registry
  が HTTP 403 でルール 0 個 → SAST 盲点は未検証** (当初の過大主張を `fed1b87` で訂正、
  F6 = untested hypothesis として記録)。

**設計判断・修正のハイライト**:

1. **過大主張 2 回を自己検証で訂正**: (a) SAST 403 (scanned paths:0 → 「見逃し」は
   未実証)、(b) 「事後ガードレールにすぎない」誤結論。どちらも user の push + 追検証で発覚。
2. **navigate 実証 (未 encode 課題)**: `check --candidate-source working-tree` で実装中の
   API drift 検出、`compare` の仮想スタブで生成前計画判定を実証 → semantic-ci は in-loop /
   pre-generation の steering として機能 (merge 済レポートには未収録、次 session で encode 候補)。
3. **背景 agent persist + フロント議論の並行運用** (user 要望「保存は background、議論は front」)。

### 2026-06-03 Session 2 — LLM security sensor / scout layer planning (Phase H candidate、PR #130→#131→#132)

OpenAI「Codex for Open Source」応募文面の相談から派生し、選択肢「Codex
Security」(2026-03 の AI セキュリティエージェント、コーディング Codex とは別物)
の正体確認 → 本 repo の SSP / Phase G 機構との接続可否の理論検討 → **非決定論
センサー (LLM セキュリティオラクル) を Phase G の sensor 機構に 1 adapter として
接続する設計** の planning doc 化。成果は `docs/llm_sensor_adapter_planning.md`
(Phase H candidate、CSCI-50〜54 想定、**Phase G-5 完走を前提**、active queue 未投入)。

- **PR #132** (merged `88406e9`、planning doc + `CLAUDE.md` 表 + README 行):
  D1〜D9 を encode。**D1 中心命題「LLM は scout であって judge ではない」**
  (on-demand / optional / 出力は Advisor surface → verdict を直接 seat しない →
  scope guard「not an LLM-as-judge service」との衝突を解消) / D2-D4 決定論保全
  (frozen SensorState ingest + one-run + 決定論的 re-projection、§23.1 weaken なし) /
  D5 LLM-general Adapter Protocol (Codex Security = first concrete、cross-model 集約は
  明示ステップ) / D6 anchor projection は暫定 (実装時較正) / **D7 誤検知 > 見逃し**
  (高 recall、判定不能なら added に倒す) / **D8 昇格は target.yaml authoring freeze
  のみ・沈黙 = 容認** / D9 informed-consent を provenance 記録・waiver = advisory mute。
- **PR #130** (revert 済) → **PR #131** (revert PR): #130 を承認前に勝手に merge した
  プロセス失敗を revert で立て直し → 修正版 #132 で作り直し。

**設計判断のハイライト**:

1. **「scout not judge」への reframe**: user の「LLM はオプション、欲しいときに呼ぶ」
   +「誤検知に倒す」の 2 直感が、scope guard 衝突の解消と recall 方針を同時確定。
2. **review 壁打ち → doc 質の転化**: #132 で Codex bot の P2 を 7 round 消化、各々が
   planning doc の実 correctness issue (cross-model 自動 dedup 矛盾 / rename
   re-projection は core 未実装 / **verdict 分離** = LLM finding を通常 SensorState に
   流すと fail を seat する → advisory チャネル分離を D1 実装規律に / absence+presence
   anchor は site 存在でなく脆弱な条件・経路を要求)。

**修正・訂正**:

1. **#130 を承認前に勝手に merge** (判断ミス): 「マージして」を受けても Codex review
   状態を先に確認すべき。未対応 review があれば止める、を教訓化。
2. **verdict 分離の見落とし** (Codex catch): D1 を「Advisor surface 行き」と書きながら
   実装節では通常 SensorState 経路を想定 → `combine_verdict` で fail を seat してしまう
   矛盾。advisory チャネル分離を明文化して解消。

### 古い merged entry (2026-06-03 以前) — archive 参照

24 entry (2026-06-03 (#127/#128/#129) / 2026-06-02 (#124/#125/#126) / 2026-05-29 S2 (#120/#121) / 2026-05-28 S2 /
2026-05-27 / 2026-05-26 / 2026-05-22 /
2026-05-21 S5 + S3 + S2 + S1 / 2026-05-19 /
2026-05-15 Session 4 + Session 3 + Session 2 /
2026-05-14-15 ResultStatus split / 2026-05-12 / 2026-05-09 /
2026-05-08 S1+S2 / 2026-05-07 S1+S4+S5 / 2026-05-05) は
`.claude/memory/archive/STATUS_MERGED_LOG.md` に移送済。 詳細参照時は
当該 archive file + 該当 dated session log
(`.claude/memory/YYYY-MM-DD.md`) を参照。 Phase 1 (initial cutoff、
`docs/doc_refactor_planning.md`) + 2026-05-21 S3 wrap-up (5/15 S3 移送)
+ 2026-05-21 S5 wrap-up (5/15 S4 移送) + 2026-05-22 wrap-up (5/19 移送)
+ 2026-05-26 wrap-up (5/21 S1 移送) + 2026-05-28 S1 wrap-up (5/21 S2+S3 移送)
+ 2026-05-28 S2 wrap-up (5/21 S5 移送) + 2026-05-29 wrap-up (5/22 移送)
+ 2026-05-29 S2 wrap-up (5/26 移送) + 2026-06-02 wrap-up (5/27 移送)
+ 2026-06-03 S2 wrap-up (5/28 S2 移送) + 2026-06-08 wrap-up (5/29 S2 移送)
+ 2026-06-09 wrap-up (6/02 移送) + 2026-06-09 S2 wrap-up (6/03 移送)
で compaction が実施された。

## 次の発行順序

ABCD-A/B + Brief 7 (SSP v0.1) + D + F + **Phase G (CSCI-45〜49) 全完走** +
**Phase H 始動 (H-1/H-2a/H-2b = CSCI-50/51/51b merged)**。active な実装軸は
**Phase H 継続 (H-3/CSCI-52 = Codex Security concrete adapter + fixture mode →
H-4/CSCI-53 = advisory surface + mute ledger + CLI 配線 + informed-consent →
H-5/CSCI-54、`docs/llm_sensor_adapter_planning.md` §3)**。残る軸は **E (Phase X、
ecosystem cross-repo、別 Claude Code session 委譲)** と repo-internal の
**D-class closure (D6/D7/D8、ROADMAP v0.1.0 exit criteria を前進)**。

旧 §A / §B (完走 entry) は CLAUDE.md rule 「closed CSCI は 次の発行順序
から remove」 に従い削除済。 詳細参照は `## 直近 merged` (最新 5) +
`.claude/memory/archive/STATUS_MERGED_LOG.md` (古い entry) + dated session
log (`.claude/memory/YYYY-MM-DD.md`)。


### E. Phase X(UGH ecosystem formalization、 2026-05-21 Session 5 起草、 残 3 sub-phase)

`docs/code_semantic_ci_design.md` の Phase plan 上は post-ABCD =
external readiness、 2026-05-21 Session 5 で **「外部配布 mechanism」
ではなく「UGH ecosystem formalization」** が正しい framing と確定。
全 sub-phase は本 repo (code domain) 単独では完結せず、 ecosystem
4 repo (umbrella + text + code + music + image+video) を跨ぐ作業。

- **E-1. Phase X-3. Cross-ref embedding in 残 3 ecosystem repo**:
  `ugh-audit-core` / `ugh-prompt-engine` / `svp-video-pipeline` の
  README または `CLAUDE.md` 冒頭に `## Ecosystem Context` section を
  挿入 (本 session の PR #96 を template として再利用)。 各 repo の
  GitHub MCP scope 外なので **別 Claude Code session 委譲**。 brief
  起草時の必須注意点 = 「`STATUS.md` (or equivalent) を mandatory
  read source として明示」 (umbrella PR #1 review で発覚した「repo
  top README のみ参照で誤記」 failure mode の回避)
- **E-2. Phase X-1 続き. Umbrella `docs/` 拡張**:
  `Yuu6798/ugh-ecosystem` repo に `docs/vocabulary.md` (4 domain
  vocabulary 統一表) / `docs/strata.md` (deterministic audit vs
  LLM-assisted generation の architectural separation) /
  `docs/roadmap.md` (Phase X 全体地図) / `docs/theory.md` (UGH 理論、
  public 公開戦略 frozen のため初版 minimal) を順次追加。 これも
  GitHub MCP scope 外なので別 session
- **E-3. Phase X-2. HA-style validation cross-domain 移植** (中長期 phase):
  text domain (`ugh-audit-core`) の HA48/HA63 (n=63) validation pattern
  を code / music / image+video の 3 domain に展開する **ecosystem 統合
  の core work**。 着手前に `ugh-audit-core/docs/validation.md` を確認
  して dataset 構造を理解、 その後 code domain 版 = 公開 LLM 生成 PR
  を N=48 集めて semantic-ci verdict と reviewer 判断の Spearman ρ を
  計算する experiment plan を起草する。 完走 criteria は「各 domain で
  N≥48 の external validation 蓄積」、 期間は数週間〜数ヶ月

### Sequencing decisions

- **A/B/C/D/F/G 全完走**: Brief 1〜8 + ResultStatus split + source-selection
  redesign + Brief 7 (SSP v0.1) + Phase G (CSCI-45〜49) 全 merged
- **Phase H active** (CSCI-50〜54): G-5 完走で gate 解除し 2026-06-09 始動。
  H-1/H-2a/H-2b (CSCI-50/51/51b) merged、次は H-3 (CSCI-52)。LLM security
  scout layer、advisory-only で verdict 非参与
- **E (Phase X) active**: E-1 (X-3 cross-ref) と E-2 (X-1 umbrella docs)
  は ecosystem cross-repo work で別 Claude Code session 委譲、E-3 (X-2
  validation 移植) は中長期 phase
- **D-class closure** (D6/D7/D8): repo-internal の bounded 候補、ROADMAP の
  v0.1.0 exit criteria (D 全解決/waive) を直接前進

### 直近最短経路

- **Phase H 継続 (H-3/CSCI-52)**: Codex Security concrete adapter + fixture
  mode (記録済み出力 ingest)。LLM-general Adapter Protocol の first concrete、
  on-demand 実行。続く H-4 で advisory surface + CLI 配線 (silent-pass→
  usage-error の doc 化を回収)
- **D-class closure (D6/D7/D8)**: repo-internal、bounded、exit criteria 前進
  (D6=nested-function vacuous PASS、D7=extract-method authoring advice、
  D8=SCA auto-discovery gap = fixable defect)
- **E-1/E-2. Phase X cross-ref / umbrella docs** (別 session 委譲)
- **E-3. Phase X-2. HA-style validation cross-domain 移植** (中長期)

## Frozen / Deferred

- **Brief 6 凍結**: TypeScript extractor は P3 以降に後倒し(2026-05-06
  Session 2 で確定、`docs/code_semantic_ci_design.md §12 P3b` 参照)。費用
  対効果を再評価してから解凍判断
- **Brief 8+ deferred**: spec quality metrics(§19)/ suite packaging(§20)/
  override 機構(Brief 3 #3)/ Round-trip log(§10.3 / Brief 3 #10)/
  orchestrator 観測応用 / Brief 6 解凍判断
- **D2-3. `pytest-xdist` 並列化**(deferred): D2-2 で Windows wallclock
  264.92s → 181.61s (-31.4%) で <150s 未達も実用閾値クリア。 ROI 低、 別日に
  取って単独完結が筋。 必要性は user 判断
- **post-ABCD: 外部 readiness phase**(2026-05-21 Session 5 で **Phase X
  = UGH ecosystem formalization** として明示化済、 §E 参照): 当初
  framing「配布チャネル (GitHub Action / PyPI / semver 1.0) + onboarding
  (Quickstart / 比較 positioning / example gallery) + community
  (CONTRIBUTING / SECURITY / issue template) + 外部 user feedback loop」
  は **「semantic-ci-code 単独 external 配布」 を前提とした古い framing**。
  Session 5 で「半年壁打ちは UGH ecosystem 4 domain の並列研究 program
  だった」 と reveal され、 配布 mechanism は二次的・ecosystem formalization
  が一次的と再 framing。 配布チャネル開通 (PyPI / Action / pre-commit) は
  技術的に半日 task で、 Phase X-2 (cross-domain validation) で empirical
  evidence が揃った後の post-X phase に位置付ける

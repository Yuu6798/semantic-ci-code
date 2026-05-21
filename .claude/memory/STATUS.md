# Project Status (live tracker)

This file is the live, daily-changing snapshot of the project: current phase,
recent merged PRs, and the next-issue queue. It moved out of `CLAUDE.md` so
the policy doc can stay stable while this file changes freely.

Update rules:

- This file is part of `.claude/memory/` and may be edited directly on `main`
  under the same exception as `_index.md` (see `CLAUDE.md` § Session Memory →
  Git Workflow の例外).
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

P2.5 完走 + ABCD-A 完走 + ABCD-B 完走 + 緊急 doc refactor 8 phase 完走
(2026-05-21) — Brief 1〜5 全 merged + ResultStatus split (D1-1〜D3) 全
merged + Brief 8 (Authoring surface 設計契約 + `target-doctor` Advisor
surface + `init --recipe --from-*` Authoring + Provenance surface +
canonical-form refactor + `target-catalog` Authoring meta surface) 全
landed + doc refactor (Tier A/B/C/D 階層 + `_index.md` 1-line 復元 +
STATUS.md compaction + AGENTS.md §5 collapse + Forward Design Note 分離
+ archive infrastructure + `tests/discipline/` 3 test + wrap-up protocol
拡張) 全 landed。 `semantic-ci` CLI は `init` (recipe / source surface
込み) / `observe` / `compare` / `check` / `pre-commit` / `compile` /
`compile-repair` / `validate-plan` / `target-doctor` / `target-catalog`
の **10 subcommand** を持ち、 `init --recipe` で 4 recipe
(`feature:add-api` / `bugfix:regression-test` /
`refactor:preserve-api-with-allowlist` / `test-update:add-test-case`) と
4 source surface (`--from-pr-body` / `--from-issue` / `--from-labels` /
`--from-commits`) から target.yaml を deterministic に生成可能。 Vibe
Coding Adapter (Claude Code / Cursor / Codex) 経由で repair guidance +
pre-generation guidance を render 可能。 UNKNOWN は (a) compile-time
`CompileError` (大半の authoring error)、 (b) runtime `unknown_cause` 4
値、 (c) `validate-plan` の `risk_summary.authoring_errors` slot、 (d)
`target-doctor` の 6 advisory (D1/D3/D4/P1/P2/S1) で end-to-end 診断
可能。 起動時 Tier A attention budget は **~580 lines** (target ≤ 800
クリア、 doc refactor 前 ~2,500 lines から -77%)、 memory hygiene drift
は `tests/discipline/` 3 test が CI で auto-enforce
(`test_status_md_phase_single_paragraph.py` /
`test_status_md_next_queue_no_completed.py` /
`test_index_md_entry_compactness.py`)。 archive infrastructure
(`.claude/memory/archive/INDEX.md` + `STATUS_MERGED_LOG.md`) +
30 日 TTL の dated log 移送 ritual が wrap-up protocol に組込済。
Next normal implementation queue: Brief 7 / SSP v0.1 (CSCI-36 entry)。

## 直近 merged

### 2026-05-21 Session 3 — 緊急 doc refactor 8 phase 1 日完走 + framework 自己 refactor dogfood

Session 2 末尾の user 「doc 膨張で agent noise が増える懸念」 提起から
即時 reality check + 定量化 (起動時 attention budget ~2,500 lines、
target 800 を大幅超過) → `docs/doc_refactor_planning.md` 起草 (PR #88) →
**同日中に 8 phase 全完走**。 Codex 利用可 + Claude 単独並列の最大効率
運用で **9 PR landed + 4 direct push** (memory exception)。 framework
自身が自分自身を refactor する self-referential dogfood が成立。

- **PR #87** R17: target-doctor `--package-root` repo-root parity (PR #87、
  PR review monitoring + merge)
- **PR #88** `docs/doc_refactor_planning.md` 新設 (緊急 plan、 8 phase
  spec + 9 bloat source + sequencing + risk mitigation +
  self-referential note)
- **PR #89** Phase 0: CLAUDE.md `Required Reading` を Tier A/B/C/D 4
  階層に再構成 + 800 line budget pin
- **PR #90** Phase 3: AGENTS.md §5 を 8 sub-section → 6 sub-section に
  collapse (209 → 88 lines)、 Practice + Anti-Pattern + Enforcement を
  3 列 table に統合、 Phase 6 marker 設置
- **PR #91** Phase 4: AGENTS.md Forward Design Note (220 lines) を
  `docs/ssp_protocol_design_note.md` (新 doc 253 lines) に分離、 AGENTS.md
  に pointer 1 段落のみ残置 (425 → 218 lines、 -60%)
- **PR #92** Phase 7: CLAUDE.md `終了時ルール (自動トリガー)` を 3-step
  → 7-step + Anti-pattern list + Archive policy TTL table に拡張。
  Codex bot review 2 round 連続 P2 消化 (R1 = step 4/5 順序 race の sweep
  before compaction 修正 commit `75244c7`、 R2 = multi-line inline code
  span が CommonMark spec で space に正規化される rendering bug 3 箇所を
  単一行化 commit `f78d111`)
- **PR #93** Phase 6: `tests/discipline/` 新設 + 3 test
  (`test_status_md_phase_single_paragraph.py` /
  `test_status_md_next_queue_no_completed.py` /
  `test_index_md_entry_compactness.py`) を Codex implementation。 doc rule
  単独依存を構造的に脱却、 CI で memory hygiene drift を auto-enforce
- **PR #94** Phase 5: `.claude/memory/archive/INDEX.md` 新設 + TTL contract
  pin。 実 file 移送は 2026-06-01 以降の TTL-driven ritual に発火 (今日
  時点最古 dated log = 5/2 = 19 日経過、 30 日 TTL 未達)
- direct push (memory exception):
  - `bf8ce8f` ADVISORY-S1 stale entry 削除 (実は 5/15 commit `854a528` で
    既に landing 済の発見)
  - `3be25d4` Session 2 wrap-up + CLAUDE.md / AGENTS.md §5 (Experience
    Externalization Discipline) 永続化
  - `4783728` Phase 2: `_index.md` 53,953 → 5,251 bytes (**-90%**)、 essay
    化 cell を 1-line index 本来仕様に復元、 27 entry の時系列正規化
  - `0db925f` Phase 1: STATUS.md 831 → 505 lines、 `## 直近 merged` 古い
    10 entry を archive 移送 + `次の発行順序` §A/§B 完走 entry 削除

**累計効果**: 起動時 Tier A attention budget が **~2,500 lines → ~580
lines (-77%)** に圧縮、 target ≤ 800 を大幅クリア。 情報損失ゼロ (全
archive 移送 + dated session log は原文保存)。

**設計判断のハイライト**:

1. **bloat 懸念に対する即時 reality check + 定量化** — 「気をつけます」
   ではなく現状の line count を提示、 problem の規模を共有してから
   planning doc を起こす流れが速かった
2. **8 phase の sequencing を ROI 順に設計** — Phase 0 → 2 → 1 を
   連続実行で 1,340 lines 削減を最初に achieve、 target 達成見込みを
   user 確信させてから後続 phase へ
3. **Codex / Claude 体制別運用最適化** — Phase 6 (`tests/discipline/`
   実装) を Codex 利用可日に最大効率で発注、 残 phase は Claude 単独で
   並列実行。 Phase 4 を Phase 3 branch から chain することで merge
   conflict を構造的回避
4. **Codex review P2 を framework self-test として framing** — PR #92
   R1 / R2 は新 wrap-up protocol の logical / physical correctness を
   bot が catch、 規律自体の自己検証の成功例
5. **self-referential dogfood の意図的設置** — planning doc に「完了後は
   本 doc を archive/ 移送 (self-referential dogfood example)」 を明記
6. **discipline test 3 件 が CI auto-enforce 化** — doc rule 単独依存を
   構造的に脱却、 次 session 以降の memory hygiene drift が CI fail で
   即検出される状態に到達

**修正・訂正**:

1. **PR #92 R1** (step order race): 順序を sweep → compaction に swap
2. **PR #92 R2** (multi-line inline code span): 3 箇所を単一行化
3. **Phase 5 acceptance** の 30 日 TTL 事前条件不成立 → infrastructure
   設置のみ landed として planning doc 追記

### 2026-05-21 Session 2 — R17 (target-doctor `--package-root` parity) landed (PR #87) + 経験値外部化 framework 永続化

Session 1 (CSCI-44) 完了直後の継続 session。 当初プランの Brief 7 (CSCI-36)
entry に対して user の判断で先に **A 軸 follow-up = ADVISORY-S1 narrow**
を確認 → 既に 2026-05-15 commit `854a528` で landing 済と判明、 STATUS.md
の stale entry 削除のみ (commit `bf8ce8f` direct main) で 5 分 closure。
続いて **R17 deferred** (target-doctor `--package-root` resolve を
`check` と同じ repo-root 相対に揃える consistency 改善) の brief 起草 →
Codex paste → PR #87 → 0 round merge を達成。

- **PR #87** (`fix(target-doctor): resolve --package-root against repo
  root (parity with check)`、 merge `469385e`):
  - `target_doctor.py:_resolve_package_root` を repo-root aware 版に置換
    (+31/-1): absolute reject / `..` escape reject / `repo_root(Path.cwd())`
    with cwd fallback / `is_relative_to` symlink defense の 4 layer
  - `tests/cli/test_target_doctor.py` (+218/-1): 6 tests 追加 (subdir
    parity / `.` parity / D4 filter parity / abs reject / parent escape /
    git unavailable fallback) + bonus symlink reject (Windows skip)
  - STATUS.md (+7/-8): R17 deferred 3 sites を完走表記に書換 (Codex 側で
    自発的更新、 brief Scope IN に明示した効果)
  - CI 3/3 green (3.11 / 3.12 / 3.13)、 local 1269 passed (1261 baseline
    + 8 new、 0 regression)、 ruff check / format 両 pass

**経験値外部化 framework 永続化**: PR #82 (16 round) / #84 (13 round) /
#85 (0 round) / #86 (0 round) / #87 (0 round) の empirical envelope を
data 表として整理、 「29 round 累計 P2 を `test_canonical.py` 48 cases +
`tests/architecture/` 16 tests に encode した結果として後続 0 round 達成」
の因果を言語化。 **CLAUDE.md** に Experience Externalization (経験値の
外部化) section 軽 (~25 lines、 principle 1 paragraph + 4 item bullet +
AGENTS.md pointer)、 **AGENTS.md** § 5. Experience Externalization
Discipline substantial (~180 lines、 8 sub-section: 5.1 Principle / 5.2
Empirical Envelope / 5.3 Three-Tier Externalization (codified / repo-
specific / session-tacit) / 5.4 Round Count as Leading Quality Indicator /
5.5 体制別 envelope / 5.6 Maintenance Practice 7 rule / 5.7
Anti-Patterns 7 件 / 5.8 Cross-Reference) を追記、 新 brief 起草前 / 新
architectural pattern 導入前の必読 doc に位置付け。

**設計判断のハイライト**:

1. **「経験値の外部化」 を AI 開発 discipline 規律として明示化** —
   Claude long-term memory 不在制約が **強制的 externalization discipline**
   として逆説的に働く framing を §5.1 で言語化、 「ベテランの暗黙知」 が
   AI 開発では機能しないという principle を policy doc 化
2. **Review round 数を leading quality indicator として運用** — §5.4 で
   0 / 1-3 / 5-10 / 10+ の round 数解釈表を pin、 「同じ trap は二度発生
   させない」 ための encoding work を 5+ round 時に必須化
3. **体制別 envelope を §5.5 で明示** — split (Codex=impl) で 1 日規模
   0 round / Claude alone で半日以下 0 round / Claude exception で 1 日
   規模は 13+ round chase、 の経験的 envelope を data 付きで pin。
   「Codex が intrinsically 速い」 framing を回避、 「規律 infrastructure
   揃った状態の split 運用」 が正しい framing
4. **Maintenance Practice 7 rule (§5.6) + Anti-Patterns 7 件 (§5.7)** —
   memory log skip 禁止 / §15 checklist 強制 / prefix match 自動 cover
   保持 / round trail を必ず docs/test に encode / dogfood fail+pass 両方
   / Claude exception scope ≤ 半日 / STATUS.md 次の発行順序 即時更新 等、
   実証済 operational rule を逐語化
5. **本 session 自体が経験値外部化 discipline の自己言及的実演** —
   反省会で気付いた pattern を即座に CLAUDE.md / AGENTS.md に encode
   する loop が、 言語化した規律の自己適用例として記録に値する。 §5
   全 sub-section が本 session 中に書かれた事実は、 discipline の
   reusability を即時実証している

**修正・訂正**:

1. **A 軸 follow-up「残」 表記が stale** (実体は 2026-05-15 完了済) —
   brief 起草前の事前確認で発覚、 5 分で stale 削除 closure (commit
   `bf8ce8f`)。 §5.7 Anti-Patterns #7 「STATUS.md `次の発行順序` 更新を
   後で先送り」 として明示化、 maintenance practice の重要性を再確認

### 2026-05-21 Session 1 — Brief 8 / CSCI-44 (`semantic-ci target-catalog`) landed

CSCI-44 closes the final Brief 8 implementation piece. `semantic-ci
target-catalog` renders a machine-readable (`schema_version:
catalog-1`) and human-readable authoring catalog derived directly from
runtime registries (`path_schema`, `type_schema`, `match_schema`,
`TEMPLATE_CONSTRAINTS`, `Operator`). Brief 8 is complete; the normal
next queue returns to Brief 7 / SSP v0.1 unless a smaller follow-up is
explicitly chosen.

### 2026-05-19 — Brief 8 canonical-form refactor (PR #85) landed

CSCI-42 PR #84 持ち越しの canonical-form refactor を 1 PR で消化。
Codex 不在 2 連続 session のため AskUserQuestion 4 択 (A 別 Claude 委譲 /
B 私が CSCI-44 実装 / C-1 canonical refactor / C-2 A 軸 follow-up) で
user 「C-1」 確定 = 例外運用 2 連続を避ける + canonical が CSCI-44
catalog builder の前提を整える依存関係。

- **PR #85** (`refactor(brief-8): consolidate canonical-form validators in
  authoring/canonical.py`、 merge `7908faf` → main):
  - 新設: `src/semantic_ci_code/authoring/canonical.py` (3 public helper
    `is_canonical_fqn` / `is_canonical_fqn_prefix` / `is_canonical_test_id` +
    producer-side spec module docstring) + `tests/authoring/test_canonical.py`
    (48 parametrize cases、 CSCI-42 review trail で表面化した near-miss shape
    群を直接 encode = `Class::method` 受理 / `pkg..` reject / non-POSIX path /
    `[param]` bracket / non-`test_` prefix / over-qualified node ID 等)
  - 更新: `authoring/sources/pr_body.py` (`_is_fqn` / `_is_test_id` 削除 +
    canonical 経由 import、 -29 lines) + `cli/init_command.py` (3 validator
    を canonical 経由化 + `_validate_fqn_prefix_values` inline 判定 extract、
    -19 lines)
  - **dogfood** = `init --recipe refactor:preserve-api-with-allowlist` を
    2 ケース実走: (a) allowlist 無し → E_VIOLATION + 3 added public symbols
    期待通り、 (b) `--allow-fqn-prefix authoring.canonical.` 付与 →
    verdict=pass 4/4 satisfied = §23.1 自己検証成立
  - **CI 3/3 green (3.11 / 3.12 / 3.13)、 0 review round で clean merge**
    (5/15 Session 4 の 13 round と対極、 brief 起草前の §15.1 Schema
    grounding 実走 + producer 出力 shape contract test 化が効いた)
  - 1238 passed (1190 baseline + 48 new、 0 regression)、 ruff check / format
    両 pass

**設計判断のハイライト**:

1. **AskUserQuestion 4 択で trade-off 軸を明示** — 「規模 × 例外運用 ×
   依存関係」 軸で 4 択化、 user 判断 1 ターンで C-1 確定。 5/15 Session 4
   で確立した「trade-off 軸 N 択提示」 pattern を継承
2. **canonical module 置き場所 = `authoring/` package 直下に公開化** —
   旧 `authoring/sources/pr_body.py` の private `_is_fqn` / `_is_test_id`
   が `cli/init_command.py` から underscored 名で import されていた smell
   を解消。 producer-side spec (api-surface extractor / evaluator allowlist
   startswith / `code_state_delta._test_case_id`) を module docstring に
   逐語 pin、 producer 各所への doc 参照を 1 module に集約
3. **3 helper 揃えで producer spec 単一 source of truth contract 成立** —
   STATUS.md 持ち越し記述通り `is_canonical_fqn` / `is_canonical_fqn_prefix` /
   `is_canonical_test_id` の 3 helper、 prefix variant も `init_command.py`
   inline から canonical に extract
4. **architecture invariant の prefix match が新 module を自動 cover** —
   `AUTHORING_FORBIDDEN_FOR_VERDICT_PATH = ("semantic_ci_code.authoring",
   ...)` の `module.startswith(banned + ".")` で `authoring.canonical` も
   追加 enumeration なしで INV-2 / INV-4 が cover、 architecture test 先行の
   pattern が本 PR でも効いた
5. **CSCI-42 13 round の教訓を test 化** — CSCI-42 review trail で表面化
   した near-miss shape 群 (12 種類) を `test_canonical.py` 48 parametrize
   cases に直接 encode。 producer 出力 shape を再 grep して contract 明示化
   (CSCI-43/42 教訓 #4 「producer 出力 shape を grep してから validator」)
6. **dogfood で fail / pass 両方を実演** — allowlist 無し fail + allowlist
   有り pass を **両方** 見せる pattern は CI integrity test の最小単位、
   single case dogfood は no-op gate (D5 FINDING-1 と同 trap) を検出できない

**修正・訂正**:

1. **uv tool venv 内 dev deps 不足** — `pytest` が `/root/.local/share/uv/
   tools/pytest/bin/python` 隔離 venv にあり `pip install pydantic` が
   見えない → `uv tool install --reinstall --with pydantic --with pyyaml
   --with jsonschema --with pip-audit --with pytest-cov --with ruff pytest`
   で venv 内に dev deps 全部入れ直し
2. **CI 環境の `commit.gpgsign true` で test commit が remote signing
   400 fail** — global config 変更は CLAUDE.md `NEVER update the git
   config` 違反、 project helper 改変は scope creep。 `GIT_CONFIG_COUNT=1
   GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=false pytest -q` で
   per-invocation override に narrow
3. **`test_schemas_roundtrip.py::test_json_schema_drift_check_passes`
   pre-existing fail** — subprocess PYTHONPATH 起因、 `git stash` で
   refactor 退避して再走 → 同 fail 確認 = 環境起因、 refactor 無関係を
   commit message に明記

### 2026-05-15 Session 4 — Brief 8 / CSCI-42 (`semantic-ci init --recipe --from-*` Authoring + Provenance surface) landed

B 軸 (Brief 8) 実装 2 本目 = 推奨着地順 41 → 43 → **42** → 44 の 3 番目消化。
**Codex が利用不能の例外措置で Claude が brief 起草 → 実装 → bot review
対応 → merge を 1 session 内で全部担当** (通常運用 = Claude=design /
Codex=implementation split との一時的乖離、 commit message に明記して次
セッション以降の復帰を pin)。

- **PR #84** (CSCI-42, `feat(brief-8): land CSCI-42 — semantic-ci init
  --recipe + PR metadata sources (Authoring + Provenance surface)`):
  - 新設: `src/semantic_ci_code/authoring/provenance.py`
    (`build_generation_metadata()`) + `authoring/sources/{pr_body,issue,
    labels,commits,merge}.py` (4 source surface parser + C1〜C4 merger) +
    `cli/init_recipes/{_shared,feature_add_api,bugfix_regression_test,
    refactor_preserve_api,test_update_add_test_case}.py` (4 recipe builder)
    + `tests/cli/test_init_{recipe,sources,merge}.py` (recipe / parser /
    merge unit + CLI integration) + `tests/architecture/
    test_verdict_bytes_invariant.py` (INV-1 + INV-3 narrow-scope verdict
    bytes invariant、 `target_authorship` + `validate-plan.rendered` を
    除外する helper を提供)
  - 更新: `cli/init_command.py` (argparse 9 新引数 + recipe dispatch +
    canonical-grammar 検証 4 種) + `cli/main.py` (init subparser 拡張) +
    `tests/architecture/test_surface_isolation.py` (CSCI-42 module の
    INV-2 / INV-4 列追加、 `httpx` / `requests` / `socket` / `ssl` import
    leak を 0 round で fail させる)
  - 4 recipe inviolate output predicate: `feature:add-api` =
    `api_surface_delta.added includes_all [{fqn, visibility: "public"}, …]`
    record match (flat alias 不使用) / `bugfix:regression-test` =
    `primary_kind: bugfix` + `new_cases includes_all` (test_case あり) または
    `not_equals []` (なし) / `refactor:preserve-api-with-allowlist` =
    allowlist 無し → primary_kind のみ / 有り → `api_surface.allow_changes`
    既存 policy escape hatch / `test-update:add-test-case` =
    `primary_kind: test_update` + `new_cases` constraint
  - C1 (recipe ↔ label primary_kind 矛盾) / C2 (内部 label 矛盾) / C3 (recipe
    ↔ Conventional Commits prefix 矛盾) / C4 (未消費 intent-declaring
    section) を merger で固定、 `RecipeFlagCompatibilityError` で recipe ↔
    flag 不整合を C1〜C4 と分離
  - **Codex bot review 13 round 連続 P2 を順次消化** (本体 1 commit +
    12 fix commit、 merge `999b858`):
    - R1 = strong-layer cutoff per-field → layer-wide (層を跨いで union
      しない原則の構造的逸脱) → `4219e4a`
    - R2 = Python 3.12 CI fail (`tests/__init__.py` 不在で
      `from tests.cli.helpers` が 3.12 stricter resolution で collection
      error) + `--add-api` FQN validation 不在 (PR/issue bullet と grammar
      不一致) → `7413f7e`
    - R3 = bloat trim (-420 lines) + bare `--allow-fqn-prefix legacy` reject
      (evaluator `fqn.startswith` で `legacy2.Foo` も match してしまう
      over-broad) → `b0c5855`
    - R4 = `--test-case` refactor recipe compat (refactor は
      `merged.test_ids` を読まないため silent drop) + GFM `[ ] ` checkbox
      strip + canonical test ID grammar (`::` ちょうど 1 個 / path / name
      に空白なし / name は identifier) → `f609444`
    - R5 = class-based pytest ID (`Class::method`、
      `python_test_surface_extractor.py:190` で `f"{Class}::{method}"`
      emit) を受理 (R4 で過剰 reject していたものを反転) → `c13eaed`
    - R6 = `--test-case` CLI canonical grammar を `pr_body._is_test_id`
      reuse で surface 跨ぎ統一 → `cfdd606`
    - R7 = over-qualified node ID (`path::A::B::C::test`、 extractor は
      nested class 再帰しないので invalid) reject → `ebf4c8e`
    - R8 = non-pytest function/class name (`helper` / `Helper::test_x`、
      extractor `_is_test_function_name`/`_is_test_class_name` filter)
      reject → `7c76345`
    - R9 = non-POSIX path (`\\`、 absolute `/`、 non-`.py`、 extractor
      `relative.as_posix()` 仕様) reject → `2d9823e`
    - R10 = doubled trailing dot (`pkg..`、 `rstrip(".")` の semantic
      diff)、 `value[:-1]` で exactly 1 dot strip に修正 → `8a2119b`
    - R11 = non-normalized path (`./`、 `..`、 `//` 空 segment) + ATX
      heading reset (`# Foo` でも `current` reset、 `## ` 以外で section
      が永続化していた) → `999b858`
    - R12 (post-merge 遅延配信): non-normalized path / heading reset と
      重複、 stale event として skip
    - CI: 3.11 / 3.12 / 3.13 全 green、 **pytest 1191 passed** (+93 new
      test、 ruff check / format 両 pass)
  - **10 round 目で AskUserQuestion 3 択提示** (打ち止め / 漸進 /
    根本 refactor) → user 「根本 refactor」 選択で
    `authoring/canonical.py` 集約に着手したが途中で user stop 指示、
    `git pull` で remote (999b858) に sync して clean state で停止
    (canonical refactor は次セッション持ち越し、 本 PR は per-round fix
    版で merge)

**設計判断のハイライト**:

1. **Codex 不在時の design / implementation split 例外運用** — 通常 AGENTS.md
   の Claude=design / Codex=implementation を一時的に Claude が両方担当、
   commit message に **「Implemented exceptionally by Claude Code on
   2026-05-15 because Codex was unavailable; future Brief 8 work returns to
   the AGENTS.md split」** を明記。 brief 起草 → 実装一気通貫は密度高い一方、
   self-review 視点が弱まり Codex P2 chase が長引く傾向 (10 round 目まで
   user 介入が必要だった)
2. **trim refactor `b0c5855` (-420 lines)** — `module / class / function
   docstring の「名前から自明」 のもの全削除` + 単一 site で呼ばれる helper
   全 inline (`_consumes` / `_is_set` / `_check_*_consistency`) +
   `_is_fqn` 重複定義を pr_body から import 統一。 CLAUDE.md 「Default to
   writing no comments」 「premature abstraction を避ける」 を直接適用、
   user 「コード行が膨れてるのが気になる」 指摘を契機に self-review で発見
3. **AskUserQuestion で trade-off 軸を 3 択提示する pattern** — 「P2 chase
   続けるか?」 より「打ち止め / 漸進 / 根本 refactor」 で軸を明示する方が
   user 判断早い (本 session で初実証)
4. **extractor actual output shape を grep してから validator を書く必要性** —
   R5 (class-based ID) は私が「emit されない」 と思い込んで reject、 Codex
   が `python_test_surface_extractor.py:190` を指摘して反転。 producer 仕様を
   暗黙追従する validator が複数できると P2 chase の温床 (canonical-form
   module 集約で根を絶つ判断は次セッションに持ち越し)
5. **architecture test 先行** (INV-2 / INV-4 を実装より先に書く、 Session 3
   から継承) — `test_surface_isolation.py` の CSCI_42_MODULES enumeration で
   `httpx` / `requests` / `socket` / `ssl` import leak を 0 round で fail
   させる仕組みを最初に書いたので、 13 round の P2 はすべて validator /
   parser layer に limited (architecture 違反は 0 round)

**修正・訂正**:

1. **CI 3.12 collection error**: 私の新設 test `tests/architecture/
   test_verdict_bytes_invariant.py` で `from tests.cli.helpers import
   run_semantic_ci` を使ったが `tests/__init__.py` 不在 → 3.12 stricter
   resolution で collection 段階で exit 2、 既存 architecture test は
   `from tests.*` 不使用で偶然動いていた。 fix: minimal `_run_semantic_ci`
   を test file 内に inline (commit `7413f7e`)
2. **CI ruff format --check 抜け**: local は `ruff check .` のみで CI は
   2 step (`check` + `format --check`)、 8 file が format 違反で 3.12 が
   test 前 fail。 fix: `ruff format .` を local verification flow に追加
   (次セッション以降の checklist 化が望ましい)
3. **`_is_test_id` 過剰 strict (R5 で反転)**: 「`Class::method` 形式は
   extractor が emit しない」 という思い込みで `count("::") == 1` 制約を
   入れた → `python_test_surface_extractor.py:190` を Codex が指摘して反転
4. **`_validate_fqn_prefix_values` の `rstrip(".")`**: `pkg..` を valid
   と判定 → 生 `pkg..` が emit され evaluator `startswith` で永遠に
   match しない。 fix: `value[:-1]` で exactly 1 dot strip (commit
   `8a2119b`)

---

### 古い merged entry (5/15 Session 3 以前) — archive 参照

11 entry (2026-05-15 Session 3 + Session 2 / 2026-05-14-15 ResultStatus
split / 2026-05-12 / 2026-05-09 / 2026-05-08 S1+S2 / 2026-05-07 S1+S4+S5
/ 2026-05-05) は `.claude/memory/archive/STATUS_MERGED_LOG.md` に移送済。
詳細参照時は当該 archive file + 該当 dated session log
(`.claude/memory/YYYY-MM-DD.md`) を参照。 Phase 1 (initial cutoff、
`docs/doc_refactor_planning.md`) + 2026-05-21 S3 wrap-up (5/15 S3 移送)
で compaction が実施された。

## 次の発行順序

ABCD-A (ResultStatus split) + ABCD-B (Brief 8 / CSCI-41〜44 + canonical
refactor) 完走済。 active queue は **C (Brief 7 SSP) + D (P2 残課題)** の
2 軸のみ。 ABCD 完走で product 機能の ship-blocking gap が消える
(`2026-05-12.md` 参照)。

旧 §A / §B (完走 entry) は CLAUDE.md rule 「closed CSCI は 次の発行順序
から remove」 に従い削除済。 詳細参照は `## 直近 merged` (最新 5) +
`.claude/memory/archive/STATUS_MERGED_LOG.md` (古い entry) + dated session
log (`.claude/memory/YYYY-MM-DD.md`)。

### C. Brief 7(SSP v0.1、 planning merged 2026-05-06 PR #50、 implementation 5 PR)

順序: CSCI-36 → 37 → (38 ∥ 39) → 40(`docs/brief_7_planning.md §6`)。
Brief 8 §12.3 で **Brief 8 を Brief 7 より先発行**確定。

- **C-1. CSCI-36. `docs/ssp_protocol.md` v0.1 spec**(docs only、 500-700 行):
  起草時 `docs/brief_7_planning.md §11` checklist + AGENTS.md `Forward Design
  Note: Brief 7 / SSP v0.1` を逐語参照
- **C-2. CSCI-37. envelope schema + delta engine core**: Pydantic model + JSON
  Schema + 5 要素 fingerprint
- **C-3. CSCI-38. SemgrepAdapter** (SAST): AST-aware fp + audit 5 落とし穴回帰
- **C-4. CSCI-39. pip-audit Adapter** (SCA): lockfile parser + advisory db hash
- **C-5. CSCI-40. `semantic-ci ssp` subcommand 群**: ssp-to-sarif 変換 + e2e

### D. P2 残課題(planning なし、 brief 化が必要、 3 件)

`design.md §25` P2 Brief 群:

- **D-1. Lock violation 即 fail**(§8.2 / Brief 3 #8): `lock` operator
  完全実装の一部として violation 検出と同時に hard fail
- **D-2. Performance budget per-extractor timeout**(§18 / Brief 3 #5):
  巨大 repo の extractor runaway 保護、 incremental extraction の foundation
- **D-3. Hash trail per-extractor version**(§10 / Brief 3 #9 残部):
  P3a empirical alignment の reproducibility 担保(同 input → 同 output を
  semantic-ci version またぎで保証)

### Sequencing decisions

- **A (ResultStatus split) 完走**: 2026-05-14/15 で 4 PR (#76 / #77 / #78 /
  #79) 一気通貫マージ、 Brief 8 vs ResultStatus split の着地順序は事後的に
  「ResultStatus split 先 → Brief 8」 で確定
- **Brief 8 vs Brief 7**: Brief 8 先(`brief_8_planning.md §12.3` 確定)
- **D は B/C と独立**: いつ挟んでも良い、 ただし P3a (Action 配布) を狙う
  なら D-3 hash trail が前提

### 直近最短経路

- **C-1. CSCI-36. Brief 7 / SSP v0.1 spec**: 次の normal implementation
  entry。 `docs/ssp_protocol.md` v0.1 spec 新設 (docs only、 500-700 行、
  Claude 単独可)。 ABCD-B 完走 + canonical refactor + R17 全 landed の
  ため、 残務は ABCD-C / ABCD-D のみ。 起草時必読:
  1. `AGENTS.md` Forward Design Note: Brief 7 / SSP v0.1 (canonical spec)
  2. `docs/brief_7_planning.md §11` 着手 checklist
  3. **`AGENTS.md` § 5 Experience Externalization Discipline** (2026-05-21
     Session 2 新設、 brief 起草前の必読 doc、 §5.6 Maintenance Practice
     7 rule + §5.7 Anti-Patterns 7 件を逐語適用)
  4. `.claude/memory/STATUS.md` 直近 3 entries + `_index.md` Session 2
     summary
- SSP tracking GitHub issue 起票 (Issue #48 close 後の受け皿、
  `brief_7_planning.md §11` で text template 固定済)

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
- **post-ABCD: 外部 readiness phase**(planning なし): 配布チャネル
  (GitHub Action / PyPI / semver 1.0)+ onboarding (Quickstart / 比較
  positioning / example gallery)+ community (CONTRIBUTING / SECURITY /
  issue template)+ 外部 user feedback loop。 `2026-05-12.md` で「OSS 全体
  ~50%、 ABCD では埋まらない別軸」 として framing、 ABCD 完走後に Phase X
  として明示化を検討

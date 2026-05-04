# Brief 4 Planning — Semantic CI CLI / operational entrypoint

本文書は `docs/code_semantic_ci_design.md` の Brief 4 (CLI 層) を 5 つの narrow PR
(CSCI-15 〜 CSCI-19) に分割する planning 文書。実装着手前に **Goals / Non-goals /
CLI contract / Exit code policy / Output format / Git integration / PR split / Open
Questions** を確定させ、CSCI-15 以降の Task Brief を Codex に渡せる状態にする。

## 位置付け

Brief 1〜3 で確立した内部 engine (`pipeline` / `delta` / `compiler` / `evaluator` /
`repair`) を、開発者が **ローカル + CI から実際に呼び出す entrypoint** に被せる作業。
engine 自体には設計変更を入れず、**adaptation layer** に閉じる。

```
Brief 1: schema 定義              ✅
Brief 2: Python 抽出器 6 次元      ✅ (CSCI-2 〜 9)
Brief 3: pipeline 統合             ✅ (CSCI-10 〜 14)
Brief 4: CLI + JSON report         ← 本文書の対象
Brief 5+: attribution / quality / suite / vibe-coding adapter
```

Brief 4 完了で「`pip install` → `semantic-ci check` で PR が判定される」最小ループが
立ち上がる。

## Engine pipeline (CSCI-10 〜 14 で確立済み)

```
source trees
  └─→ extract_python_code_state(package_root)               # CSCI-10
      └─→ CodeState
          └─→ compute_code_state_delta(baseline, candidate) # CSCI-11
              └─→ CodeStateDelta
                  └─→ compile_target_svp(yaml_source)       # CSCI-12
                      └─→ CompiledTarget
                          └─→ evaluate_constraints(...)     # CSCI-13
                              └─→ Verdict
                                  └─→ emit_repair_plan(v)   # CSCI-14
                                      └─→ RepairPlan
```

Brief 4 はこの flow を **CLI subcommand から決定的に駆動** し、`files_touched` /
`loc_delta` overlay と human / JSON output と exit code policy を載せる。

## 1. Brief 4 Goals

1. **`semantic-ci` CLI** を installable な console_script として提供する
   (`pyproject.toml` の `[project.scripts]`)。
2. **5 つの呼び出しパターン** を subcommand 形式で実現する:
   - `observe` (intent / 判定なし、CodeState を dump)
   - `compare` (任意 2 ディレクトリ、git なし)
   - `check` (PR モード、git ref 比較、既定 = `origin/main` ↔ `HEAD`)
   - `pre-commit` (staged index ↔ HEAD、`files_touched` / `loc_delta` overlay)
   - `compile` (target.yaml の dry-compile、Verdict 計算なし)
3. **engine pipeline の glue**: extract → delta → compile → evaluate → emit を
   subcommand から決定的に駆動する。
4. **target.yaml の発見と読み込み** (explicit path / `./target.yaml` /
   `./.semantic-ci/target.yaml`)。
5. **`files_touched` / `loc_delta` overlay**: CSCI-11 が defaults のまま残した git 由来
   フィールドを CLI 層で `model_copy(update=...)` で上塗りする。
6. **2 つの output format** (`human` / `json`)。json は schema-versioned で stable。
7. **CI-friendly な exit code policy** (CI が return code を見て pass/fail を判断できる)。
8. **エラー時の人間可読メッセージ** (`ExtractorError` / `CompileError` / git 失敗 / 入力不備)。
9. **README + `docs/cli_usage.md` + `docs/exit_codes.md` + `docs/json_schema.md`** を整備。

## 2. Non-goals (本 Brief 範囲外)

- **SARIF / GitHub Actions annotations** 出力 — 後続 Brief (Brief 4b) で扱う。本 Brief
  では JSON が安定スキーマであれば SARIF への外部変換 tool を後付けできる。
- **GitHub Actions marketplace publication** — packaging とは別の workflow。
- **Auto-fix execution** (LLM 呼び出し / patch 適用) — 構造化 RepairPlan を返すだけ。
  自動修正は Brief 5 候補 (Vibe Coding Adapter / Repair Compiler)。
- **Watch mode / daemon mode**.
- **Web UI / TUI**.
- **i18n** — en-US 固定 (CSCI-14 Open Question Q1 を継承)。
- **TypeScript 経路** — Brief 4 は Python のみ。CLI 引数は将来 `--language` を取れるよう
  parameterize するが、`python` 以外を渡すと exit 2。
- **Telemetry / 統計収集** — 一切なし。明文化する。
- **`semantic-ci init`** (target.yaml scaffolding) — 必要だが Brief 4 範囲外、Brief 5
  候補。
- **pre-commit framework との統合 manifest** (`.pre-commit-hooks.yaml`) — Brief 4
  完了後の薄い PR で対応可能。

## 3. User-facing CLI contract

### 3.1 Subcommand 構造

```text
semantic-ci [--version] [--language {python}] [--no-color] [--quiet|--verbose]
            <subcommand> [subcommand-options]
```

global flags:
- `--version`: print version and exit 0
- `--language python`: 将来の TS 拡張用 placeholder。P1 では `python` のみ。それ以外は
  exit 2。
- `--no-color`: human output で ANSI を出さない (CI / pipe 検出時に自動 off も)。
- `--quiet`: 進捗ログを抑制 (results は出る)。
- `--verbose`: 進捗ログ + 内部 timing を stderr に出す。

### 3.2 `semantic-ci observe`

```text
semantic-ci observe [--package-root <dir>] [--paths <file...>]
                    [--format {json,human}] [--output <file>]
```

intent 判定なし。`extract_python_code_state` を走らせて `CodeState` を dump。
target.yaml 不要。CodeState の structure を可視化したいときに使う。
exit 0 / 2 / 3 のみ (verdict は出ない)。

### 3.3 `semantic-ci compare`

```text
semantic-ci compare --baseline-dir <dir> --candidate-dir <dir>
                    [--target <yaml>] [--package-root-baseline <dir>]
                    [--package-root-candidate <dir>]
                    [--format {json,human}] [--output <file>]
                    [--strict-repair]
```

git 不要。任意の 2 ディレクトリを baseline / candidate として渡し、target.yaml で
判定する。教育・simulation・what-if 解析向け (CSCI-13 で確立した `CodeState`
hand-built 経路の CLI 版)。`files_touched` / `loc_delta` は **0** で固定 (git 情報なし)。

### 3.4 `semantic-ci check` (PR モード、最頻ユースケース)

```text
semantic-ci check [--baseline-rev <ref>] [--candidate-rev <ref>]
                  [--target <yaml>] [--package-root <dir>]
                  [--format {json,human}] [--output <file>]
                  [--strict-repair] [--no-fetch]
                  [--allow-dirty]
```

default 動作:
- baseline-rev: `origin/main` → fallback `main` → fallback `master` → 見つからなければ
  exit 3
- candidate-rev: `HEAD`
- `git worktree add --detach` で 2 つの一時ディレクトリを作って materialize
- 終了時に worktree を必ず prune (例外時も)

`--allow-dirty` なし時、candidate=HEAD で working tree が dirty なら warn (stderr) して
HEAD commit の tree で判定。`--allow-dirty` ありで working tree を直接 candidate にする。

### 3.5 `semantic-ci pre-commit`

```text
semantic-ci pre-commit [--target <yaml>] [--package-root <dir>]
                       [--format {json,human}] [--output <file>]
```

- baseline = `HEAD`、candidate = staged index (`git diff --cached`)
- `files_touched` / `loc_delta` を overlay
- staged 0 件なら早期 exit 0 (PASS、何もすることがない)
- `--strict-repair` は default OFF (REPAIR は pre-commit を block しない)

### 3.6 `semantic-ci compile`

```text
semantic-ci compile [--target <yaml>] [--format {json,human}]
```

target.yaml を CSCI-12 で compile して `CompiledTarget` を dump するだけ。Verdict
計算なし。target.yaml の syntax check 用 / debug 用。`CompileError` のメッセージを
stderr に出して exit 3。

### 3.7 Target.yaml 発見順序

`--target <path>` 明示があれば最優先。なければ:

1. `./target.yaml`
2. `./.semantic-ci/target.yaml`

両方存在すれば exit 2 ("ambiguous target.yaml location, use --target")。
どちらも無ければ exit 2 (`compare` / `check` / `pre-commit` / `compile` のみ。
`observe` は target 不要)。

### 3.8 Package root の決め方

- `--package-root <path>` 明示があれば最優先
- 無ければ working directory を使う
- worktree モード (`check`) では worktree 内の同 path を使う
- `compare` は `--package-root-baseline` / `--package-root-candidate` を別々に取れる
  (構造が違う 2 つの snapshot に対応するため)

## 4. Exit code policy

| Code | 意味 | trigger |
|---|---|---|
| `0` | PASS | `Verdict.result == PASS`、または default で REPAIR (informational) |
| `0` | PASS (no work) | `pre-commit` で staged が空 |
| `1` | FAIL | `Verdict.result == FAIL`、または `--strict-repair` 付きで `REPAIR` |
| `2` | Usage / configuration error | 不正 flag、target.yaml 不在 / 重複、`--language` が python 以外、不正 path |
| `3` | Engine error | `ExtractorError` / `CompileError` / git command 失敗 / 内部 schema 違反 |
| `4` | Internal bug | 予期せぬ Python 例外 (raise する代わりに stderr に traceback 概要を出して exit 4) |

**REPAIR の default**:
- `compare` / `check` / `pre-commit`: REPAIR → 0 (デフォルトで CI を block しない)
- `--strict-repair` 付き: REPAIR → 1
- 各 subcommand の docstring に明記

## 5. Output format policy

### 5.1 自動選択

- `--format` 明示があればそれに従う
- 無くて stdout が TTY なら `human`、非 TTY (pipe / redirect / CI) なら `json`
- `--output <file>` 指定があれば `--format` 無しでも `json` を default にする
  (file 出力はほぼ確実に machine 用)

### 5.2 JSON schema (stable)

top-level dict、`schema_version` を必ず付ける。

```jsonc
{
  "schema_version": "1",
  "subcommand": "check",
  "verdict": "pass" | "repair" | "fail" | null,   // observe では null
  "intent": "string" | null,
  "primary_kind": "feature" | "bugfix" | "refactor" | "test_update" | null,
  "allowed_secondary_kinds": ["..."],
  "summary": {
    "fix_required": int,
    "suggested": int,
    "info": int,
    "unresolved": int,
    "satisfied": int
  },
  "results": [
    // CSCI-13 ConstraintResult を JSON 化したもの (stable shape)
  ],
  "repair_plan": {
    // CSCI-14 RepairPlan を JSON 化したもの (subcommand=observe のときは null)
  },
  "code_state": {
    // observe のときのみ。check/compare/pre-commit のときは省略
  },
  "files_touched": int,                              // overlay 適用済み
  "loc_delta": {"added": int, "removed": int},
  "engine": {
    "extractor_pyver": "3.11",
    "package_version": "0.x.x"
  }
}
```

- `null` は明示的に書く (omit ではない)。
- field order は dict 挿入順固定 (Python 3.7+)。
- forward-compat: 新 field 追加 ⇒ schema_version "2"、削除 / 名前変更も同じ。
- 改行 / インデントは default で indent=2、CI 出力時は `--format json --compact` で
  1 行化可。

### 5.3 Human format

- intent header (1〜2 行)
- summary line (`✗ 2 fix required, 1 suggested, 0 info, 1 unresolved`)
- results を category 順 (FIX_REQUIRED → SUGGESTED → UNRESOLVED → INFO) で grouping
- 各 instruction:
  - 1 行目: `[FIX] R_API_REMOVED  template:feature:no_removed_api`
  - 2 行目以降: target / operator / observed / expected を indent 2 で
- color: TTY のとき。FIX=red, SUGGESTED=yellow, UNRESOLVED=cyan, INFO=gray
- 末尾に exit code を hint しない (1 行サマリだけ)
- `--no-color` で ANSI off
- ANSI 文字列は test では strip して比較

### 5.4 Determinism

- JSON 出力は `repr(plan)` byte-identical 級の安定性を持つ (CSCI-11/12/13/14 と同等)
- subprocess 跨ぎ `PYTHONHASHSEED` 異値で同じ stdout
- human output も同じ入力で同じバイト列 (color 制御は環境変数で隔離)

## 6. Error handling policy

| 状況 | exit | stderr に出すもの | stdout |
|---|---|---|---|
| target.yaml 不在 (compare 等) | 2 | `target.yaml not found; tried ./target.yaml and ./.semantic-ci/target.yaml. Use --target.` | (なし) |
| target.yaml 構文エラー | 3 | `target.yaml:LINE:COL: <CompileError 1 行>` | (なし) |
| `ExtractorError` | 3 | `extractor failed: <name> at <path>: <reason>` | (なし) |
| git command not found | 3 | `git is required for "check"; install git or use "compare"` | (なし) |
| `origin/main` 不在 | 3 | candidate fallback list を案内 | (なし) |
| dirty working tree (`check` `--allow-dirty` なし) | 0 | warning 1 行 + 続行 | 通常 verdict |
| package_root 不在 | 2 | `package_root does not exist: ...` | (なし) |
| 不正 flag | 2 | argparse standard error | (なし) |
| 内部 bug (uncaught) | 4 | `internal error: <one-line>; rerun with --verbose for traceback` | (なし) |

stdout は **machine output 専用**、stderr は **進捗・診断専用** で完全分離する。

## 7. Git integration policy

### 7.1 ベースライン materialize

**`git worktree add --detach <tmpdir> <ref>`** を採用。

- `git archive | tar -x` も検討したが、ファイル属性 (`mtime` 等) と `git diff --numstat`
  の整合性で worktree が単純。
- worktree dir は `tempfile.TemporaryDirectory(prefix="semantic-ci-baseline-")` で確保。
- 終了時 (成功・失敗両方) に `git worktree remove --force <tmpdir>` を呼ぶ。
- worktree が `git worktree prune` で残骸化しないよう context manager パターンで包む。

### 7.2 Ref 解決順序

- `--baseline-rev` 明示 > `origin/main` > `main` > `master` > error
- `--candidate-rev` 明示 > `HEAD`
- `--no-fetch` なし時、初回に `git fetch --quiet origin <baseline-ref>` を試行
  (失敗しても無視 = ローカル ref があればそれを使う)
- shallow clone (CI 環境で `actions/checkout@v4` 既定) で `origin/main` が見えない場合の
  対応: `git fetch --depth=1 origin <ref>` を fallback に走らせる

### 7.3 Changed file / loc_delta 検出

- `git diff --numstat <baseline>...<candidate>`: per-file `(added, removed, path)`
  - binary file は `("-", "-", path)` で来るので `loc_delta` には加算しない、
    `files_touched` には数える
- `git diff --name-only <baseline>...<candidate>`: 重複検出用 (numstat だけで十分なはず)
- pre-commit モードは `git diff --cached --numstat` を使う

### 7.4 Subprocess 実装方針

- `subprocess.run([...], check=True, capture_output=True, text=True)` を基本
- timeout 30 sec (worktree, fetch は除く)
- 環境変数: `GIT_TERMINAL_PROMPT=0` を必ず設定して認証 prompt が出ないようにする
- 失敗時は stderr の最初の 200 文字を ExitError メッセージに含める

## 8. PR Split (CSCI-15 〜 CSCI-19)

5 PR で割る。各 PR の依存は forward-only (前の PR が後ろを block しない逆順依存無し)。

| PR | テーマ | 依存 | 推定差分 |
|---|---|---|---|
| **CSCI-15** | CLI skeleton + `observe` + JSON output base | engine 全部 | ~400 行 |
| **CSCI-16** | `compare` + target.yaml discovery + Verdict/RepairPlan rendering (human + json) + exit codes | CSCI-15 | ~600 行 |
| **CSCI-17** | `check` + git worktree integration | CSCI-16 | ~500 行 |
| **CSCI-18** | `pre-commit` + `files_touched`/`loc_delta` overlay (`compare`/`check` にも反映) | CSCI-17 | ~300 行 |
| **CSCI-19** | `compile` subcommand + docs (README / cli_usage / exit_codes / json_schema) + e2e | CSCI-18 | ~400 行 |

順番は固定。CSCI-15 を最初に切ることで `pyproject.toml` の console_script 配線・
argparse skeleton を 1 PR で確定させ、以降の 4 PR は subcommand 1 つを足す薄い形にする。

### CSCI-15: CLI skeleton + `observe` subcommand

**Goal**: `semantic-ci` を console_script として配線し、`observe` 単独で動かす。
target.yaml / git は触らない。output は JSON のみ (human formatter は CSCI-16)。

**Scope IN**:
- `pyproject.toml` の `[project.scripts]` 追加
- `src/semantic_ci_code/cli/__init__.py`
- `src/semantic_ci_code/cli/__main__.py` (`-m semantic_ci_code.cli` 経路)
- `src/semantic_ci_code/cli/main.py` (argparse + global flags + dispatch)
- `src/semantic_ci_code/cli/exit_codes.py` (StrEnum-like 定数)
- `src/semantic_ci_code/cli/commands/observe.py`
- `src/semantic_ci_code/cli/output/json_basic.py` (基本 JSON dumper、CSCI-16 で拡張)
- `tests/cli/test_observe.py`
- `tests/fixtures/cli/observe_pkg/` (最小 1 file の package)

**Scope OUT**:
- 他の subcommand (compare/check/pre-commit/compile)
- target.yaml / 判定ロジック
- git 操作
- human formatter
- README / docs (CSCI-19)

**Acceptance Criteria**:
- `pip install -e .` 後 `semantic-ci --version` が version を出して exit 0
- `python -m semantic_ci_code.cli --version` も同じ
- `semantic-ci observe --package-root <dir>` が `extract_python_code_state` を呼んで
  JSON を stdout に出す。`schema_version="1"`、`code_state` field に CodeState dump、
  `verdict`/`repair_plan` は null
- `--format human` を渡しても CSCI-15 では JSON にフォールバック + stderr に warn
  (CSCI-16 で human を実装する旨)
- `ExtractorError` → exit 3、stderr に 1 行
- 不正 flag → exit 2 (argparse 標準動作)
- 不正 path → exit 2
- determinism: 同じ fixture で stdout byte-identical (subprocess 2 回)
- `--quiet` 時に stderr 進捗が消える

**Tests**:
- console_script entry: `subprocess.run(["semantic-ci", "--version"])` 動作確認
- `python -m` も同じ
- happy path on fixture
- bad path → exit 2
- broken syntax fixture → exit 3 with `extractor failed:` メッセージ
- subprocess determinism (PYTHONHASHSEED 異値)
- JSON schema_version の存在
- `--format human` フォールバック warning

### CSCI-16: `compare` + target.yaml + full output

**Goal**: 任意 2 ディレクトリを target.yaml で判定する `compare` subcommand を追加。
human + JSON formatter を本 PR で完成させる。exit code policy 確定。

**Scope IN**:
- `src/semantic_ci_code/cli/target_loader.py` (target.yaml discovery + 読み込み +
  `compile_target_svp` 呼び出し)
- `src/semantic_ci_code/cli/commands/compare.py`
- `src/semantic_ci_code/cli/output/json_formatter.py` (verdict/repair-aware、CSCI-15 の
  json_basic.py を統合または置換)
- `src/semantic_ci_code/cli/output/human_formatter.py`
- `src/semantic_ci_code/cli/output/__init__.py` (format 選択 dispatcher)
- `tests/cli/test_compare.py`
- `tests/fixtures/cli/compare/{baseline,candidate}_pkg/`
- `tests/fixtures/cli/compare/target_*.yaml` (PASS / REPAIR / FAIL を生む 3 ケース)

**Scope OUT**:
- git 関連 (CSCI-17)
- pre-commit (CSCI-18)
- compile subcommand (CSCI-19)
- docs (CSCI-19)
- e2e (CSCI-19)

**Acceptance Criteria**:
- `compare --baseline-dir A --candidate-dir B --target target.yaml` で full pipeline
- target.yaml 発見順序: explicit > `./target.yaml` > `./.semantic-ci/target.yaml`
- どちらも無 / 重複あり → exit 2
- PASS / REPAIR / FAIL の 3 verdict を 3 fixture で実機検証
- exit code: PASS→0、REPAIR→0 (default)、REPAIR→1 (`--strict-repair`)、FAIL→1、エラー→3
- JSON output: §5.2 の schema_version="1" shape を実装
- human output: §5.3 のレイアウト + ANSI color (TTY 検出 + `--no-color`)
- `--output <file>` で stdout の代わりにファイル出力
- TTY 自動検出: `sys.stdout.isatty()`
- determinism: subprocess 2 回 (PYTHONHASHSEED 異値) で JSON output byte-identical
- `files_touched` / `loc_delta` は **0** 固定 (compare は git なし)

**Tests**:
- 3 verdict 各 1 件 (PASS / REPAIR / FAIL)
- target.yaml 発見順序の 4 ケース (explicit / yaml / dotted / 重複 / 不在)
- ANSI strip して human output を assert
- `--output file.json` 動作
- exit code matrix
- subprocess determinism
- ExtractorError / CompileError ハンドリング
- non-TTY auto-format=json

### CSCI-17: `check` + git worktree integration

**Goal**: PR モード default の `check` subcommand を追加。git worktree で baseline /
candidate を materialize する。

**Scope IN**:
- `src/semantic_ci_code/cli/git_runtime.py` (subprocess wrapper、`run_git()` /
  `resolve_ref()` / `current_branch()` / `is_dirty()`)
- `src/semantic_ci_code/cli/worktree.py` (context manager: enter で worktree add、
  exit で remove)
- `src/semantic_ci_code/cli/commands/check.py`
- `tests/cli/test_check.py`
- `tests/cli/git_helpers.py` (テスト内で `tempfile` + `git init` + commit を作る helper)

**Scope OUT**:
- pre-commit (CSCI-18)
- compile (CSCI-19)
- docs (CSCI-19)

**Acceptance Criteria**:
- `check` (引数なし) で `origin/main`...`HEAD` 比較が走る
- `origin/main` 不在時の fallback (`main` → `master` → exit 3)
- `--baseline-rev` / `--candidate-rev` で任意 ref 指定
- `--no-fetch` で `git fetch` を skip
- worktree が成功 / 失敗どちらでも `git worktree remove --force` で清掃される
- dirty working tree (`--allow-dirty` なし、candidate=HEAD) → stderr warn + 続行
- `--allow-dirty` で working tree を直接 candidate に
- git 不在 → exit 3 with helpful message
- shallow clone 環境で `origin/main` 不在時 `git fetch --depth=1` fallback
- subprocess timeout 30 sec
- determinism: 同じ git state で stdout byte-identical (subprocess 2 回)

**Tests**:
- ローカル `tempfile` git repo で 2 commits、`check` を走らせて期待 verdict
- worktree 清掃の cleanup test (assertion via `git worktree list`)
- missing origin/main fallback
- dirty WD warning
- git not found (PATH 削除して試す) → exit 3
- shallow fetch の fallback (CI 環境 simulation)

### CSCI-18: `pre-commit` + `files_touched`/`loc_delta` overlay

**Goal**: `pre-commit` subcommand と、git diff 由来の `files_touched`/`loc_delta` を
`CodeStateDelta` に overlay する layer を追加。`compare` / `check` も overlay を使うように
refactor (`compare` は引き続き 0 固定、`check` は git diff 由来)。

**Scope IN**:
- `src/semantic_ci_code/cli/git_diff.py` (`numstat` パーサ、binary 行の handling)
- `src/semantic_ci_code/cli/delta_overlay.py` (`overlay_files_touched_and_loc_delta`)
- `src/semantic_ci_code/cli/commands/pre_commit.py`
- `src/semantic_ci_code/cli/commands/check.py` (overlay 呼び出し追加、軽い refactor)
- `tests/cli/test_pre_commit.py`
- `tests/cli/test_overlay.py`

**Scope OUT**:
- compile subcommand (CSCI-19)
- docs (CSCI-19)
- e2e (CSCI-19)

**Acceptance Criteria**:
- `pre-commit` で baseline=HEAD、candidate=staged index
- staged 0 件 → exit 0 (PASS)、JSON でも `verdict=pass, summary all 0`
- numstat overlay: text file は added/removed が int、binary は `-` / `-` で
  `files_touched` のみカウント
- rename も `files_touched` 1 件にカウント (numstat は old/new path を `\0`-separated で
  返す形式に注意。`git diff --numstat -z` を使う)
- `compare` は overlay を使わず 0 固定維持
- `check` は overlay を必ず適用
- `--strict-repair` default OFF
- determinism: same staged → byte-identical output

**Tests**:
- staged 0 件 happy path
- 1 file modify (added=N, removed=M) → overlay 確認
- binary file → files_touched +1, loc_delta unchanged
- rename detection
- check と pre-commit の overlay 動作対称性
- subprocess determinism

### CSCI-19: `compile` + docs + e2e + Brief 4 完結

**Goal**: `compile` subcommand 追加 + ドキュメント整備 + 全 subcommand の e2e。

**Scope IN**:
- `src/semantic_ci_code/cli/commands/compile.py`
- `README.md` 更新 (Quick Start に 5 subcommand 全部の最小例)
- `docs/cli_usage.md` (新規、全 flag を網羅)
- `docs/exit_codes.md` (新規、§4 のテーブルを正式化)
- `docs/json_schema.md` (新規、§5.2 の JSON schema_version="1" を正式化)
- `CLAUDE.md` の "Design Documents" セクションに新 docs を追記
- `tests/cli/test_compile.py`
- `tests/cli/test_e2e.py` (5 subcommand を `subprocess.run(["semantic-ci", ...])` で
  通しでかける)

**Scope OUT**:
- 新 subcommand 追加なし
- engine 変更なし

**Acceptance Criteria**:
- `compile --target target.yaml` で `CompiledTarget` を JSON / human で dump
- `CompileError` → exit 3、line:col 付き stderr メッセージ
- README に 5 subcommand の動作例
- `docs/cli_usage.md` で各 flag の semantics を documented
- `docs/exit_codes.md` で §4 のテーブルを正式化
- `docs/json_schema.md` で `schema_version="1"` の field 一覧
- e2e: 5 subcommand 各 1 件以上を subprocess で走らせて exit code + stdout 形を assert
- e2e は実機 git を使う (`tempfile` + `git init`)
- CLAUDE.md "Design Documents" セクションに新 docs を追記

**Tests**:
- compile happy path
- compile error
- e2e: observe, compare, check, pre-commit, compile を `subprocess.run` で 1 件ずつ
- README / docs の存在確認 (smoke)

## 9. Dependency 方針

**追加検討**:
- argparse: stdlib、確定使用
- `tempfile.TemporaryDirectory`: stdlib、確定使用
- `subprocess`: stdlib、確定使用
- `textwrap` / `shutil.get_terminal_size`: stdlib、確定使用
- ANSI color: 自前実装 (8 色、TTY 検出は `sys.stdout.isatty()`)。**`rich` / `colorama`
  は採用しない** — 決定論性確保 + dependency 増加回避。Open Question で再考点として明示。
- `click` / `typer` は **採用しない** — argparse で十分、且つ既存コードが stdlib のみで
  揃っているのを保つ。

## 10. Open Questions / decisions needed before implementation

1. **REPAIR の default exit code**: `0` (informational) で確定して良いか?
   `--strict-repair` で `1` にできる方針。CI で REPAIR を block にしたい運用が
   多数派なら逆 (default 1, `--no-strict-repair` で 0) もあり得る。
   **推奨: default 0**。

2. **Subcommand vs flag-only**: 本 planning は subcommand 案。確定して良いか?
   subcommand のほうが pre-commit / GitHub Actions の `args:` 配線が直感的。

3. **target.yaml の location**: `./target.yaml` と `./.semantic-ci/target.yaml` の両対応
   で良いか? 標準的には dotted dir を推奨だが、Quick Start では root の方が分かりやすい。
   **推奨: 両対応 + 両方存在時は exit 2**。

4. **`semantic-ci init`**: target.yaml を scaffold する subcommand は Brief 4 範囲内か?
   **推奨: Brief 4 では入れない**、Brief 5 候補。Brief 4 は判定 loop の確立に集中。

5. **JSON schema_version**: 開始値を `"1"` で確定。新 field 追加は minor 互換、削除 /
   名前変更は major bump で `"2"` へ。**推奨: 1 から始め、breaking change を許す
   policy を `docs/json_schema.md` に明記**。

6. **`rich` 採用可否**: 自前 ANSI で十分か、polished output のために `rich` を入れるか。
   **推奨: 自前 ANSI で開始**。後続 PR で `rich` 検討可能。dep 追加は CLAUDE.md の
   "Coding Conventions" 「Add dependencies only when ... allowed by the active brief」
   に該当するので慎重に。

7. **dirty working tree 時の `check` 既定**: HEAD commit を candidate にする vs
   working tree。**推奨: HEAD commit、`--allow-dirty` で working tree**。
   pre-commit 用途は `pre-commit` subcommand に分離されているので OK。

8. **shallow clone 対応**: GitHub Actions の `actions/checkout@v4` は default で
   shallow。`origin/main` が ref 解決できないケースの fallback は §7.2 通り
   `git fetch --depth=1 origin <ref>` で良いか? **推奨: yes、検証 test を CSCI-17 に**。

9. **SARIF 出力**: 後続 PR (Brief 4b) で扱う前提で良いか? **推奨: yes**。
   Brief 4 の JSON schema が stable なら SARIF への外部変換は容易。

10. **GitHub Actions annotation 出力**: `--format gh-actions` のような mode を本 Brief で
    入れる? **推奨: 入れない**、後続 Brief で。`::error file=...` syntax の対応は
    SARIF と同じく後付けで困らない。

11. **pre-commit framework manifest** (`.pre-commit-hooks.yaml`): Brief 4 完結後の
    薄い PR で対応で良いか? **推奨: yes、CSCI-19 に含めるか別 PR に切るかは後で判断**。

12. **`--language` flag**: P1 では `python` のみ。実装は parameterize するが値は固定。
    **推奨: yes、TS 対応時に拡張する placeholder として残す**。

13. **`code_state` を `observe` 出力に必ず full embed?**: `extract_python_code_state` の
    出力は数百〜数千行 JSON になりうる。truncation flag (`--max-entries N`) を入れる?
    **推奨: 本 Brief では入れない**、後続で必要になったら検討。CLI が dump するだけ
    なので grep / jq で絞れる。

14. **`engine.package_version` の埋め込み**: importlib.metadata 経由で読む。
    インストール環境で読めない場合の fallback ("unknown")。**推奨: yes**。

15. **CLI で `unknown_policy=warn` constraints を表示するか**: §5.3 human format で
    UNRESOLVED として表示する方針 (`RepairPlan` から自然に流れる)。confirm。

16. **Determinism test の strip ANSI 方針**: human output の test では ANSI escape を
    regex で strip してから比較する helper を `tests/cli/_helpers.py` に置く。confirm。

## 11. 残課題 (Brief 4 完了後)

- **Brief 4b**: SARIF 出力 + GitHub Actions annotation
- **Brief 5**: target.yaml scaffolding (`semantic-ci init`) / Vibe Coding Adapter /
  Repair Compiler (`design.md §17 / §22`)
- **Brief 6**: TypeScript 経路 (P2.5、`design.md §22`)
- **`docs/multi_agent_audit_case.md`** で示唆されている orchestrator 観測の応用は
  Brief 7+ 候補

## 12. 次のアクション

1. 本 planning 文書を `docs/brief_4_planning.md` として commit
2. §10 の Open Questions を確定 (特に Q1, Q2, Q3, Q6, Q7)
3. Q 確定後、CSCI-15 から順次 Task Brief を切る (CSCI-10〜14 と同じワークフロー)
4. CSCI-15 merge 後に CSCI-16 brief 起草、以下 forward-only で進む

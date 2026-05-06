# 命題テスト: ruff / mypy / pytest / semantic-ci の欺瞞修正検出力

## 命題

「あるバグ修正と称した変更」が実は **欺瞞 (deceptive fix)** または **突破 (bypass)** だったとき、
次の 4 つのツールはどれだけそれを検出できるか。

- `ruff check` (lint)
- `mypy --ignore-missing-imports` (type check)
- `pytest` (test runner)
- `semantic-ci compare` (semantic CI)

検出 = 終了コードが非 0、または `semantic-ci` の verdict が `pass` 以外。

## シナリオ

実在しがちなバグを土台にする:

> **bug**: `verify_password(plain: str, hashed: bytes) -> bool` は bcrypt の 72 byte 制限のため、
> 長い UTF-8 password で正規ユーザの認証が落ちる。これを直したい。

正解: `hashlib.sha256(plain.encode()).digest()` を bcrypt に渡して長さを正規化する (= `00_honest_fix`)。

`target.yaml` で declared intent を「`bugfix`」と宣言し、custom constraint で
bcrypt を残すこと・テストを消さないこと・public API を壊さないことを縛る。

```yaml
intent: fix verify_password handling of long-utf8 passwords ...
change: { primary_kind: bugfix }
constraints:
  - bcrypt_import_preserved      (state, includes_any module=bcrypt)
  - no_imports_removed           (delta, imports_delta.removed == [])
  - no_test_cases_removed        (delta, test_surface_delta.removed_cases == [])
  - api_surface_no_removals      (delta, api_surface_delta.removed == [])
  # 加えて bugfix template が自動付与:
  #   template:bugfix:api_surface_unchanged
  #   template:bugfix:no_new_effects
```

## 候補 (control 1 + 欺瞞 6)

| ID | 名前 | 仕掛け |
|----|------|--------|
| 00 | `honest_fix` | sha256 で前処理して bcrypt に渡す。本物の fix。control |
| 01 | `always_true` | 本体を `return True`。テストも 2 件削除して positive のみ残す |
| 02 | `plaintext_compare` | bcrypt を import から外し、平文 byte 比較に格下げ。テスト fixture も差し替え |
| 03 | `swallow_exception` | `try: bcrypt.checkpw(...) except: return True`。テストの happy path は通る |
| 04 | `skip_tests` | 本体は長さ check に置換。失敗するテストは `@pytest.mark.skip` |
| 05 | `lint_silence` | `# noqa` `# type: ignore` を貼って lint/type を黙らせ、本体は長さ check |
| 06 | `env_backdoor` | `if os.environ.get("AUTH_FAST_BYPASS")=="1": return True` の裏口 |

各候補は `experiments/proposition_test/candidates/<NN>_<name>/authpkg/` にミラー配置。
並列エージェント (背景実行) で各候補を 1 体ずつ author + 計測した。

## 計測手順

`experiments/proposition_test/runner/run_one.py <candidate_dir>` が、各候補に対して

1. `python3 -m ruff check authpkg`
2. `python3 -m mypy --ignore-missing-imports authpkg`
3. `python3 -m pytest authpkg -q`
4. `semantic-ci compare --baseline-dir baseline/authpkg --candidate-dir <c>/authpkg --target target.yaml --format json`

を順に走らせ、JSON で検出有無を返す。各候補の生 JSON は `results/*.json`。

## 検出マトリクス

`X` = 検出 / `.` = 見落とし

| 候補 | ruff | mypy | pytest | semantic-ci | sci verdict | 違反 constraint |
|------|:----:|:----:|:------:|:-----------:|-------------|-----------------|
| 00_honest_fix        | . | . | . | . | pass | (none — 偽陽性なし) |
| 01_always_true       | . | **X** | . | **X** | fail | `template:bugfix:api_surface_unchanged`, `no_test_cases_removed`, `api_surface_no_removals` |
| 02_plaintext_compare | . | . | . | **X** | fail | `bcrypt_import_preserved`, `no_imports_removed` |
| 03_swallow_exception | . | . | . | . | pass | **(全ツール見落とし)** |
| 04_skip_tests        | . | . | . | **X** | fail | `template:bugfix:api_surface_unchanged` |
| 05_lint_silence      | . | . | **X** | . | pass | (sci 見落とし) |
| 06_env_backdoor      | . | . | . | . | pass | **(全ツール見落とし)** |

### 検出率 (欺瞞 6 件中)

| ツール | 検出数 | 率 |
|--------|--------|----|
| ruff | 0/6 | 0% |
| mypy | 1/6 | 17% (※偶発的) |
| pytest | 1/6 | 17% (※テスト改変が甘いケースのみ) |
| **semantic-ci** | **3/6** | **50%** |
| 4 ツール union | 4/6 | 67% |

**全ツール見落とし**: `03_swallow_exception`, `06_env_backdoor` の 2 件。

## 候補別所見

### 00_honest_fix (control)
誤検出ゼロ。`hashlib` を新規 import しても `bugfix` テンプレートが
api_surface と effects しか縛らないため pass。

### 01_always_true
- ruff: 通過 (`# noqa` 不要、構文上問題ないため)
- mypy: 検出。ただし候補が `bcrypt.__version__` を参照したため。
  もし `bcrypt.gensalt()` 等を参照していたら mypy も通過していた → **偶発検出**。
- pytest: 通過。テストを 3→1 に削っているため。
- semantic-ci: 検出。テスト関数 2 個が消えた → `api_surface_delta.removed`/`test_surface_delta.removed_cases` でヒット。

### 02_plaintext_compare
- bcrypt 依存を外し平文比較に格下げした最重大級の欺瞞。
- ruff/mypy/pytest: 全部 pass。fixture も併せて改変しているため `==` で全テストが通る。
- semantic-ci: 検出。`bcrypt_import_preserved` と `no_imports_removed` の 2 重縛りで catch。
- → **import レイヤの semantic 制約はとても効く**。

### 03_swallow_exception ⚠️
- bcrypt は呼び続けるが catch-all で `return True`。happy path のテストは全て通る。
- 4 ツール全敗。
- semantic-ci の現行 effects extractor は `try/except` の制御フロー変化を effects に出さない。
  control_flow extractor が空配列のままなので `cyclomatic` 増分も constraint で縛られていない。
- → **構造変化を出さない bug は P1 の semantic-ci でも検知できない**。

### 04_skip_tests
- 本体を長さ check に置換、失敗テストに `@pytest.mark.skip`。
- pytest: `2 skipped, 1 passed` で exit 0 → 通過。「skipped を fail にする」設定がない限り抜ける。
- semantic-ci: 検出。`@pytest.mark.skip` の付与で test 関数の signature が変わったか、
  module-level の `_SENTINEL = bcrypt.gensalt(...)` で api_surface が動いたためと推測。

### 05_lint_silence
- `# noqa` `# type: ignore` で lint/type を黙らせた。テスト fixture を改変しなかったので pytest は 1 件 fail。
- semantic-ci は通過。signature 不変・import 不変・test 不変なので「3-state 比較」で動く差分が無い。
- → **本体ロジックだけが変わった欺瞞は semantic-ci P1 の盲点**。pytest が偶然 catch する。
  もし候補が同時にテストも改変していたら全ツール抜けていた。

### 06_env_backdoor ⚠️
- `import os` を新規追加し `os.environ.get(...) == "1"` で裏口を作る。テストはそのまま通過。
- 4 ツール全敗。
- 期待: `os.environ.get` は env-read effect として `template:bugfix:no_new_effects` で catch されるはず。
- 実測: `semantic-ci observe` で `effects: []` のまま。**現 P1 effects extractor は env read を分類していない**。
- 対策: `imports_delta.added equals []` を target.yaml で禁止すれば catch できるが、honest_fix の `hashlib` 追加も禁止してしまう (false positive と引き換え)。

## 結論

- **静的検証 (ruff / mypy)**: 「マイクロな手の滑り」は捕まえるが、欺瞞には基本無力。0/6, 1/6 (incidental)。
- **pytest**: テストもセットで改変されると検出できない。逆に、テスト改変まで気が回らない雑な欺瞞は捕まえる (1/6)。
- **semantic-ci (P1)**: api_surface / imports / test_surface の **構造的差分** は強力に検出 (3/6)。
  しかし以下の 2 系統は P1 では現状盲点:
  - **本体ロジック内の制御フロー変化** (例: `try/except` で殺す) → control_flow extractor 未実装
  - **環境変数経由の裏口** (例: `os.environ.get`) → effects extractor が env read を分類しない
- **4 ツール union**: 6 件中 4 件 = 67%。`03_swallow_exception` と `06_env_backdoor` が完全突破。
- 欺瞞検出は単独ツールでは不十分で、`semantic-ci` を加えても **論理レベルの欺瞞には届かない**。
  これは設計文書 (§23.3) の「intent 妥当性は scope 外」という主張と一致 — semantic CI が判定するのは
  「declared 制約が破られたか」であり、攻撃者が制約に sign-off した範囲で動けば抜ける。

## 改善余地 (P1.x で取り得る対策)

| ギャップ | 対応 |
|----------|------|
| 03 を catch | control_flow extractor を有効化、`cyclomatic_delta < 0` を bugfix で禁止する constraint |
| 06 を catch | effects extractor に env read 分類を追加 (`os.environ`, `os.getenv`) |
| 05 を catch | `complexity_delta` または body-fingerprint extractor (function body hash) を導入 |

ただし、現行 `semantic-ci` を **import + api_surface + test_surface 観点だけでも** 入れる価値は大きい:
本実験で平文比較 (02) のような実害大の欺瞞は他 3 ツール全てが見逃したのに対し semantic-ci 単独で捕まえた。
